"""
Pinned results of the 2021-22 Ludhiana replay (Open-Meteo ERA5
archive, observed weather standing in for the forecast, forecast rain
not trusted). These are the numbers quoted in the demo: if a change to
the engine or the data moves them, this test fails so the figures are
re-checked before they are used again.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from engine.data import get_crop
from engine.replay import replay


CACHE = Path(__file__).resolve().parents[2] / "replay" / "cache"
WEATHER = json.loads((CACHE / "ludhiana_actual_2021_22.json").read_text())

# crop, sowing date,
# (Boond irrigations, mm, stress days, of which after the last irrigation date),
# (baseline irrigations, mm, stress days, of which after the last irrigation date)
#
# Stress days after the crop's last irrigation date (PAU wheat 31 March /
# 10 April, paddy day 95, cotton 30 September, sugarcane 30 days before
# harvest) are the intended drying-off before harvest, in both runs.
LOAM_RESULTS = [
    ("wheat", date(2021, 11, 5), (3, 162.1, 0, 0), (2, 125.0, 14, 0)),
    ("wheat_late", date(2021, 12, 1), (4, 225.1, 0, 0), (2, 125.0, 31, 12)),
    ("wheat_january", date(2022, 1, 5), (5, 240.6, 9, 9), (3, 200.0, 34, 18)),
    ("paddy", date(2021, 6, 25), (7, 527.9, 7, 7), (7, 525.0, 8, 8)),
    ("cotton", date(2021, 5, 1), (6, 282.1, 0, 0), (6, 450.0, 8, 0)),
    ("sugarcane", date(2021, 3, 1), (12, 749.8, 0, 0), (20, 1500.0, 8, 0)),
]


def totals(summary):
    return (
        summary["irrigation_events"],
        summary["irrigation_mm"],
        summary["stress_days"],
        summary["drying_off_stress_days"],
    )


@pytest.mark.parametrize("crop, sowing, boond, baseline", LOAM_RESULTS, ids=[row[0] for row in LOAM_RESULTS])
def test_pinned_loam_results(crop, sowing, boond, baseline):
    result = replay(WEATHER, crop, sowing, "loam")

    assert totals(result["boond"]) == boond
    assert totals(result["baseline"]) == baseline


def test_replay_is_labelled_honestly():
    result = replay(WEATHER, "wheat", date(2021, 11, 5), "loam")

    assert result["label"].startswith("SIMULATION")
    assert result["boond_forecast"] == "actual weather used as forecast (perfect foresight)"
    assert result["boond_rain_probability"] is None
    assert all(row["action"] != "SKIP" for row in result["boond_days"])


def test_wheat_irrigation_dates():
    result = replay(WEATHER, "wheat", date(2021, 11, 5), "loam")

    boond = [(row["date"], row["reason_code"]) for row in result["boond_days"] if row["irrigation_mm"] > 0]
    baseline = [row["date"] for row in result["baseline_days"] if row["irrigation_mm"] > 0]

    assert boond == [
        ("2021-12-02", "CRITICAL_STAGE_IRRIGATION"),
        ("2022-02-28", "CROSSES_RAW_IN_2D"),
        ("2022-03-17", "HEAT_RISK"),
    ]
    assert baseline == ["2021-12-02", "2022-02-16"]


def test_boond_has_no_upland_stress_days_before_the_last_irrigation_date():
    for crop, sowing, _, _ in LOAM_RESULTS:
        if crop == "paddy":
            continue

        for soil in ("sandy", "loam", "clay"):
            summary = replay(WEATHER, crop, sowing, soil)["boond"]
            assert summary["stress_days"] == summary["drying_off_stress_days"], (crop, soil)


def test_no_irrigation_after_the_last_irrigation_date():
    for crop, sowing, _, _ in LOAM_RESULTS:
        result = replay(WEATHER, crop, sowing, "loam")
        last = result["boond"]["last_irrigation_date"]

        assert last is not None, crop
        assert all(
            row["irrigation_mm"] == 0 for row in result["boond_days"] if row["date"] > last
        ), crop


def test_late_wheat_heat_irrigation_stops_on_31_march():
    # Sown 1 Dec (on or before 5 Dec): PAU allows irrigation up to 31 March.
    # The April 2022 heat no longer gives a heat irrigation on 4 April.
    result = replay(WEATHER, "wheat_late", date(2021, 12, 1), "loam")

    boond = [(row["date"], row["reason_code"]) for row in result["boond_days"] if row["irrigation_mm"] > 0]

    assert boond == [
        ("2021-12-28", "CRITICAL_STAGE_IRRIGATION"),
        ("2022-02-28", "CROSSES_RAW_IN_2D"),
        ("2022-03-13", "HEAT_RISK"),
        ("2022-03-25", "HEAT_RISK"),
    ]
    assert result["boond"]["last_irrigation_date"] == "2022-03-31"
    assert {row["reason_code"] for row in result["boond_days"] if row["date"] > "2022-03-31"} == {
        "IRRIGATION_STOPPED"
    }


def test_january_wheat_after_a_wet_january_needs_no_cri_irrigation():
    # 119 mm fell in January 2022, so the crown-root irrigation is skipped.
    result = replay(WEATHER, "wheat_january", date(2022, 1, 5), "loam")

    reasons = [row["reason_code"] for row in result["boond_days"] if row["irrigation_mm"] > 0]

    assert "CRITICAL_STAGE_IRRIGATION" not in reasons
    assert reasons.count("HEAT_RISK") == 3
    assert result["boond"]["last_irrigation_date"] == "2022-04-10"


def test_two_hot_days_rule_reduces_heat_irrigations_for_long_season_crops():
    # cotton and sugarcane need 2 consecutive hot days (crops.json heat_consecutive_days).
    for crop, sowing, heat_irrigations in (
        ("cotton", date(2021, 5, 1), 4),
        ("sugarcane", date(2021, 3, 1), 2),
    ):
        days = replay(WEATHER, crop, sowing, "loam")["boond_days"]
        assert sum(
            1 for row in days if row["reason_code"] == "HEAT_RISK" and row["irrigation_mm"] > 0
        ) == heat_irrigations, crop


@pytest.mark.parametrize("crop, sowing", [
    ("wheat", date(2021, 11, 5)),
    ("wheat_late", date(2021, 12, 1)),
    ("wheat_january", date(2022, 1, 5)),
])
def test_wheat_seasonal_water_use_is_in_the_sanity_range(crop, sowing):
    # crops.json validation_targets.seasonal_etc_mm
    low, high = get_crop(crop)["validation_targets"]["seasonal_etc_mm"]
    result = replay(WEATHER, crop, sowing, "loam")

    assert low <= result["boond"]["seasonal_etc_mm"] <= high
