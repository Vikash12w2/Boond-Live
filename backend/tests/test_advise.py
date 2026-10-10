import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from boond.advise import engine_field, run_field
from engine.field_runner import MissingWeather

ROOT = Path(__file__).resolve().parents[2]
REPLAY = json.loads((ROOT / "replay/cache/ludhiana_actual_2021_22.json").read_text())["daily"]
PROFILE = {"language": "hi", "latitude": 30.9, "longitude": 75.85, "crop": "wheat", "sowing_date": "2021-11-05",
           "soil": "loam", "area_acres": 1.0, "lift_m": 30, "pump_eff": 0.4, "pump_type": "electric", "status": "ACTIVE"}


def weather_on(today):
    i = REPLAY["date"].index(today.isoformat())
    s = REPLAY["date"].index(PROFILE["sowing_date"])
    obs = {k: REPLAY[k][s:i] for k in ("date", "et0_mm", "rain_mm", "tmax_c")}
    fc = {k: REPLAY[k][i:i + 16] for k in ("date", "et0_mm", "rain_mm", "tmax_c")}
    fc["rain_prob"] = [0.0] * len(fc["date"])
    return {"observed": obs, "forecast": fc}


def test_engine_field_uses_the_engine_profile_key():
    assert engine_field(PROFILE)["crop"] == "wheat"
    assert engine_field(dict(PROFILE, sowing_date="2021-12-10"))["crop"] == "wheat_late"


def test_run_field_matches_engine_and_adds_tmax():
    today = date(2022, 1, 20)
    advice = run_field(PROFILE, [], weather_on(today), today)
    assert advice["status"] == "ACTIVE" and advice["date"] == "2022-01-20"
    assert advice["outlook"][0]["tmax_c"] == REPLAY["tmax_c"][REPLAY["date"].index("2022-01-20")]


def test_late_checkin_is_applied():
    today = date(2022, 1, 20)
    dry = run_field(PROFILE, [], weather_on(today), today)
    wet = run_field(PROFILE, [{"date": "2022-01-10", "type": "WATERED", "level": "normal", "mm_assumed": 75.0}],
                    weather_on(today), today)
    assert wet["depletion_mm"] < dry["depletion_mm"]


def test_run_waiting_field():
    today = date(2021, 11, 1)
    w = {"observed": {"date": [], "et0_mm": [], "rain_mm": [], "tmax_c": []},
         "forecast": weather_on(date(2021, 11, 5))["forecast"]}
    w["forecast"]["date"] = [(today + timedelta(days=i)).isoformat() for i in range(len(w["forecast"]["date"]))]
    assert run_field(PROFILE, [], w, today)["status"] == "WAITING"


def test_gap_in_observed_raises():
    today = date(2022, 1, 20)
    w = weather_on(today)
    for k in w["observed"]:
        del w["observed"][k][10]
    with pytest.raises(MissingWeather):
        run_field(PROFILE, [], w, today)


def test_outlook_rows_carry_the_engine_heat_threshold():
    today = date(2022, 2, 8)  # day 96: flowering window (days 92-110, 31 C) for this sowing
    advice = run_field(PROFILE, [], weather_on(today), today)
    by_day = {row["day_after_sowing"]: row["heat_threshold_c"] for row in advice["outlook"]}
    assert by_day[96] == 31.0 and by_day[111] == 35.0  # 111: grain filling only
