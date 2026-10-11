"""
Check crops.json, soils.json, config.json and baseline.json, and
print Kc and TAW/RAW tables (DATA_GUIDE 4.9).

    python -m engine.check_data
    python -m engine.check_data --tables
    python -m engine.check_data --weather weather.json --crop wheat --sow 2021-11-05

With --weather it also prints the stress-free seasonal ETc and
compares it with the crop's validation_targets.
"""

import argparse
import json
import sys
from datetime import date

from engine.data import CROP_FAMILIES, entries, load_config, load_json, select_profile
from engine.kc import STAGES, get_kc, get_season_length
from engine.season_rules import WINDOW_KEYS, month_day


PADDY_WATER_KEYS = (
    "continuous_ponding_days",
    "irrigate_days_after_pond_disappears",
    "target_pond_mm",
    "bund_storage_mm",
    "stop_irrigation_day",
)


def _bad_month_day(value):
    try:
        month_day(value)
    except (AttributeError, TypeError, ValueError):
        return True

    return False


def check_calendar_rules(name, crop, season_length, heat_window_days):
    """Sowing windows, stop_irrigation and heat_consecutive_days."""
    problems = []
    windows = [key for key, _ in WINDOW_KEYS if crop.get(key)]

    if len(windows) > 1:
        problems.append(f"crops.{name}: give only one of {', '.join(windows)}")

    for key in windows:
        for end in ("start", "end"):
            if _bad_month_day(crop[key].get(end)):
                problems.append(f"crops.{name}: {key}.{end} must be a real MM-DD date")

    stop = crop.get("stop_irrigation")

    if stop is not None:
        if not {"last_irrigation_date", "days_before_harvest"} & set(stop):
            problems.append(f"crops.{name}: stop_irrigation needs last_irrigation_date or days_before_harvest")

        if "last_irrigation_date" in stop and _bad_month_day(stop["last_irrigation_date"]):
            problems.append(f"crops.{name}: stop_irrigation.last_irrigation_date must be MM-DD")

        later = stop.get("if_sown_after")

        if later is not None and (
            _bad_month_day(later.get("date")) or _bad_month_day(later.get("last_irrigation_date"))
        ):
            problems.append(f"crops.{name}: stop_irrigation.if_sown_after needs MM-DD date and last_irrigation_date")

        days = stop.get("days_before_harvest")

        if days is not None and not (isinstance(days, int) and 0 < days < season_length):
            problems.append(f"crops.{name}: stop_irrigation.days_before_harvest must be within the season")

    consecutive = crop.get("heat_consecutive_days")

    if consecutive is not None and not (isinstance(consecutive, int) and 1 <= consecutive <= heat_window_days):
        problems.append(
            f"crops.{name}: heat_consecutive_days must be 1..heat.forecast_window_days ({heat_window_days})"
        )

    return problems


def check_profile_selection(crops):
    """Every sowing date of the year picks an existing profile."""
    problems = []
    names = set(entries(crops))

    for family in CROP_FAMILIES:
        for month in range(1, 13):
            for day in (1, 15, 28):
                for ratoon in (False, True):
                    profile = select_profile(family, date(2021, month, day), ratoon=ratoon)

                    if profile not in names:
                        problems.append(f"select_profile({family}, {month:02d}-{day:02d}) -> unknown {profile}")

    return sorted(set(problems))


