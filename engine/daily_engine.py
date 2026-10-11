"""
One-call wrappers around engine.field_runner for a single day.

The live daily job should use field_runner.advance_field (it stores a
state and catches up missed days). These wrappers keep the original
Boond_1 interface: apply one day (YESTERDAY), then decide today's
advice, through the same apply_day / decide_today functions, so they
can never disagree with the replay.
"""

from datetime import date, timedelta

from engine.field_runner import (
    apply_day,
    calculate_resources,
    decide_today
)
from engine.kc import get_stage


__all__ = [
    "calculate_resources",
    "generate_daily_decision",
    "generate_daily_decision_paddy"
]

# Used only to turn crop days into dates when the caller has no
# sowing date (the result does not depend on it, except the wheat
# CRI window, which then assumes a November sowing).
_NO_SOWING_DATE = date(2001, 11, 1)


def _forecast(first_date, future_et0, future_rain, forecast_tmax, rain_probability):
    days = len(future_et0)

    if len(future_rain) != days:
        raise ValueError("future_et0 and future_rain must have equal lengths")

    if rain_probability is None or isinstance(rain_probability, (int, float)):
        probability = [rain_probability] * days
    else:
        probability = list(rain_probability)

        if len(probability) != days:
            raise ValueError("rain_probability must have one value per forecast day")

    tmax = list(forecast_tmax or [])[:days]
    tmax += [None] * (days - len(tmax))

    return {
        "date": [(first_date + timedelta(days=i)).isoformat() for i in range(days)],
        "et0_mm": list(future_et0),
        "rain_mm": list(future_rain),
        "tmax_c": tmax,
        "rain_prob": probability
    }


def _field(crop, soil, sowing_date, area_acres, lift_m, pump_efficiency):
    sowing = date.fromisoformat(sowing_date) if isinstance(sowing_date, str) else sowing_date

    return {
        "crop": crop,
        "soil": soil,
        "sowing_date": (sowing or _NO_SOWING_DATE).isoformat(),
        # Without a real date only crop-day rules apply (no sowing-window
        # warning, no calendar last-irrigation date).
        "sowing_date_known": sowing is not None,
        "area_acres": area_acres,
        "lift_m": lift_m,
        "pump_eff": pump_efficiency
    }


def generate_daily_decision(
    day_after_sowing,
    soil,
    et0,
    rain,
    irrigation,
    previous_depletion,
    future_et0,
    future_rain,
    rain_probability,
    forecast_tmax,
    area_acres,
    lift_m,
    pump_efficiency=None,
    electricity_tariff=None,
    grid_factor=None,
    maximum_irrigation_depth=None,
    crop="wheat",
    water_since_sowing_mm=None,
    sowing_date=None
):
    """
    Apply day_after_sowing (YESTERDAY in the 06:00 job: observed et0,
    rain and the farmer's WATERED mm), then return TODAY's advice.

    future_et0, future_rain, forecast_tmax and a per-day
    rain_probability list start today (day_after_sowing + 1).

    water_since_sowing_mm is the effective rain + irrigation that
    reached the field before day_after_sowing (0 on the sowing date);
    with sowing_date it enables the wheat CRI irrigation. If it is
    None that rule is skipped. The returned water_since_sowing_mm is
    stored for the next call.

    Fields describing the applied day (kc, et0_mm, etc_mm, ks,
    depletion_mm, raw_mm, taw_mm, stage) refer to day_after_sowing;
    action, depth_mm, reason_code and the outlook are today's advice.
    """
    field = _field(crop, soil, sowing_date, area_acres, lift_m, pump_efficiency)
    applied_date = date.fromisoformat(field["sowing_date"]) + timedelta(days=day_after_sowing - 1)

    state = {
        "last_processed_date": (applied_date - timedelta(days=1)).isoformat(),
        "depletion_mm": previous_depletion,
        "water_since_sowing_mm": water_since_sowing_mm
    }

    if water_since_sowing_mm is None:
        # Track nothing: the CRI rule is skipped.
        state["water_since_sowing_mm"] = 0.0

    state, row = apply_day(field, state, applied_date, et0, rain, irrigation)

    if water_since_sowing_mm is None:
        state["water_since_sowing_mm"] = None

    advice = decide_today(
        field,
        state,
        _forecast(applied_date + timedelta(days=1), future_et0, future_rain,
                  forecast_tmax, rain_probability),
        applied_date + timedelta(days=1),
        maximum_depth=maximum_irrigation_depth,
        electricity_tariff=electricity_tariff,
        grid_factor=grid_factor
    )

    taw = row["taw_mm"]

    return {
        **advice,
        "day_after_sowing": day_after_sowing,
        "stage": get_stage(day_after_sowing, crop),
        "rain_probability": rain_probability,
        "kc": round(row["kc"], 3),
        "et0_mm": round(row["et0_mm"], 2),
        "etc_mm": round(row["actual_etc_mm"], 2),
        "depletion_mm": round(row["depletion_mm"], 2),
        "raw_mm": round(row["raw_mm"], 2),
        "taw_mm": round(taw, 2),
        "ks": round(row["ks"], 3),
        "water_wallet_pct": round(max(0.0, min(100.0, 100 * (1 - row["depletion_mm"] / taw))), 1),
        "water_since_sowing_mm": (
            None if water_since_sowing_mm is None
            else round(state["water_since_sowing_mm"], 2)
        )
    }


def generate_daily_decision_paddy(
    day_after_transplanting,
    soil,
    et0,
    rain,
    irrigation,
    state,
    future_rain,
    rain_probability,
    forecast_tmax,
    area_acres,
    lift_m,
    pump_efficiency=None,
    electricity_tariff=None,
    grid_factor=None,
    crop="paddy"
):
    """
    Paddy: apply day_after_transplanting (yesterday) to state =
    {"pond_mm", "depletion_mm", "dry_days"}, then decide today's
    advice with the PAU rule. The returned "state" is stored for the
    next call.
    """
    field = _field(crop, soil, None, area_acres, lift_m, pump_efficiency)
    applied_date = date.fromisoformat(field["sowing_date"]) + timedelta(days=day_after_transplanting - 1)

    field_state = {
        "last_processed_date": (applied_date - timedelta(days=1)).isoformat(),
        "water_since_sowing_mm": 0.0,
        **state
    }

    field_state, row = apply_day(field, field_state, applied_date, et0, rain, irrigation)

    future_et0 = [0.0] * len(future_rain)  # paddy decisions do not use ET0 forecasts
    advice = decide_today(
        field,
        field_state,
        _forecast(applied_date + timedelta(days=1), future_et0, future_rain,
                  forecast_tmax, rain_probability),
        applied_date + timedelta(days=1),
        electricity_tariff=electricity_tariff,
        grid_factor=grid_factor
    )

    new_state = {key: field_state[key] for key in ("pond_mm", "depletion_mm", "dry_days")}

    return {
        **advice,
        "day_after_transplanting": day_after_transplanting,
        "stage": get_stage(day_after_transplanting, crop),
        "pond_mm": round(new_state["pond_mm"], 2),
        "depletion_mm": round(new_state["depletion_mm"], 2),
        "dry_days": new_state["dry_days"],
        "kc": round(row["kc"], 3),
        "etc_mm": round(row["actual_etc_mm"], 2),
        "percolation_mm": round(row["percolation_mm"], 2),
        "state": new_state
    }
