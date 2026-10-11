"""
Crop parity: sowing-window warnings, the last irrigation before
harvest, the new wheat_january and sugarcane_autumn profiles, and the
per-crop number of consecutive hot days.
"""

import copy
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from engine.check_data import check_crops, validate
from engine.daily_engine import generate_daily_decision
from engine.data import entries, get_crop, load_json, select_profile
from engine.field_runner import advance_field, decide_today, sowing_warnings, start_state
from engine.heat_rules import assess_heat_risk, consecutive_hot_days_required
from engine.kc import get_season_length
from engine.messages import allowed_numbers, numbers_in, render, render_warnings
from engine.season_rules import (
    check_sowing_window,
    irrigation_stopped,
    last_irrigation,
    window_position
)


CACHE = Path(__file__).resolve().parents[2] / "replay" / "cache" / "ludhiana_actual_2021_22.json"


def field(crop, sowing, soil="loam"):
    return {
        "crop": crop,
        "soil": soil,
        "sowing_date": sowing.isoformat(),
        "area_acres": 1.0,
        "lift_m": 30.0,
        "pump_eff": 0.4
    }


def forecast(today, days=16, et0=5.0, tmax=30.0):
    tmax_values = tmax if isinstance(tmax, list) else [tmax] * days
    tmax_values = (tmax_values + [30.0] * days)[:days]

    return {
        "date": [(today + timedelta(days=i)).isoformat() for i in range(days)],
        "et0_mm": [et0] * days,
        "rain_mm": [0.0] * days,
        "tmax_c": tmax_values,
        "rain_prob": [None] * days
    }


def state_on(field_, today, depletion):
    return dict(
        start_state(field_),
        depletion_mm=depletion,
        water_since_sowing_mm=200.0,
        last_processed_date=(today - timedelta(days=1)).isoformat()
    )


# ---------------------------------------------------------------------------
# Sowing windows
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("crop, sowing, position, days", [
    ("wheat", date(2021, 11, 5), "INSIDE", 0),
    ("wheat", date(2021, 10, 15), "EARLY", 7),
    ("wheat_late", date(2021, 12, 28), "LATE", 8),
    ("wheat_january", date(2022, 1, 25), "LATE", 10),
    ("paddy", date(2021, 6, 10), "EARLY", 10),
    ("paddy_short", date(2021, 7, 15), "INSIDE", 0),
    ("cotton", date(2021, 5, 31), "LATE", 16),
    ("sugarcane", date(2021, 3, 1), "INSIDE", 0),
    ("sugarcane_autumn", date(2021, 11, 10), "LATE", 10),
])
def test_check_sowing_window(crop, sowing, position, days):
    check = check_sowing_window(crop, sowing)

    assert (check["position"], check["days_outside"]) == (position, days)
    assert (check["warning"] is None) == (position == "INSIDE")


def test_window_over_the_new_year():
    assert window_position(date(2022, 1, 5), "12-15", "01-10")[:2] == ("INSIDE", 0)
    assert window_position(date(2021, 12, 20), "12-15", "01-10")[:2] == ("INSIDE", 0)
    assert window_position(date(2022, 1, 20), "12-15", "01-10")[:2] == ("LATE", 10)
    assert window_position(date(2021, 12, 1), "12-15", "01-10")[:2] == ("EARLY", 14)


def test_profiles_without_a_window_give_no_check():
    assert check_sowing_window("wheat_fao56", date(2021, 11, 5)) is None
    assert check_sowing_window("sugarcane_ratoon", date(2021, 3, 1)) is None


def test_every_sowing_date_maps_to_a_profile_whose_window_is_close():
    # Registration picks the profile from the date; the date should then be
    # inside that profile's window or close to it (one month at most for
    # the families with seasonal profiles, outside the off-season).
    for sowing, crop in (
        (date(2021, 11, 10), "wheat"),
        (date(2021, 12, 10), "wheat_late"),
        (date(2022, 1, 10), "wheat_january"),
        (date(2021, 3, 10), "sugarcane"),
        (date(2021, 10, 10), "sugarcane_autumn"),
    ):
        profile = select_profile(crop.split("_")[0], sowing)
        assert profile == crop
        assert check_sowing_window(profile, sowing)["position"] == "INSIDE"


def test_warning_is_part_of_every_advice():
    sowing = date(2021, 12, 28)
    wheat = field("wheat_late", sowing)

    waiting = decide_today(wheat, start_state(wheat), None, sowing - timedelta(days=2))
    active = decide_today(wheat, start_state(wheat), forecast(sowing), sowing)

    for advice in (waiting, active):
        assert advice["warnings"] == [{
            "code": "SOWN_AFTER_WINDOW",
            "kind": "sowing",
            "days_outside": 8,
            "window_start": "2021-11-22",
            "window_end": "2021-12-20"
        }]

    assert sowing_warnings(field("wheat", date(2021, 11, 5))) == []