def check_crops(crops, heat_window_days=3):
    problems = []

    for name, crop in entries(crops).items():
        stages = crop.get("stages", {})
        season_length = 0
        previous_kc_end = None

        for stage in STAGES:
            values = stages.get(stage, {})
            days = values.get("days")

            if not isinstance(days, int) or days < 1:
                problems.append(f"crops.{name}: stages.{stage}.days must be a positive integer")
                continue

            season_length += days

            for key in ("kc_start", "kc_end"):
                if not 0 < values.get(key, -1) <= 2:
                    problems.append(f"crops.{name}: stages.{stage}.{key} must be in (0, 2]")

            if stage in ("initial", "mid") and values.get("kc_start") != values.get("kc_end"):
                problems.append(f"crops.{name}: Kc must be constant in the {stage} stage")

            if previous_kc_end is not None and values.get("kc_start") != previous_kc_end:
                problems.append(f"crops.{name}: Kc jumps at the start of the {stage} stage")

            previous_kc_end = values.get("kc_end")

        if crop.get("total_days") != season_length:
            problems.append(f"crops.{name}: total_days {crop.get('total_days')} != sum of stages {season_length}")

        if not 0.1 <= crop.get("depletion_fraction", -1) <= 0.8:
            problems.append(f"crops.{name}: depletion_fraction must be in [0.1, 0.8]")

        for stage, value in (crop.get("depletion_fraction_by_stage") or {}).items():
            if stage not in STAGES or not 0.1 <= value <= 0.8:
                problems.append(f"crops.{name}: bad depletion_fraction_by_stage.{stage}")

        roots = crop.get("root_depth", {})

        if not 0 < roots.get("initial_m", 0) <= roots.get("maximum_m", 0):
            problems.append(f"crops.{name}: need 0 < root_depth.initial_m <= maximum_m")

        if not 1 < roots.get("full_depth_day", 0) <= season_length:
            problems.append(f"crops.{name}: root_depth.full_depth_day must fall within the season")

        thresholds = crop.get("heat_thresholds", {})

        for window in crop.get("heat_windows", []):
            label = f"crops.{name}: heat window {window.get('name')}"

            if not 1 <= window.get("day_start", 0) <= window.get("day_end", 0) <= season_length:
                problems.append(f"{label} must lie within the season")

            if "tmax_threshold_c" not in window:
                problems.append(f"{label} has no tmax_threshold_c")
            elif thresholds.get(window.get("name")) != window["tmax_threshold_c"]:
                problems.append(f"{label} threshold differs from heat_thresholds")

        irrigation = crop.get("irrigation", {})

        if set(irrigation.get("checkin_depth_mm", {})) != {"light", "normal", "heavy"}:
            problems.append(f"crops.{name}: irrigation.checkin_depth_mm needs light/normal/heavy")

        problems += check_calendar_rules(name, crop, season_length, heat_window_days)

        if crop.get("crop_family") == "paddy":
            water = crop.get("paddy_water", {})

            for key in PADDY_WATER_KEYS:
                if key not in water:
                    problems.append(f"crops.{name}: paddy_water.{key} is missing")

            if water.get("stop_irrigation_day", 0) > season_length:
                problems.append(f"crops.{name}: paddy_water.stop_irrigation_day is after harvest")

        elif crop.get("crop_family") != "upland":
            problems.append(f"crops.{name}: crop_family must be upland or paddy")

    return problems


def check_soils(soils):
    problems = []

    for name, soil in entries(soils).items():
        fc = soil.get("theta_fc", 0)
        wp = soil.get("theta_wp", 0)

        if not 0 < wp < fc < 1:
            problems.append(f"soils.{name}: need 0 < theta_wp < theta_fc < 1")

        if abs(1000 * (fc - wp) - soil.get("taw_per_m_mm", -100)) > 0.5:
            problems.append(f"soils.{name}: taw_per_m_mm does not equal 1000 x (theta_fc - theta_wp)")

        if soil.get("paddy_percolation_mm_per_day", -1) < 0:
            problems.append(f"soils.{name}: paddy_percolation_mm_per_day is missing")

        target = soil.get("maps_to_farmer_choice")

        if target is not None and not soils.get(target, {}).get("farmer_choice"):
            problems.append(f"soils.{name}: maps_to_farmer_choice {target} is not a farmer choice")

    if len([soil for soil in entries(soils).values() if soil.get("farmer_choice")]) != 3:
        problems.append("soils: the form expects exactly three farmer_choice soils")

    return problems


