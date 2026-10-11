import copy
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from engine.checkins import make_event
from engine.field_runner import (
    MissingWeather,
    advance_field,
    apply_day,
    decide_today,
    start_state
)
from engine.kc import get_season_length
from engine.simulate import boond_policy, simulate_season


CACHE = Path(__file__).resolve().parents[2] / "replay" / "cache"
WEATHER = json.loads((CACHE / "ludhiana_actual_2021_22.json").read_text())["daily"]
FIELD = {
    "crop": "wheat",
    "soil": "loam",
    "sowing_date": "2021-11-05",
    "area_acres": 1.0,
    "lift_m": 30.0,
    "pump_eff": 0.4
}


def window(start, days, with_probability=True):
    """Rows of the 2021-22 weather from `start` (a date) on."""
    index = WEATHER["date"].index(start.isoformat())
    rows = {key: WEATHER[key][index:index + days] for key in ("date", "et0_mm", "rain_mm", "tmax_c")}

    if with_probability:
        rows["rain_prob"] = [None] * len(rows["date"])

    return rows


def observed_between(first, last):
    """Observed weather from `first` to `last` inclusive."""
    return window(first, (last - first).days + 1, with_probability=False)


def flat_forecast(today, days=16, et0=4.0, rain=0.0, tmax=25.0, probability=None):
    return {
        "date": [(today + timedelta(days=i)).isoformat() for i in range(days)],
        "et0_mm": [et0] * days,
        "rain_mm": [rain] * days,
        "tmax_c": [tmax] * days,
        "rain_prob": [probability] * days
    }


def test_daily_live_runs_match_the_replay_exactly():
    # The live job, run every morning of the 2021-22 season with the
    # farmer following each advice through a WATERED check-in, must
    # give exactly the replay's advice on every day.
    sowing = date(2021, 11, 5)
    replay = simulate_season({"daily": WEATHER}, sowing, "loam", crop="wheat",
                             policy=boond_policy())

    state = start_state(FIELD)
    events = []

    for offset, replay_day in enumerate(replay["days"]):
        today = sowing + timedelta(days=offset)
        observed = observed_between(sowing, today - timedelta(days=1)) if offset else None
        todays_events = [event for event in events if event["date"] == (today - timedelta(days=1)).isoformat()]

        result = advance_field(FIELD, state, observed, window(today, 16), todays_events, today)
        state, advice = result["state"], result["advice"]

        assert (advice["action"], advice["reason_code"], advice["depth_mm"]) == (
            replay_day["action"], replay_day["reason_code"], replay_day["irrigation_mm"]
        ), today

        if advice["depth_mm"] > 0:
            events.append({
                "date": today.isoformat(),
                "type": "WATERED",
                "level": "normal",
                "mm_assumed": advice["depth_mm"]
            })

    assert offset + 1 == get_season_length("wheat")


def test_catch_up_after_missed_days_equals_daily_runs():
    sowing = date(2021, 11, 5)
    today = sowing + timedelta(days=40)
    forecast = window(today, 16)

    daily_state = start_state(FIELD)

    for offset in range(40):
        on_date = sowing + timedelta(days=offset)
        daily_state, _ = apply_day(FIELD, daily_state, on_date,
                                   WEATHER["et0_mm"][WEATHER["date"].index(on_date.isoformat())],
                                   WEATHER["rain_mm"][WEATHER["date"].index(on_date.isoformat())])

    result = advance_field(FIELD, start_state(FIELD), observed_between(sowing, today - timedelta(days=1)),
                           forecast, [], today)

    assert len(result["days"]) == 40
    assert result["state"] == daily_state
    assert result["advice"] == decide_today(FIELD, daily_state, forecast, today)


def test_missing_observed_day_raises_and_leaves_state_alone():
    sowing = date(2021, 11, 5)
    state = start_state(FIELD)
    before = copy.deepcopy(state)
    observed = observed_between(sowing, sowing + timedelta(days=9))

    for key in observed:
        del observed[key][4]          # day 5 is missing

    with pytest.raises(MissingWeather):
        advance_field(FIELD, state, observed, flat_forecast(sowing + timedelta(days=10)), [],
                      sowing + timedelta(days=10))

    assert state == before


def test_missing_et0_raises():
    sowing = date(2021, 11, 5)
    observed = observed_between(sowing, sowing + timedelta(days=2))
    observed["et0_mm"][1] = None

    with pytest.raises(MissingWeather):
        advance_field(FIELD, start_state(FIELD), observed, None, [], sowing + timedelta(days=3))


def test_waiting_before_sowing_and_season_over_after_harvest():
    before = advance_field(FIELD, start_state(FIELD), None, None, [], date(2021, 11, 1))

    assert before["advice"]["status"] == "WAITING"
    assert before["advice"]["reason_code"] == "NOT_SOWN_YET"
    assert before["advice"]["depth_mm"] == 0.0

    after = decide_today(FIELD, start_state(FIELD), None, date(2021, 11, 5) + timedelta(days=145))

    assert after["status"] == "SEASON_OVER"
    assert after["action"] == "WAIT"


