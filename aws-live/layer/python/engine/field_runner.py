"""
One field, one season: the single daily path used by BOTH the live
daily job and the replay/simulator, so the replay validates exactly
the code that runs in production.

    state = start_state(field)
    result = advance_field(field, state, observed, forecast, events, today)
    store(result["state"]); show(result["advice"])

field     {"crop": crops.json profile key (data.select_profile),
           "soil": soils.json key, "sowing_date": "YYYY-MM-DD",
           "area_acres": float, "lift_m": float, "pump_eff": float or None}
state     JSON-serialisable dict, stored with the field (DynamoDB STATE item)
observed  daily weather, same layout as the cache files:
          {"date": [...], "et0_mm": [...], "rain_mm": [...], "tmax_c": [...]}
          (forecast API past_days, or the archive API for long gaps)
forecast  the same layout starting TODAY, plus optional "rain_prob" (0-1)
events    farmer check-ins: {"date", "type": "WATERED" | "RAIN",
          "level", "mm_assumed" (optional; stored value wins)}

Timing (06:00 job): every day up to YESTERDAY is applied with observed
weather and check-ins, then today's advice is decided from the
forecast that starts today. On a day the farmer follows the advice,
the irrigation reaches the balance through the WATERED check-in.
"""

from datetime import date, timedelta

from engine.advisor import make_daily_decision
from engine.checkins import apply_checkins
from engine.critical import critical_irrigation_due
from engine.data import get_crop, get_setting, is_paddy, max_advised_depth
from engine.heat_rules import assess_heat_risk
from engine.kc import get_kc, get_season_length, get_stage
from engine.paddy import decide_paddy, initial_paddy_state, update_paddy_day
from engine.resources import (
    co2_emissions,
    electricity_cost,
    gross_depth_mm,
    irrigation_volume_litres,
    irrigation_volume_m3,
    pump_energy_kwh
)
from engine.water_balance import (
    calculate_daily_balance,
    calculate_p,
    calculate_raw,
    calculate_taw,
    forecast_water_balance,
    get_root_depth
)


STATE_VERSION = 1