def test_warning_messages_in_both_languages():
    advice = {"warnings": sowing_warnings(field("paddy", date(2021, 7, 20)))}

    assert render_warnings(advice, "en") == [
        "Note: transplanting was 10 days after the recommended window (20 Jun – 10 Jul). "
        "Yield may be lower; the irrigation advice still follows the crop's water need."
    ]
    assert render_warnings(advice, "hi") == [
        "ध्यान दें: रोपाई अनुशंसित समय (20 जून – 10 जुलाई) से 10 दिन बाद हुई। "
        "पैदावार कम हो सकती है; सिंचाई की सलाह फिर भी फसल की पानी की ज़रूरत के अनुसार दी जाएगी।"
    ]
    assert numbers_in(" ".join(render_warnings(advice, "hi"))) <= allowed_numbers(advice)
    assert render_warnings({"warnings": []}, "hi") == []


def test_status_messages_render():
    wheat = field("wheat", date(2021, 11, 5))
    waiting = decide_today(wheat, start_state(wheat), None, date(2021, 11, 1))
    over = decide_today(wheat, start_state(wheat), None, date(2022, 4, 1))

    assert render(waiting, "hi").startswith("फसल अभी बोई नहीं गई है।")
    assert render(over, "en").startswith("The season for this crop is over.")


# ---------------------------------------------------------------------------
# Last irrigation before harvest
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("crop, sowing, last_date, rule", [
    ("wheat", date(2021, 11, 5), "2022-03-31", "last_irrigation_date"),
    ("wheat_late", date(2021, 12, 5), "2022-03-31", "last_irrigation_date"),
    ("wheat_late", date(2021, 12, 6), "2022-04-10", "if_sown_after"),
    ("wheat_january", date(2022, 1, 5), "2022-04-10", "last_irrigation_date"),
    ("cotton", date(2021, 5, 1), "2021-09-30", "last_irrigation_date"),
    ("sugarcane", date(2021, 3, 1), "2022-01-24", "days_before_harvest"),
    ("sugarcane_ratoon", date(2022, 2, 1), "2022-10-08", "days_before_harvest"),
    ("sugarcane_autumn", date(2021, 10, 1), "2022-10-25", "days_before_harvest"),
    ("paddy", date(2021, 6, 25), "2021-09-27", "paddy_water.stop_irrigation_day"),
])
def test_last_irrigation(crop, sowing, last_date, rule):
    last = last_irrigation(crop, sowing)

    assert (last["date"], last["rule"]) == (last_date, rule)
    assert last["day_after_sowing"] == (date.fromisoformat(last_date) - sowing).days + 1
    assert not irrigation_stopped(crop, sowing, last["day_after_sowing"])
    assert irrigation_stopped(crop, sowing, last["day_after_sowing"] + 1)


def test_timely_wheat_is_harvested_before_its_last_irrigation_date():
    # Sown 5 Nov, 145 days: harvest on 29 March, so 31 March never binds.
    assert last_irrigation("wheat", date(2021, 11, 5))["day_after_sowing"] > get_season_length("wheat")


def test_sugarcane_stops_30_days_before_harvest():
    for crop in ("sugarcane", "sugarcane_ratoon", "sugarcane_autumn"):
        last = last_irrigation(crop, date(2021, 3, 1))
        assert get_season_length(crop) - last["day_after_sowing"] == 30


def test_profile_without_a_stop_rule():
    assert last_irrigation("wheat_fao56", date(2021, 11, 5)) is None


@pytest.mark.parametrize("crop, sowing, stop_day", [
    ("wheat_late", date(2021, 12, 1), date(2022, 4, 1)),
    ("cotton", date(2021, 5, 1), date(2021, 10, 1)),
    ("sugarcane", date(2021, 3, 1), date(2022, 1, 25)),
])
def test_dry_field_after_the_last_irrigation_date_is_not_irrigated(crop, sowing, stop_day):
    # Far past RAW, with a heat wave forecast.
    field_ = field(crop, sowing)
    before = stop_day - timedelta(days=1)

    advice = decide_today(field_, state_on(field_, before, 150.0), forecast(before, tmax=45.0), before)

    assert advice["action"] != "WAIT"
    assert advice["depth_mm"] > 0

    advice = decide_today(field_, state_on(field_, stop_day, 150.0), forecast(stop_day, tmax=45.0), stop_day)

    assert advice["action"] == "WAIT"
    assert advice["reason_code"] == "IRRIGATION_STOPPED"
    assert advice["depth_mm"] == 0.0
    assert advice["crossing_day"] is None
    assert advice["heat_risk"] == "HIGH" or crop != "wheat_late"  # still reported
    assert advice["last_irrigation_date"] == before.isoformat()
    assert advice["depletion_mm"] == 150.0                        # the balance is still reported
    assert render(advice, "en").startswith("Stop irrigating")


