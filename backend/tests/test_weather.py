import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from boond.weather import WeatherCache, WeatherUnavailable, cell, fetch, weather_for

FIX = Path(__file__).parent / "fixtures"
FORECAST = json.loads((FIX / "forecast_ludhiana.json").read_text())
ARCHIVE = json.loads((FIX / "archive_ludhiana.json").read_text())
TODAY = date.fromisoformat(FORECAST["daily"]["time"][7])


def fake_get(urls):
    def get(url, params):
        urls.append((url, params))
        return FORECAST if "forecast" in url else ARCHIVE
    return get


def test_cell_rounds_to_two_decimals():
    assert cell(30.896309, 75.83432) == (30.9, 75.83)


def test_waiting_field_needs_no_archive():
    urls = []
    w = fetch(30.9, 75.85, TODAY + timedelta(days=20), TODAY, get_json=fake_get(urls))
    assert len(urls) == 1 and "forecast" in urls[0][0]
    assert w["forecast"]["date"][0] == TODAY.isoformat() and len(w["forecast"]["date"]) == 16


def test_forecast_rain_prob_is_a_fraction():
    w = fetch(30.9, 75.85, TODAY, TODAY, get_json=fake_get([]))
    assert all(p is None or 0 <= p <= 1 for p in w["forecast"]["rain_prob"])


def test_long_season_merges_archive_and_past_days_without_gaps():
    sow = date.fromisoformat(ARCHIVE["daily"]["time"][0])
    urls = []
    w = fetch(30.9, 75.85, sow, TODAY, get_json=fake_get(urls))
    archive_calls = [p for u, p in urls if "archive" in u]
    assert archive_calls and archive_calls[0]["start_date"] == sow.isoformat()
    obs = w["observed"]["date"]
    assert obs[0] == sow.isoformat() and obs[-1] == (TODAY - timedelta(days=1)).isoformat()
    assert len(obs) == (TODAY - sow).days and None not in w["observed"]["et0_mm"]


def test_archive_nulls_filled_by_forecast_past_days():
    archive = json.loads(json.dumps(ARCHIVE))
    archive["daily"]["et0_fao_evapotranspiration"][-3:] = [None, None, None]
    get = lambda url, params: FORECAST if "forecast" in url else archive  # noqa: E731
    sow = date.fromisoformat(archive["daily"]["time"][0])
    w = fetch(30.9, 75.85, sow, TODAY, get_json=get)
    # ERA5 lags a few days: its last 3 days are null, and the forecast's past days fill them
    assert None not in w["observed"]["et0_mm"]
    assert len(w["observed"]["date"]) == (TODAY - sow).days


def test_cache_used_when_fresh_and_stale_fallback(bucket):
    cache = WeatherCache(bucket, "boond-test")
    w, stale = weather_for(30.9, 75.85, TODAY, TODAY, cache, get_json=fake_get([]))
    assert not stale
    calls = []
    w2, stale2 = weather_for(30.9, 75.85, TODAY, TODAY, cache, get_json=fake_get(calls))
    assert calls == [] and w2 == w and not stale2

    def down(url, params):
        raise OSError("network down")
    tomorrow = TODAY + timedelta(days=1)
    w3, stale3 = weather_for(30.9, 75.85, TODAY, tomorrow, cache, get_json=down)
    assert stale3 and w3["forecast"]["date"][0] == tomorrow.isoformat()
    assert w3["observed"]["date"][-1] == TODAY.isoformat()


def test_cache_with_later_sowing_is_refetched(bucket):
    cache = WeatherCache(bucket, "boond-test")
    weather_for(30.9, 75.85, TODAY, TODAY, cache, get_json=fake_get([]))
    calls = []
    weather_for(30.9, 75.85, TODAY - timedelta(days=30), TODAY, cache, get_json=fake_get(calls))
    assert calls, "a field sown earlier than the cached range needs a new fetch"


def test_no_weather_and_no_cache_raises(bucket):
    def down(url, params):
        raise OSError("network down")
    with pytest.raises(WeatherUnavailable):
        weather_for(30.9, 75.85, TODAY, TODAY, WeatherCache(bucket, "boond-test"), get_json=down)