def test_without_a_forecast_a_dry_field_is_still_irrigated():
    today = date(2021, 11, 5) + timedelta(days=60)
    state = dict(start_state(FIELD), depletion_mm=90.0, water_since_sowing_mm=100.0,
                 last_processed_date=(today - timedelta(days=1)).isoformat())

    advice = decide_today(FIELD, state, None, today)

    assert advice["forecast_days"] == 0
    assert advice["action"] == "IRRIGATE"
    assert advice["reason_code"] == "ALREADY_PAST_RAW"

    wet = decide_today(FIELD, dict(state, depletion_mm=10.0), None, today)

    assert wet["action"] == "WAIT"
    assert wet["reason_code"] == "NO_FORECAST_DATA"


def test_without_a_forecast_cri_is_still_given():
    # Sown 5 Nov: CRI window is day 28-34.
    today = date(2021, 11, 5) + timedelta(days=27)
    state = dict(start_state(FIELD), depletion_mm=20.0,
                 last_processed_date=(today - timedelta(days=1)).isoformat())

    advice = decide_today(FIELD, state, None, today)

    assert advice["reason_code"] == "CRITICAL_STAGE_IRRIGATION"
    assert advice["critical_stage"] == "CRI"


def test_forecast_is_cut_at_the_first_missing_et0():
    today = date(2021, 11, 5) + timedelta(days=50)
    forecast = flat_forecast(today)
    forecast["et0_mm"][5] = None
    state = dict(start_state(FIELD), last_processed_date=(today - timedelta(days=1)).isoformat())

    advice = decide_today(FIELD, state, forecast, today)

    assert advice["forecast_days"] == 5
    assert len(advice["outlook"]) == 5


def test_outlook_has_sixteen_days():
    today = date(2021, 11, 5) + timedelta(days=50)
    state = dict(start_state(FIELD), last_processed_date=(today - timedelta(days=1)).isoformat())

    advice = decide_today(FIELD, state, window(today, 16), today)

    assert len(advice["outlook"]) == 16
    assert advice["outlook"][0]["date"] == today.isoformat()
    assert {"projected_depletion_mm", "raw_mm", "rain_prob"} <= set(advice["outlook"][0])


def test_rain_checkin_replaces_gridded_rain_in_the_balance():
    sowing = date(2021, 11, 5)
    day = sowing + timedelta(days=9)
    observed = observed_between(day, day)
    observed["rain_mm"][0] = 2.0
    state = dict(start_state(FIELD), last_processed_date=(day - timedelta(days=1)).isoformat(),
                 depletion_mm=30.0)

    result = advance_field(FIELD, state, observed, flat_forecast(day + timedelta(days=1)),
                           [make_event("RAIN", "moderate", day.isoformat())], day + timedelta(days=1))

    assert result["days"][0]["rain_mm"] == 30.0


def test_stored_mm_assumed_wins_over_current_config():
    day = date(2021, 11, 5) + timedelta(days=9)
    event = make_event("WATERED", "normal", day.isoformat())

    assert event["mm_assumed"] == 75.0
    assert event["choice"] == "normal"

    event["mm_assumed"] = 60.0        # assumed when the check-in was made
    observed = observed_between(day, day)
    state = dict(start_state(FIELD), last_processed_date=(day - timedelta(days=1)).isoformat())

    result = advance_field(FIELD, state, observed, None, [event], day + timedelta(days=1))

    assert result["days"][0]["irrigation_mm"] == 60.0


def test_state_is_json_serialisable_and_versioned():
    sowing = date(2021, 11, 5)
    today = sowing + timedelta(days=10)
    result = advance_field(FIELD, start_state(FIELD), observed_between(sowing, today - timedelta(days=1)),
                           window(today, 16), [], today)

    assert json.loads(json.dumps(result["state"])) == result["state"]
    assert result["state"]["version"] == 1
    assert result["state"]["last_processed_date"] == (today - timedelta(days=1)).isoformat()


def test_paddy_field_advances_with_the_pond_model():
    field = dict(FIELD, crop="paddy", sowing_date="2021-06-25")
    sowing = date(2021, 6, 25)
    today = sowing + timedelta(days=20)

    result = advance_field(field, start_state(field), observed_between(sowing, today - timedelta(days=1)),
                           window(today, 16), [], today)

    assert result["advice"]["status"] == "ACTIVE"
    assert "pond_mm" in result["advice"]
    assert "pond_mm" in result["state"]
    assert len(result["days"]) == 20


def test_field_registered_before_sowing_waits_then_starts_on_the_sowing_date():
    # Registered on 1 Nov for a 5 Nov sowing (spec 4.1: WAITING status).
    sowing = date(2021, 11, 5)
    state = dict(start_state(FIELD), last_processed_date="2021-10-31")

    early = advance_field(FIELD, state, None, window(date(2021, 11, 3), 16), [], date(2021, 11, 3))

    assert early["advice"]["status"] == "WAITING"
    assert early["days"] == []
    assert early["state"]["last_processed_date"] == "2021-11-02"

    started = advance_field(FIELD, early["state"], observed_between(sowing, date(2021, 11, 6)),
                            window(date(2021, 11, 7), 16), [], date(2021, 11, 7))

    assert started["advice"]["status"] == "ACTIVE"
    assert [row["date"] for row in started["days"]] == ["2021-11-05", "2021-11-06"]


def test_apply_day_before_sowing_only_moves_the_date():
    state = start_state(FIELD)
    new_state, row = apply_day(FIELD, state, date(2021, 11, 1), 3.0, 0.0)

    assert row is None
    assert new_state["depletion_mm"] == state["depletion_mm"]
    assert new_state["last_processed_date"] == "2021-11-01"
