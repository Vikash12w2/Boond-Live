from datetime import date, timedelta

import pytest

from engine.check_data import seasonal_etc, validate
from engine.kc import get_kc
from engine.replay import replay
from engine.simulate import simulate_season


def test_data_files_are_consistent():
    assert validate() == []


def make_weather(days, start=date(2021, 11, 10), et0=4.0, rain=None, tmax=25.0):
    return {
        "daily": {
            "date": [(start + timedelta(days=i)).isoformat() for i in range(days)],
            "et0_mm": [et0] * days,
            "rain_mm": rain or [0.0] * days,
            "tmax_c": [tmax] * days,
        }
    }


def test_dry_season_irrigates_without_stress():
    result = simulate_season(make_weather(160), date(2021, 11, 10), "loam")
    summary = result["summary"]

    assert len(result["days"]) == 145
    assert summary["irrigation_events"] > 0
    assert summary["stress_days"] == 0
    # Every advised depth respects the 40-75 mm flood limits.
    depths = [row["irrigation_mm"] for row in result["days"] if row["irrigation_mm"] > 0]
    assert min(depths) >= 40.0
    assert max(depths) <= 75.0
    assert summary["gross_pumped_mm"] == pytest.approx(summary["irrigation_mm"] / 0.70, abs=0.1)


def test_season_must_be_covered_by_weather():
    with pytest.raises(ValueError):
        simulate_season(make_weather(60), date(2021, 11, 10), "loam")


def test_stress_free_seasonal_etc():
    # Constant ET0 4 mm: sum of Kc over 145 days x 4.
    etc = seasonal_etc(make_weather(160), "wheat", date(2021, 11, 10))

    assert etc == pytest.approx(4.0 * sum(get_kc(day) for day in range(1, 146)))


def test_wheat_replay_follows_the_pau_calendar():
    result = replay(make_weather(160), "wheat", date(2021, 11, 10), "loam")
    baseline_days = [
        row["day"] for row in result["baseline_days"] if row["irrigation_mm"] > 0
    ]

    # Sown in November: day 28, then 5.5 (38.5 days), 5.5 and 4 weeks later.
    assert baseline_days == [28, 67, 106, 134]
    assert result["baseline"]["irrigation_mm"] == 50 + 3 * 75


def baseline_irrigation_days(rain):
    result = replay(make_weather(160, rain=rain), "wheat", date(2021, 11, 10), "loam")
    return [row["day"] for row in result["baseline_days"] if row["irrigation_mm"] > 0]


def test_wheat_baseline_rain_delay_rule():
    # Sown 10 Nov: first irrigation at 4 weeks (day 28), second
    # 5.5 weeks later (day 66.5 -> 67) without rain.
    assert baseline_irrigation_days([0.0] * 160)[:2] == [28, 67]

    # 2 cm on day 40 (19 Dec, before 31 Jan): next interval +10 days.
    rain = [0.0] * 160
    rain[39] = 20.0
    assert baseline_irrigation_days(rain)[:2] == [28, 77]


def test_rain_before_first_wheat_irrigation_does_not_move_it():
    # PAU states the rain rule for intervals between irrigations.
    rain = [0.0] * 160
    rain[9] = 20.0
    assert baseline_irrigation_days(rain)[0] == 28


def test_replay_does_not_trust_rain_by_default():
    rain = [0.0] * 160
    for day in range(30, 150, 12):
        rain[day] = 30.0
    weather = make_weather(160, rain=rain)

    cautious = replay(weather, "wheat", date(2021, 11, 10), "loam")
    perfect = replay(weather, "wheat", date(2021, 11, 10), "loam", rain_probability=1.0)

    assert cautious["boond_rain_probability"] is None
    assert all(row["action"] != "SKIP" for row in cautious["boond_days"])
    assert perfect["boond"]["irrigation_mm"] <= cautious["boond"]["irrigation_mm"]


def test_replay_uses_separate_forecast_file():
    weather = make_weather(160)                      # no rain actually fell
    forecast = make_weather(160, rain=[25.0] * 160)  # but rain was forecast
    forecast["daily"]["rain_prob"] = [0.9] * 160
    forecast["source"] = "test forecast"

    result = replay(weather, "wheat", date(2021, 11, 10), "loam", forecast=forecast)

    assert result["boond_forecast"] == "test forecast"
    assert any(row["action"] == "SKIP" for row in result["boond_days"])
    assert all(row["rain_mm"] == 0.0 for row in result["boond_days"])


def test_paddy_replay_runs_the_pond_model():
    weather = make_weather(130, start=date(2021, 6, 25), et0=6.0)
    result = replay(weather, "paddy", date(2021, 6, 25), "sandy")

    assert result["baseline"]["irrigation_events"] > 5
    assert result["boond"]["irrigation_events"] > 5
    assert "pond_mm" in result["boond_days"][0]


def test_cotton_baseline_interval():
    weather = make_weather(170, start=date(2021, 5, 1), et0=6.0)
    result = replay(weather, "cotton", date(2021, 5, 1), "loam")
    days = [row["day"] for row in result["baseline_days"] if row["irrigation_mm"] > 0]

    assert days[:3] == [35, 52, 69]
    # Last irrigation by 30 September (day 153).
    assert days[-1] <= 153


def test_baseline_credits_at_most_one_irrigation_of_rain_per_interval():
    # 150 mm on day 40 credits only 75 mm: +37.5 days, not +75.
    rain = [0.0] * 160
    rain[39] = 150.0
    assert baseline_irrigation_days(rain)[:2] == [28, 104]


def test_identical_forecast_file_is_rejected():
    weather = make_weather(160)

    with pytest.raises(ValueError, match="identical"):
        replay(weather, "wheat", date(2021, 11, 10), "loam", forecast=make_weather(160))
