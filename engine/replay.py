"""
Offline replay (DATA_GUIDE 4.8): run the same weather through the
Boond rules and through the published baseline schedule in
baseline.json, then compare water, kWh, CO2e, irrigations and
stress days. Results are a simulation, not field data.

    python -m engine.replay --weather weather.json --crop wheat --sow 2021-11-05 --soil loam

Pre-sowing irrigation is the same in both runs and is not counted.
"""

import argparse
import json
import math
from datetime import date, timedelta
from pathlib import Path

from engine.data import add_profile_arguments, get_crop, load_json, profile_from_arguments
from engine.paddy import LOW_POND_MM
from engine.simulate import boond_policy, simulate_season


BASELINE_KEYS = {
    "wheat": "wheat",
    "wheat_late": "wheat",
    "wheat_january": "wheat",
    "wheat_fao56": "wheat",
    "paddy": "paddy",
    "paddy_short": "paddy",
    "cotton": "cotton",
    "sugarcane": "sugarcane",
    "sugarcane_ratoon": "sugarcane",
    "sugarcane_autumn": "sugarcane",
}


def _action(depth, reason):
    if depth > 0:
        return {"action": "IRRIGATE", "depth_mm": float(depth), "reason_code": reason}

    return {"action": "WAIT", "depth_mm": 0.0, "reason_code": reason}


def _yesterday_rain(context):
    if context["day"] == 1:
        return 0.0

    return context["weather"]["rain_mm"][context["index"] - 1]


def _season_date(sow_date, month_day):
    """
    Turn "MM-DD" into a date in the season that starts on sow_date.
    """
    month, day = (int(part) for part in month_day.split("-"))
    candidate = date(sow_date.year, month, day)

    return candidate if candidate >= sow_date else date(sow_date.year + 1, month, day)


def wheat_baseline(sow_date):
    """
    PAU Rabi 2025-26 p.17: first irrigation at 3 weeks (October
    sowing) or 4 weeks, later irrigations after the listed weeks,
    and for each cm of rain the next interval is extended by 5 days
    until 31 January and 2 days after that. PAU states the rain
    rule for intervals, so it starts after the first irrigation.
    At most rain_rule.max_rain_credit_mm_per_interval of rain is
    credited per interval (one irrigation's worth), so one very wet
    spell cannot cancel the rest of the schedule.
    """
    plan = load_json("baseline.json")["wheat"]
    first = plan["first_irrigation"]

    month_day = (sow_date.month, sow_date.day)

    if sow_date.month >= 7 and month_day <= (11, 21):
        weeks = plan["later_irrigations_weeks_after_previous"]["sown_up_to_nov_21"]
    elif sow_date.month >= 7 and month_day <= (12, 20):
        weeks = plan["later_irrigations_weeks_after_previous"]["sown_nov_22_to_dec_20"]
    else:
        weeks = plan["later_irrigations_weeks_after_previous"]["sown_dec_21_to_jan_15"]

    sown_after_dec_5 = month_day > (12, 5) or sow_date.month < 7
    stop = _season_date(
        sow_date,
        plan["stop_irrigation"]["sown_after_dec_5" if sown_after_dec_5 else "timely_sown"]
    )
    end_of_january = _season_date(sow_date, "01-31")
    rain_rule = plan["rain_rule"]

    max_credit = rain_rule.get("max_rain_credit_mm_per_interval", math.inf)

    state = {
        "next_due": first["day_if_sown_in_october" if sow_date.month == 10 else "day_if_sown_later"],
        "count": 0,
        "credited_mm": 0.0
    }

    def decide(context):
        if context["day"] > 1 and state["count"] > 0:
            rain_date = context["date"] - timedelta(days=1)
            days_per_cm = (
                rain_rule["delay_days_per_cm_rain_until_jan_31"]
                if rain_date <= end_of_january
                else rain_rule["delay_days_per_cm_rain_after_jan_31"]
            )
            credit = min(_yesterday_rain(context), max_credit - state["credited_mm"])
            state["credited_mm"] += credit
            state["next_due"] += credit / 10 * days_per_cm

        if context["date"] > stop or context["day"] < state["next_due"]:
            return _action(0, "BASELINE_WAIT")

        count = state["count"]
        depth = first["depth_mm"] if count == 0 else plan["later_depth_mm"]
        state["next_due"] = (
            context["day"] + weeks[count] * 7 if count < len(weeks) else math.inf
        )
        state["count"] += 1
        state["credited_mm"] = 0.0

        return _action(depth, "BASELINE_PAU_CALENDAR")

    return decide