def check_config(config):
    problems = []

    if not 0 < config["rain"]["skip_probability_threshold"] <= 1:
        problems.append("config: rain.skip_probability_threshold must be in (0, 1]")

    if not 0 < config["rain"]["forecast_rain_discount"] <= 1:
        problems.append("config: rain.forecast_rain_discount must be in (0, 1]")

    irrigation = config["irrigation"]

    if not irrigation["minimum_advised_depth_mm"] <= irrigation["maximum_depth_mm"]:
        problems.append("config: irrigation.minimum_advised_depth_mm exceeds maximum_depth_mm")

    if irrigation["light_depth_mm"] > irrigation["maximum_depth_mm"]:
        problems.append("config: irrigation.light_depth_mm exceeds maximum_depth_mm")

    if not 0 < irrigation["application_efficiency"] <= 1:
        problems.append("config: irrigation.application_efficiency must be in (0, 1]")

    if config["advisor"]["irrigate_within_days"] > config["advisor"]["rain_skip_window_days"]:
        problems.append("config: advisor.irrigate_within_days exceeds rain_skip_window_days")

    if config.get("kc_climate_adjustment", {}).get("enabled"):
        problems.append(
            "config: kc_climate_adjustment.enabled is true, but the engine does not "
            "implement it (it needs daily RHmin and mean wind inputs); keep it false"
        )

    return problems


def check_baseline(baseline, crops):
    from engine.replay import BASELINE_KEYS

    problems = []

    for name in ("wheat", "paddy", "cotton", "sugarcane"):
        if name not in baseline:
            problems.append(f"baseline: no schedule for {name}")
        elif name not in crops:
            problems.append(f"baseline: {name} is not a crop in crops.json")

    for name in entries(crops):
        if BASELINE_KEYS.get(name) not in baseline:
            problems.append(f"replay.BASELINE_KEYS: no baseline schedule for profile {name}")

    return problems


def validate():
    crops = load_json("crops.json")
    config = load_config()

    return (
        check_crops(crops, config["heat"]["forecast_window_days"])
        + check_profile_selection(crops)
        + check_soils(load_json("soils.json"))
        + check_config(load_config())
        + check_baseline(load_json("baseline.json"), crops)
    )


def print_tables():
    crops = entries(load_json("crops.json"))
    soils = entries(load_json("soils.json"))

    print("\nKc on selected days")

    for name in crops:
        length = get_season_length(name)
        days = sorted({1, length // 6, length // 2, length})
        print(f"  {name:17}" + "  ".join(f"d{day}={get_kc(day, name):.3f}" for day in days))

    print("\nTAW / RAW (mm) at full root depth, p unadjusted")

    for name, crop in crops.items():
        depth = crop["root_depth"]["maximum_m"]
        p = crop["depletion_fraction"]
        cells = [
            f"{soil}={soil_data['taw_per_m_mm'] * depth:.0f}/{soil_data['taw_per_m_mm'] * depth * p:.0f}"
            for soil, soil_data in soils.items()
            if soil_data.get("farmer_choice")
        ]
        print(f"  {name:17}" + "  ".join(cells))


def seasonal_etc(weather, crop, sow_date):
    """
    Stress-free seasonal ETc = sum of Kc x ET0 over the season.
    """
    daily = weather["daily"]
    first = daily["date"].index(sow_date.isoformat())
    length = get_season_length(crop)

    if first + length > len(daily["date"]):
        raise ValueError("Weather does not cover the whole season")

    return sum(
        get_kc(day, crop) * daily["et0_mm"][first + day - 1]
        for day in range(1, length + 1)
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--tables", action="store_true")
    parser.add_argument("--weather")
    parser.add_argument("--crop", default="wheat")
    parser.add_argument("--sow", type=date.fromisoformat)
    args = parser.parse_args()

    problems = validate()

    for problem in problems:
        print(problem)

    print("Data OK" if not problems else f"{len(problems)} problem(s) found")

    if args.tables:
        print_tables()

    if args.weather:
        with open(args.weather, "r") as file:
            weather = json.load(file)

        etc = seasonal_etc(weather, args.crop, args.sow)
        low, high = load_json("crops.json")[args.crop].get(
            "validation_targets", {}
        ).get("seasonal_etc_mm", [None, None])

        verdict = "no target" if low is None else ("inside" if low <= etc <= high else "OUTSIDE")
        print(f"\nStress-free seasonal ETc for {args.crop} sown {args.sow}: {etc:.0f} mm ({verdict} target {low}-{high})")

    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
