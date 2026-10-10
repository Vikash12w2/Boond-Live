"""
Standing-water balance and PAU irrigation rule for transplanted
paddy (DATA_GUIDE 4.6). Day 1 is the transplanting date.

State carried between days:
    pond_mm       water standing above the soil
    depletion_mm  soil water below saturation, once the pond has gone
    dry_days      consecutive days ending with no standing water
"""

from engine.advisor import confident_rain_total, normalise_probabilities
from engine.data import get_crop, get_setting, get_soil, max_advised_depth
from engine.kc import get_kc
from engine.water_balance import calculate_ks, calculate_taw, get_root_depth


# DATA_GUIDE 4.6: in the first two weeks, top up when the pond
# falls below 20 mm.
LOW_POND_MM = 20.0

# DATA_GUIDE 4.6: HEAT PROTECTION for paddy = keep 5 cm standing water.
HEAT_POND_MM = 50.0


def paddy_water(crop="paddy"):
    return get_crop(crop)["paddy_water"]


def initial_paddy_state(crop="paddy"):
    """
    The field is flooded to the target pond at transplanting.
    """
    return {
        "pond_mm": float(paddy_water(crop)["target_pond_mm"]),
        "depletion_mm": 0.0,
        "dry_days": 0
    }


def update_paddy_day(day, soil, et0, rain, irrigation, state, crop="paddy"):
    """
    One day of the pond balance.

    Water in refills the soil first, then the pond. While a pond
    stands, it loses percolation (soils.json
    paddy_percolation_mm_per_day) and ETc. Once it has gone, ETc
    dries the soil, reduced by Ks with the crop's p (FAO-56
    Table 22: 0.20 for rice). Water above the bund storage
    overflows. All rain counts: the 0.2 x ET0 rule is for
    upland soil.
    """
    water = paddy_water(crop)

    kc = get_kc(day, crop)
    potential_etc = kc * et0

    taw = calculate_taw(soil, get_root_depth(day, crop))
    p = get_crop(crop)["depletion_fraction"]

    pond = state["pond_mm"]
    depletion = min(state["depletion_mm"], taw)

    water_in = rain + irrigation
    refill = min(depletion, water_in)
    depletion -= refill
    pond += water_in - refill

    percolation = min(pond, get_soil(soil)["paddy_percolation_mm_per_day"])
    pond -= percolation

    etc_from_pond = min(pond, potential_etc)
    pond -= etc_from_pond

    ks = calculate_ks(depletion, taw, p)
    etc_from_soil = (potential_etc - etc_from_pond) * ks
    depletion = min(taw, depletion + etc_from_soil)

    overflow = max(0.0, pond - water["bund_storage_mm"])
    pond -= overflow

    dry_days = state["dry_days"] + 1 if pond <= 0 else 0

    new_state = {
        "pond_mm": pond,
        "depletion_mm": depletion,
        "dry_days": dry_days
    }

    details = {
        "day_after_transplanting": day,
        "kc": kc,
        "et0_mm": et0,
        "potential_etc_mm": potential_etc,
        "actual_etc_mm": etc_from_pond + etc_from_soil,
        "ks": ks if etc_from_pond < potential_etc else 1.0,
        "rain_mm": rain,
        "irrigation_mm": irrigation,
        "percolation_mm": percolation,
        "overflow_mm": overflow,
        "taw_mm": taw,
        **new_state
    }

    return new_state, details


def decide_paddy(
    day,
    state,
    future_rain,
    rain_probability,
    heat_result,
    crop="paddy"
):
    """
    PAU rule (Kharif 2026 p.12):
        - keep water standing for the first continuous_ponding_days;
        - then irrigate irrigate_days_after_pond_disappears days
          after the pond has gone, to target_pond_mm plus the
          soil depletion;
        - stop after stop_irrigation_day.
    Confident forecast rain at least as large as the need gives
    SKIP, but only rain inside advisor.paddy_rain_skip_window_days
    (1 = the first forecast day): PAU allows only 2 dry days, so
    waiting longer for rain would stress the crop.
    Heat protection keeps 5 cm of standing water.
    """
    water = paddy_water(crop)

    if day > water["stop_irrigation_day"]:
        return {
            "action": "WAIT",
            "depth_mm": 0.0,
            "reason_code": "IRRIGATION_STOPPED"
        }

    pond = state["pond_mm"]
    depletion = state["depletion_mm"]
    cap = max_advised_depth(crop)

    need = 0.0
    reason_code = "POND_PRESENT" if pond > 0 else "WAITING_AFTER_POND_GONE"

    if day <= water["continuous_ponding_days"]:
        if pond < LOW_POND_MM:
            need = water["target_pond_mm"] - pond + depletion
            reason_code = "KEEP_POND_FIRST_2_WEEKS"

    elif state["dry_days"] >= water["irrigate_days_after_pond_disappears"]:
        need = water["target_pond_mm"] + depletion
        reason_code = "POND_GONE_2_DAYS"

    heat_need = 0.0

    if heat_result["heat_risk"] == "HIGH" and pond < HEAT_POND_MM:
        heat_need = HEAT_POND_MM - pond + depletion

    window = get_setting("advisor", "paddy_rain_skip_window_days")
    threshold = get_setting("rain", "skip_probability_threshold")
    probabilities = normalise_probabilities(rain_probability, len(future_rain))

    confident_rain = confident_rain_total(
        list(future_rain)[:window],
        probabilities[:window],
        threshold
    ) * get_setting("rain", "forecast_rain_discount")

    largest_need = max(need, heat_need)

    if largest_need > 0 and confident_rain >= largest_need:
        return {
            "action": "SKIP",
            "depth_mm": 0.0,
            "reason_code": "RAINFALL_EXPECTED"
        }

    if heat_need > 0:
        return {
            "action": "HEAT_PROTECTION",
            "depth_mm": min(largest_need, cap),
            "reason_code": "HEAT_RISK_KEEP_5_CM"
        }

    if need > 0:
        return {
            "action": "IRRIGATE",
            "depth_mm": min(need, cap),
            "reason_code": reason_code
        }

    return {
        "action": "WAIT",
        "depth_mm": 0.0,
        "reason_code": reason_code
    }