def test_one_day_wrapper_without_sowing_date_skips_calendar_rules():
    # No sowing date: no warning and no calendar stop date, but the
    # day-based sugarcane rule (30 days before harvest) still applies.
    common = dict(
        soil="loam", et0=5.0, rain=0.0, irrigation=0.0, previous_depletion=150.0,
        future_et0=[5.0] * 3, future_rain=[0.0] * 3, rain_probability=None,
        forecast_tmax=[30.0] * 3, area_acres=1.0, lift_m=30.0
    )
    cotton = generate_daily_decision(day_after_sowing=160, crop="cotton", **common)

    assert cotton["warnings"] == []
    assert cotton["last_irrigation_date"] is None
    assert cotton["action"] == "IRRIGATE"

    cane = generate_daily_decision(day_after_sowing=331, crop="sugarcane", **common)

    assert cane["reason_code"] == "IRRIGATION_STOPPED"
    assert cane["last_irrigation_day"] == 330

    dated = generate_daily_decision(day_after_sowing=160, crop="cotton", sowing_date="2021-05-01", **common)

    assert dated["reason_code"] == "IRRIGATION_STOPPED"


def test_season_rules_keep_live_and_catch_up_identical():
    # A catch-up over the stop date gives the same advice as deciding on
    # the stored state directly.
    sowing = date(2021, 12, 1)
    field_ = field("wheat_late", sowing)
    weather = json.loads(CACHE.read_text())["daily"]
    today = date(2022, 4, 3)
    first = weather["date"].index(sowing.isoformat())
    last = weather["date"].index(today.isoformat())
    observed = {key: weather[key][first:last] for key in ("date", "et0_mm", "rain_mm")}

    result = advance_field(field_, start_state(field_), observed, forecast(today), [], today)

    assert result["advice"] == decide_today(field_, result["state"], forecast(today), today)
    assert result["advice"]["reason_code"] == "IRRIGATION_STOPPED"


# ---------------------------------------------------------------------------
# Heat: consecutive hot days per crop
# ---------------------------------------------------------------------------

def test_consecutive_hot_days_per_crop():
    assert consecutive_hot_days_required("wheat") == 1
    assert consecutive_hot_days_required("paddy") == 1

    for crop in ("cotton", "sugarcane", "sugarcane_ratoon", "sugarcane_autumn"):
        assert consecutive_hot_days_required(crop) == 2


def test_cotton_needs_two_hot_days_in_a_row():
    # Cotton day 60 is in the flowering window (35 C).
    assert assess_heat_risk(60, [36.0, 30.0, 36.0], "cotton")["heat_risk"] == "LOW"
    assert assess_heat_risk(60, [30.0, 36.0, 37.0], "cotton")["heat_risk"] == "HIGH"
    assert assess_heat_risk(60, [36.0, 30.0, 36.0], "cotton", consecutive_days_required=1)["heat_risk"] == "HIGH"


def test_wheat_still_reacts_to_one_hot_day():
    assert assess_heat_risk(95, [32.0, 25.0, 25.0], "wheat")["heat_risk"] == "HIGH"


# ---------------------------------------------------------------------------
# New profiles
# ---------------------------------------------------------------------------

def test_new_profiles_are_consistent():
    assert get_season_length("wheat_january") == 114
    assert get_season_length("sugarcane_autumn") == 420
    assert get_crop("wheat_january")["critical_irrigation"]["name"] == "CRI"
    assert validate() == []


def test_autumn_cane_heat_window_falls_in_april_to_june():
    window = get_crop("sugarcane_autumn")["heat_windows"][0]
    planted = date(2021, 10, 1)

    assert (planted + timedelta(days=window["day_start"] - 1)).month in (3, 4)
    assert (planted + timedelta(days=window["day_end"] - 1)).month == 6


def test_check_data_catches_bad_calendar_rules():
    crops = copy.deepcopy(entries(load_json("crops.json")))
    crops["cotton"]["sowing_window"]["end"] = "02-30"
    crops["cotton"]["heat_consecutive_days"] = 5
    crops["sugarcane"]["stop_irrigation"]["days_before_harvest"] = 400
    crops["wheat"]["transplant_window"] = {"start": "06-20", "end": "07-10"}

    problems = check_crops(crops)

    assert any("cotton: sowing_window.end" in problem for problem in problems)
    assert any("cotton: heat_consecutive_days" in problem for problem in problems)
    assert any("sugarcane: stop_irrigation.days_before_harvest" in problem for problem in problems)
    assert any("wheat: give only one of" in problem for problem in problems)
