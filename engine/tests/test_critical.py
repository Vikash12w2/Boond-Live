import json
from datetime import date
from pathlib import Path

from engine.advisor import make_daily_decision
from engine.critical import critical_irrigation_due
from engine.replay import replay


CACHE = Path(__file__).resolve().parents[2] / "replay" / "cache"


def test_cri_window_depends_on_sowing_month():
    # Later sowing: day 28-34; October sowing: day 21-27.
    assert critical_irrigation_due("wheat", 27, 0.0, "2021-11-05") is None
    assert critical_irrigation_due("wheat", 28, 0.0, "2021-11-05")["name"] == "CRI"
    assert critical_irrigation_due("wheat", 34, 0.0, "2021-11-05") is not None
    assert critical_irrigation_due("wheat", 35, 0.0, "2021-11-05") is None
    assert critical_irrigation_due("wheat", 21, 0.0, date(2021, 10, 28)) is not None


def test_cri_is_skipped_after_enough_water_or_without_tracking():
    assert critical_irrigation_due("wheat", 28, 25.0, "2021-11-05") is None
    assert critical_irrigation_due("wheat", 28, 10.0, "2021-11-05")["needed_mm"] == 15.0
    assert critical_irrigation_due("wheat", 28, None, "2021-11-05") is None
    assert critical_irrigation_due("cotton", 28, 0.0, "2021-04-25") is None


def decision(critical, future_rain=(0.0, 0.0, 0.0), probability=0.1):
    return make_daily_decision(
        current_depletion=10.0,
        raw=60.0,
        future_etc=[2.0, 2.0, 2.0],
        future_rain=list(future_rain),
        rain_probability=probability,
        heat_result={"heat_risk": "LOW"},
        maximum_depth=75,
        critical=critical
    )


def test_cri_irrigates_a_healthy_field():
    critical = critical_irrigation_due("wheat", 28, 0.0, "2021-11-05")
    result = decision(critical)

    assert result["action"] == "IRRIGATE"
    assert result["reason_code"] == "CRITICAL_STAGE_IRRIGATION"
    assert result["depth_mm"] == 50


def test_cri_skips_for_confident_rain_that_covers_it():
    critical = critical_irrigation_due("wheat", 28, 0.0, "2021-11-05")

    assert decision(critical, (0.0, 30.0, 0.0), [0.1, 0.9, 0.1])["reason_code"] == "CRITICAL_STAGE_RAIN_EXPECTED"
    assert decision(critical, (0.0, 30.0, 0.0), [0.1, 0.4, 0.1])["action"] == "IRRIGATE"


def test_without_critical_the_field_waits():
    assert decision(None)["action"] == "WAIT"


def test_real_2021_22_replay_gives_the_cri_irrigation():
    weather = json.loads((CACHE / "ludhiana_actual_2021_22.json").read_text())
    result = replay(weather, "wheat", date(2021, 11, 5), "loam")
    first = next(row for row in result["boond_days"] if row["irrigation_mm"] > 0)

    # Nov-Dec 2021 were almost dry: CRI irrigation 4 weeks after sowing.
    assert first["date"] == "2021-12-02"
    assert first["reason_code"] == "CRITICAL_STAGE_IRRIGATION"
    assert result["boond"]["stress_days"] == 0
