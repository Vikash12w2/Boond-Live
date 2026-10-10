"""
Season simulator: run an irrigation policy over a whole season of
daily weather.

    python -m engine.simulate --weather weather.json --sow 2021-11-10 --soil loam --crop wheat

Each morning the policy decides from yesterday's ending state.
Any irrigation is applied that day, then the day's balance is
computed with the actual weather.

Forecast seen by the Boond policy:
  * with --forecast FILE: the archived forecast in FILE (from
    tools/fetch_weather.py --source historical-forecast), using its
    own rain_prob values when present;
  * otherwise the next forecast_days of the actual weather
    (perfect foresight). Rain then counts for SKIP only if you pass
    --rain-probability; by default (None) forecast rain is NOT
    trusted, so savings are not overstated. Always report the
    setting used.

Weather files are the JSON written by tools/fetch_weather.py:
    {"daily": {"date": [...], "et0_mm": [...], "rain_mm": [...],
               "tmax_c": [...], "rain_prob": [...] (optional, 0-1)}}
"""

import argparse
import json
from datetime import date

from engine.data import is_paddy
from engine.field_runner import (
    apply_day,
    calculate_resources,
    decide_today,
    start_state,
    starting_depletion
)
from engine.kc import get_season_length


__all__ = ["boond_policy", "simulate_season", "starting_depletion"]


def _forecast_window(context, forecast_days, forecast, rain_probability):
    """
    The forecast that starts today, in the field_runner layout. From
    the archived forecast file when given (matched by date), otherwise
    from the actual weather (perfect foresight).
    """
    if forecast is None:
        daily = context["weather"]
        start = context["index"]
    else:
        daily = forecast["daily"]
        today = context["date"].isoformat()

        if today not in daily["date"]:
            raise ValueError(f"Forecast file has no row for {today}")

        start = daily["date"].index(today)

    window = slice(start, min(start + forecast_days, len(daily["date"])))
    et0 = daily["et0_mm"][window]

    if rain_probability is None and "rain_prob" in daily:
        probability = daily["rain_prob"][window]
    else:
        probability = [rain_probability] * len(et0)

    return {
        "date": daily["date"][window],
        "et0_mm": et0,
        "rain_mm": daily["rain_mm"][window],
        "tmax_c": daily["tmax_c"][window],
        "rain_prob": probability
    }


def boond_policy(rain_probability=None, forecast_days=16, forecast=None):
    """
    The Boond advisor as a simulation policy: exactly
    engine.field_runner.decide_today, the function the live daily
    job uses, with the same 16-day forecast length as Open-Meteo.

    rain_probability=None means forecast rain is not trusted (unless
    the forecast file carries its own rain_prob). Pass 1.0 only for
    a labelled "perfect rain forecast" sensitivity run.
    """

    def decide(context):
        return decide_today(
            context["field"],
            context["field_state"],
            _forecast_window(context, forecast_days, forecast, rain_probability),
            context["date"]
        )

    return decide


def simulate_season(
    weather,
    sow_date,
    soil,
    crop="wheat",
    policy=None,
    area_acres=1.0,
    lift_m=30.0,
    pump_efficiency=None
):
    """
    Run `policy` over one season, applying each day with
    field_runner.apply_day (the same path as the live daily job).

    policy(context) returns {"action", "depth_mm", "reason_code"}.
    context has field and field_state (the field_runner state at the
    end of yesterday), weather, index (today's row), day, date,
    sow_date, crop, soil, paddy, state (yesterday's depletion for
    upland crops, the pond state for paddy) and water_since_sowing_mm.
    """
    daily = weather["daily"]
    dates = [date.fromisoformat(value) for value in daily["date"]]

    if sow_date not in dates:
        raise ValueError(f"Weather does not include the sowing date {sow_date}")

    first = dates.index(sow_date)
    season_length = get_season_length(crop)

    if first + season_length > len(dates):
        raise ValueError("Weather does not cover the whole season")

    if policy is None:
        policy = boond_policy()

    paddy = is_paddy(crop)
    field = {
        "crop": crop,
        "soil": soil,
        "sowing_date": sow_date.isoformat(),
        "area_acres": area_acres,
        "lift_m": lift_m,
        "pump_eff": pump_efficiency
    }
    state = start_state(field, et0=daily["et0_mm"][first])

    days = []
    seasonal_etc = 0.0

    stress_days = 0

    for day in range(1, season_length + 1):
        today = first + day - 1

        decision = policy({
            "field": field,
            "field_state": state,
            "weather": daily,
            "index": today,
            "day": day,
            "date": dates[today],
            "sow_date": sow_date,
            "crop": crop,
            "soil": soil,
            "paddy": paddy,
            "state": state if paddy else state["depletion_mm"],
            "water_since_sowing_mm": state["water_since_sowing_mm"]
        })

        irrigation = decision["depth_mm"]

        state, row = apply_day(
            field,
            state,
            dates[today],
            daily["et0_mm"][today],
            daily["rain_mm"][today],
            irrigation
        )

        seasonal_etc += row["actual_etc_mm"]

        if row["ks"] < 1.0:
            stress_days += 1
            
        days.append({
            "date": daily["date"][today],
            "day": day,
            "action": decision["action"],
            "reason_code": decision["reason_code"],
            "irrigation_mm": round(irrigation, 2),
            "rain_mm": daily["rain_mm"][today],
            "depletion_mm": round(row["depletion_mm"], 2),
            "ks": round(row["ks"], 6),
            "losses_mm": round(row["losses_mm"], 2),
            **({"pond_mm": round(row["pond_mm"], 2)} if paddy else {})
        })

    irrigation_mm = sum(row["irrigation_mm"] for row in days)
    resources = calculate_resources(irrigation_mm, area_acres, lift_m, pump_efficiency)

    summary = {
        "crop": crop,
        "soil": soil,
        "sow_date": sow_date.isoformat(),
        "irrigation_events": sum(1 for row in days if row["irrigation_mm"] > 0),
        "irrigation_mm": round(irrigation_mm, 1),
        "gross_pumped_mm": resources["gross_depth_mm"],
        "pump_kwh": round(resources["kwh"], 1),
        "co2_kg": round(resources["co2_kg"], 1),
        "stress_days": stress_days,
        "seasonal_etc_mm": round(seasonal_etc, 1),
        "rain_mm": round(sum(row["rain_mm"] for row in days), 1),
        "drainage_mm": round(sum(row["losses_mm"] for row in days), 1)
    }

    return {"summary": summary, "days": days}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--weather", required=True)
    parser.add_argument("--sow", required=True, type=date.fromisoformat)
    parser.add_argument("--soil", default="loam")
    parser.add_argument("--crop", default="wheat")
    parser.add_argument("--forecast-days", type=int, default=16)
    parser.add_argument("--rain-probability", type=float, default=None,
                        help="trust forecast rain at this probability (default: not trusted)")
    parser.add_argument("--forecast", help="archived forecast file (historical-forecast)")
    parser.add_argument("--out")
    args = parser.parse_args()

    with open(args.weather, "r") as file:
        weather = json.load(file)

    forecast = None

    if args.forecast:
        with open(args.forecast, "r") as file:
            forecast = json.load(file)

    result = simulate_season(
        weather,
        args.sow,
        args.soil,
        crop=args.crop,
        policy=boond_policy(args.rain_probability, args.forecast_days, forecast)
    )

    print(json.dumps(result["summary"], indent=2))

    if args.out:
        with open(args.out, "w") as file:
            json.dump(result, file, indent=2)


if __name__ == "__main__":
    main()