def interval_baseline(sow_date, crop_key, crop=None):
    """
    Cotton (CICR/PAU) and sugarcane (PAU/TNAU): first irrigation on
    a fixed day, then a fixed interval. A day with at least
    rain_reset_mm of rain restarts the interval. Irrigation stops
    after last_irrigation_date, or stop_days_before_harvest before
    the end of the `crop` profile's season.
    """
    plan = load_json("baseline.json")[crop_key]

    last_date = (
        _season_date(sow_date, plan["last_irrigation_date"])
        if "last_irrigation_date" in plan
        else date.max
    )

    if "stop_days_before_harvest" in plan:
        season = get_crop(crop or crop_key)["total_days"]
        last_date = min(
            last_date,
            sow_date + timedelta(days=season - plan["stop_days_before_harvest"] - 1)
        )

    def interval(on_date):
        if "interval_days" in plan:
            return plan["interval_days"]

        return plan["interval_days_by_month"][f"{on_date.month:02d}"]

    state = {"next_due": plan["first_irrigation_day"]}

    def decide(context):
        if _yesterday_rain(context) >= plan["rain_reset_mm"]:
            state["next_due"] = max(
                state["next_due"],
                context["day"] - 1 + interval(context["date"])
            )

        if context["date"] > last_date or context["day"] < state["next_due"]:
            return _action(0, "BASELINE_WAIT")

        state["next_due"] = context["day"] + interval(context["date"])

        return _action(plan["depth_mm"], "BASELINE_INTERVAL")

    return decide


def paddy_baseline(crop):
    """
    PAU Kharif 2026 p.12 without a forecast: standing water for
    two weeks, then irrigation_depth_mm two days after the pond
    has gone, stopping stop_days_before_maturity before harvest.
    """
    plan = load_json("baseline.json")["paddy"]
    water = get_crop(crop)["paddy_water"]
    stop_day = get_crop(crop)["total_days"] - plan["stop_days_before_maturity"]

    def decide(context):
        state = context["state"]

        if context["day"] > stop_day:
            return _action(0, "BASELINE_STOPPED")

        if context["day"] <= plan["continuous_ponding_days"]:
            if state["pond_mm"] < LOW_POND_MM:
                return _action(plan["irrigation_depth_mm"], "BASELINE_KEEP_POND")

            return _action(0, "BASELINE_WAIT")

        if state["dry_days"] >= water["irrigate_days_after_pond_disappears"]:
            return _action(plan["irrigation_depth_mm"], "BASELINE_POND_GONE")

        return _action(0, "BASELINE_WAIT")

    return decide


def baseline_policy(crop, sow_date):
    key = BASELINE_KEYS[crop]

    if key == "wheat":
        return wheat_baseline(sow_date)

    if key == "paddy":
        return paddy_baseline(crop)

    return interval_baseline(sow_date, key, crop)


def replay(weather, crop, sow_date, soil, rain_probability=None, forecast=None):
    """
    rain_probability=None: forecast rain is not trusted unless the
    forecast file carries rain_prob. 1.0 = perfect rain forecast
    (sensitivity run only; label it).
    """
    if forecast is not None:
        actual, predicted = weather["daily"], forecast["daily"]

        if all(
            actual[key] == predicted.get(key)
            for key in ("date", "et0_mm", "rain_mm", "tmax_c")
        ):
            raise ValueError(
                "The forecast file is identical to the weather file, so it is not "
                "an archived forecast. Fetch it with --source historical-forecast, "
                "or run without --forecast and say that observed weather stood in "
                "for the forecast."
            )

    boond = simulate_season(
        weather, sow_date, soil, crop=crop,
        policy=boond_policy(rain_probability, forecast=forecast)
    )
    baseline = simulate_season(
        weather, sow_date, soil, crop=crop,
        policy=baseline_policy(crop, sow_date)
    )

    comparison = {
        key: round(boond["summary"][key] - baseline["summary"][key], 1)
        for key in ("irrigation_mm", "irrigation_events", "pump_kwh", "co2_kg", "stress_days")
    }

    return {
        "label": "SIMULATION: same weather through Boond and the published baseline",
        "baseline_source": load_json("baseline.json")[BASELINE_KEYS[crop]]["source"],
        "boond_rain_probability": rain_probability,
        "boond_forecast": (
            forecast.get("source", "forecast file") if forecast
            else "actual weather used as forecast (perfect foresight)"
        ),
        "boond": boond["summary"],
        "baseline": baseline["summary"],
        "boond_minus_baseline": comparison,
        "boond_days": boond["days"],
        "baseline_days": baseline["days"]
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--weather", required=True)
    add_profile_arguments(parser)
    parser.add_argument("--sow", required=True, type=date.fromisoformat)
    parser.add_argument("--soil", default="loam")
    parser.add_argument("--rain-probability", type=float, default=None,
                        help="trust forecast rain at this probability (default: not trusted)")
    parser.add_argument("--forecast", help="archived forecast file (historical-forecast)")
    parser.add_argument("--out-dir", default="replay/out")
    args = parser.parse_args(argv)
    crop = profile_from_arguments(args)

    with open(args.weather, "r") as file:
        weather = json.load(file)

    forecast = None

    if args.forecast:
        with open(args.forecast, "r") as file:
            forecast = json.load(file)

    result = replay(weather, crop, args.sow, args.soil, args.rain_probability, forecast)
    result["profile"] = crop

    out = Path(args.out_dir) / f"replay_{crop}_{args.soil}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))

    print(json.dumps(
        {key: result[key] for key in (
            "profile", "boond_rain_probability", "boond_forecast",
            "boond", "baseline", "boond_minus_baseline"
        )},
        indent=2
    ))
    print(f"Saved {out}")

    return result


if __name__ == "__main__":
    main()
