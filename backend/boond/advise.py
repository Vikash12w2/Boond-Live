"""One field, one day: recompute the season from sowing with every check-in.

No engine state is stored. The whole season (at most ~145 days) is replayed on
every run, so a check-in for any past day is always applied and runs are
idempotent.
"""
from datetime import date

from engine.data import select_profile
from engine.field_runner import advance_field, start_state
from engine.heat_rules import get_heat_windows_for_day


def engine_field(profile):
    return {
        "crop": select_profile(profile["crop"], profile["sowing_date"]),
        "soil": profile["soil"],
        "sowing_date": profile["sowing_date"],
        "area_acres": profile["area_acres"],
        "lift_m": profile["lift_m"],
        "pump_eff": profile.get("pump_eff"),
    }


def run_field(profile, events, weather, today: date):
    field = engine_field(profile)
    result = advance_field(field, start_state(field), weather["observed"], weather["forecast"], events, today)
    advice = result["advice"]
    # The engine's outlook has no daily temperature or threshold; the dashboard draws heat markers
    # from them. The threshold is the engine's own heat window for that crop day (first window, as
    # engine.heat_rules.get_heat_stage picks it).
    tmax = dict(zip(weather["forecast"]["date"], weather["forecast"]["tmax_c"]))
    for row in advice.get("outlook") or []:
        row["tmax_c"] = tmax.get(row.get("date"))
        windows = get_heat_windows_for_day(row["day_after_sowing"], field["crop"]) if "day_after_sowing" in row else []
        row["heat_threshold_c"] = windows[0]["tmax_threshold_c"] if windows else None
    return advice