class MissingWeather(ValueError):
    """Observed weather is missing for a day that must be applied."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _as_date(value):
    return date.fromisoformat(value) if isinstance(value, str) else value


def crop_day(field, on_date):
    """Day after sowing (day 1 = sowing / transplanting / planting date)."""
    return (_as_date(on_date) - _as_date(field["sowing_date"])).days + 1


def calculate_resources(
    net_depth_mm,
    area_acres,
    lift_m,
    pump_efficiency=None,
    electricity_tariff=None,
    grid_factor=None
):
    """
    Water, energy, cost and CO2e for one irrigation.

    Volumes and energy use the gross (pumped) depth =
    net depth / config irrigation.application_efficiency.
    The cost is the cost to the power system, not the
    farmer's bill (config cost._why).
    """
    if pump_efficiency is None:
        pump_efficiency = get_setting("energy", "default_pump_efficiency")

    if electricity_tariff is None:
        electricity_tariff = get_setting("cost", "electricity_tariff_inr_per_kwh")

    if grid_factor is None:
        # t CO2 per MWh is the same number as kg CO2 per kWh.
        grid_factor = get_setting("carbon", "grid_emission_factor_t_per_mwh")

    gross_mm = gross_depth_mm(net_depth_mm)

    litres = irrigation_volume_litres(gross_mm, area_acres)
    volume_m3 = irrigation_volume_m3(gross_mm, area_acres)
    energy_kwh = pump_energy_kwh(volume_m3, lift_m, pump_efficiency)

    return {
        "gross_depth_mm": round(gross_mm, 2),
        "litres": round(litres, 2),
        "volume_m3": round(volume_m3, 3),
        "kwh": round(energy_kwh, 3),
        "cost_inr": round(electricity_cost(energy_kwh, electricity_tariff), 2),
        "co2_kg": round(co2_emissions(energy_kwh, grid_factor), 3)
    }


def starting_depletion(soil, crop="wheat", et0=None):
    """
    Depletion at sowing: 0 after a pre-sowing irrigation, otherwise
    RAW (config root_zone.assume_full_at_sowing). Without an ET0 the
    tabulated p is used.
    """
    if get_setting("root_zone", "assume_full_at_sowing"):
        return 0.0

    taw = calculate_taw(soil, get_root_depth(1, crop))

    if et0 is None:
        p = calculate_p(5.0, crop=crop, day_after_sowing=1)
    else:
        p = calculate_p(get_kc(1, crop) * et0, crop=crop, day_after_sowing=1)

    return calculate_raw(taw, p)


def _forecast_lists(forecast, today=None):
    """
    Return (dates, et0, rain, tmax, probability) from `forecast`,
    starting at `today` when the forecast has dates. The forecast is
    cut at the first day with no ET0: days after a gap are not used.
    Missing rain counts as 0 (and its probability as not confident).
    """
    if forecast is None:
        return [], [], [], [], []

    dates = list(forecast.get("date") or [])
    start = 0

    if dates and today is not None:
        key = _as_date(today).isoformat()

        if key not in dates:
            return [], [], [], [], []

        start = dates.index(key)

    et0 = list(forecast["et0_mm"])[start:]
    length = len(et0)

    for index, value in enumerate(et0):
        if value is None:
            length = index
            break

    def column(name, default):
        values = forecast.get(name)

        if values is None:
            return [default] * length

        return list(values)[start:start + length]

    rain = [0.0 if value is None else value for value in column("rain_mm", 0.0)]

    return (
        dates[start:start + length] if dates else [],
        et0[:length],
        rain,
        column("tmax_c", None),
        column("rain_prob", None)
    )


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def start_state(field, et0=None):
    """
    State before the sowing date. Upland crops carry the root-zone
    depletion; paddy carries the pond state.
    """
    crop = field["crop"]
    before_sowing = (_as_date(field["sowing_date"]) - timedelta(days=1)).isoformat()

    state = {
        "version": STATE_VERSION,
        "last_processed_date": before_sowing,
        "water_since_sowing_mm": 0.0
    }

    if is_paddy(crop):
        state.update(initial_paddy_state(crop))
    else:
        state["depletion_mm"] = starting_depletion(field["soil"], crop, et0)

    return state


def apply_day(field, state, on_date, et0, rain, irrigation=0.0):
    """
    Apply one day of observed weather and irrigation to the state.
    Returns (new_state, row). Days before sowing only move the date.
    """
    crop = field["crop"]
    day = crop_day(field, on_date)
    new_state = dict(state, last_processed_date=_as_date(on_date).isoformat())

    if day < 1:
        return new_state, None

    if et0 is None:
        raise MissingWeather(f"No ET0 for {_as_date(on_date).isoformat()}")

    rain = 0.0 if rain is None else rain

    if is_paddy(crop):
        paddy_state, details = update_paddy_day(
            day=day,
            soil=field["soil"],
            et0=et0,
            rain=rain,
            irrigation=irrigation,
            state=state,
            crop=crop
        )
        new_state.update(paddy_state)
        new_state["water_since_sowing_mm"] = state["water_since_sowing_mm"] + rain + irrigation

        row = {
            "date": new_state["last_processed_date"],
            "day": day,
            "et0_mm": et0,
            "rain_mm": rain,
            "irrigation_mm": irrigation,
            "kc": details["kc"],
            "actual_etc_mm": details["actual_etc_mm"],
            "ks": details["ks"],
            "depletion_mm": details["depletion_mm"],
            "pond_mm": details["pond_mm"],
            "dry_days": details["dry_days"],
            "percolation_mm": details["percolation_mm"],
            "overflow_mm": details["overflow_mm"],
            "losses_mm": details["percolation_mm"] + details["overflow_mm"]
        }
        return new_state, row

    balance = calculate_daily_balance(
        day_after_sowing=day,
        soil=field["soil"],
        et0=et0,
        rain=rain,
        irrigation=irrigation,
        previous_depletion=state["depletion_mm"],
        crop=crop
    )

    new_state["depletion_mm"] = balance["depletion_mm"]
    new_state["water_since_sowing_mm"] = (
        state["water_since_sowing_mm"] + balance["effective_rain_mm"] + irrigation
    )

    row = {
        "date": new_state["last_processed_date"],
        "day": day,
        "et0_mm": et0,
        "rain_mm": rain,
        "effective_rain_mm": balance["effective_rain_mm"],
        "irrigation_mm": irrigation,
        "kc": balance["kc"],
        "actual_etc_mm": balance["actual_etc_mm"],
        "ks": balance["ks"],
        "depletion_mm": balance["depletion_mm"],
        "raw_mm": balance["raw_mm"],
        "taw_mm": balance["taw_mm"],
        "losses_mm": balance["deep_percolation_mm"]
    }
    return new_state, row


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------

def _status_advice(field, day, status, reason_code):
    return {
        "status": status,
        "crop": field["crop"],
        "day_after_sowing": day,
        "action": "WAIT",
        "depth_mm": 0.0,
        "reason_code": reason_code,
        "sowing_date": _as_date(field["sowing_date"]).isoformat(),
        "outlook": [],
        **calculate_resources(0.0, field.get("area_acres", 1.0), field.get("lift_m", 30.0),
                              field.get("pump_eff"))
    }


def decide_today(
    field,
    state,
    forecast,
    today=None,
    maximum_depth=None,
    electricity_tariff=None,
    grid_factor=None
):
    """
    Today's advice from the state at the end of yesterday and the
    forecast starting today. Give `today` (a date) or let it be
    state["last_processed_date"] + 1 day.

    status: WAITING (before sowing), ACTIVE, SEASON_OVER (after the
    last crop day). If the forecast is missing, the engine still
    irrigates a field that is already past RAW or due a critical
    irrigation, and otherwise returns NO_FORECAST_DATA.
    """
    crop = field["crop"]

    if today is None:
        today = _as_date(state["last_processed_date"]) + timedelta(days=1)

    today = _as_date(today)
    day = crop_day(field, today)

    if day < 1:
        return _status_advice(field, day, "WAITING", "NOT_SOWN_YET")

    if day > get_season_length(crop):
        return _status_advice(field, day, "SEASON_OVER", "SEASON_OVER")

    dates, future_et0, future_rain, future_tmax, probability = _forecast_lists(forecast, today)
    heat_result = assess_heat_risk(day, future_tmax, crop)
    skip_days = get_setting("advisor", "rain_skip_window_days")

    if maximum_depth is None:
        maximum_depth = max_advised_depth(crop)

    advice = {
        "status": "ACTIVE",
        "crop": crop,
        "date": today.isoformat(),
        "day_after_sowing": day,
        "stage": get_stage(day, crop),
        "heat_stage": heat_result["stage"],
        "heat_risk": heat_result["heat_risk"],
        "max_forecast_tmax_c": heat_result["max_forecast_tmax_c"],
        "rain_probability": probability,
        "rain_next_3d_mm": round(sum(future_rain[:skip_days]), 2),
        "forecast_days": len(future_et0)
    }

    if is_paddy(crop):
        decision = decide_paddy(
            day=day,
            state=state,
            future_rain=future_rain,
            rain_probability=probability,
            heat_result=heat_result,
            crop=crop
        )
        target = get_crop(crop)["paddy_water"]["target_pond_mm"]
        advice.update({
            "pond_mm": round(state["pond_mm"], 2),
            "depletion_mm": round(state["depletion_mm"], 2),
            "dry_days": state["dry_days"],
            "water_wallet_pct": round(max(0.0, min(100.0, 100 * state["pond_mm"] / target)), 1),
            "crossing_day": None,
            "critical_stage": None,
            "outlook": [
                {"date": d, "et0_mm": e, "rain_mm": r, "rain_prob": p}
                for d, e, r, p in zip(dates or [None] * len(future_et0), future_et0, future_rain, probability)
            ]
        })
    else:
        depletion = state["depletion_mm"]
        forecast_balances = forecast_water_balance(
            start_day_after_sowing=day - 1,
            soil=field["soil"],
            future_et0=future_et0,
            future_rain=future_rain,
            initial_depletion=depletion,
            crop=crop
        )

        if forecast_balances:
            raw = forecast_balances[0]["raw_mm"]
            taw = forecast_balances[0]["taw_mm"]
        else:
            taw = calculate_taw(field["soil"], get_root_depth(day, crop))
            raw = calculate_raw(taw, calculate_p(5.0, crop=crop, day_after_sowing=day))

        critical = critical_irrigation_due(
            crop, day, state.get("water_since_sowing_mm"), field["sowing_date"]
        )

        decision = make_daily_decision(
            current_depletion=depletion,
            raw=raw,
            future_etc=[],
            future_rain=future_rain if forecast_balances else [],
            rain_probability=probability if forecast_balances else None,
            heat_result=heat_result,
            maximum_depth=maximum_depth,
            forecast_balances=forecast_balances or None,
            critical=critical
        )

        advice.update({
            "depletion_mm": round(depletion, 2),
            "raw_mm": round(raw, 2),
            "taw_mm": round(taw, 2),
            "water_wallet_pct": round(max(0.0, min(100.0, 100 * (1 - depletion / taw))), 1),
            "crossing_day": decision["crossing_day"],
            "critical_stage": critical["name"] if critical else None,
            "water_since_sowing_mm": round(state.get("water_since_sowing_mm") or 0.0, 2),
            "outlook": [
                {
                    "date": dates[index] if dates else None,
                    "day_after_sowing": row["day_after_sowing"],
                    "et0_mm": row["et0_mm"],
                    "rain_mm": row["rain_mm"],
                    "rain_prob": probability[index],
                    "projected_depletion_mm": round(row["depletion_mm"], 1),
                    "raw_mm": round(row["raw_mm"], 1),
                    "taw_mm": round(row["taw_mm"], 1)
                }
                for index, row in enumerate(forecast_balances)
            ]
        })

    advice.update({
        "action": decision["action"],
        "depth_mm": round(decision["depth_mm"], 2),
        "reason_code": decision["reason_code"],
        **calculate_resources(
            decision["depth_mm"],
            field.get("area_acres", 1.0),
            field.get("lift_m", 30.0),
            field.get("pump_eff"),
            electricity_tariff,
            grid_factor
        )
    })

    return advice


# ---------------------------------------------------------------------------
# Catch-up + decision
# ---------------------------------------------------------------------------

def _observed_by_date(observed):
    if not observed:
        return {}

    return {
        day: {
            "et0_mm": observed["et0_mm"][index],
            "rain_mm": observed["rain_mm"][index]
        }
        for index, day in enumerate(observed["date"])
    }


def advance_field(field, state, observed, forecast, events=(), today=None):
    """
    Apply every day from state["last_processed_date"] + 1 up to the day
    before `today` (observed weather + that day's check-ins), then
    decide today's advice.

    Returns {"state", "days" (rows applied), "advice"}. Raises
    MissingWeather if an observed day is missing; the state is not
    changed in that case, so the job can retry with archive data.
    """
    if today is None:
        if forecast and forecast.get("date"):
            today = forecast["date"][0]
        else:
            raise ValueError("Give today or a forecast with dates")

    today = _as_date(today)
    weather = _observed_by_date(observed)
    events_by_date = {}

    for event in events or ():
        events_by_date.setdefault(_as_date(event["date"]).isoformat(), []).append(event)

    sowing = _as_date(field["sowing_date"])
    current = _as_date(state["last_processed_date"]) + timedelta(days=1)
    rows = []
    new_state = dict(state)

    while current < today:
        key = current.isoformat()

        if current < sowing:
            new_state["last_processed_date"] = key
            current += timedelta(days=1)
            continue

        if key not in weather or weather[key]["et0_mm"] is None:
            raise MissingWeather(f"No observed weather for {key}")

        rain, irrigation = apply_checkins(
            weather[key]["rain_mm"] or 0.0,
            events_by_date.get(key, []),
            field["crop"]
        )

        new_state, row = apply_day(field, new_state, current, weather[key]["et0_mm"], rain, irrigation)

        if row is not None:
            rows.append(row)

        current += timedelta(days=1)

    advice = decide_today(field, new_state, forecast, today)

    return {"state": new_state, "days": rows, "advice": advice}
