from datetime import date

from boond.daily import run_all
from tests.test_refresh import PROFILE, SUB

TODAY = date(2022, 1, 20)


def test_runs_every_active_field_and_fetches_weather_once_per_cell(deps):
    deps.store.put_profile("t1", PROFILE)
    deps.store.put_profile("t2", dict(PROFILE, latitude=30.901, sowing_date="2021-11-20"))  # same cell, later sowing
    deps.store.put_profile("t3", dict(PROFILE, status="INACTIVE"))
    summary = run_all(deps, TODAY)
    assert summary == {"fields": 2, "ok": 2, "skipped": 0, "failed": 0}
    assert len(deps.weather_calls) == 1 and deps.weather_calls[0][2] == date(2021, 11, 5)
    assert deps.store.latest_day("t2")["advice"]["day_after_sowing"] == 62
    assert deps.store.latest_day("t3") is None


def test_second_run_same_day_sends_no_second_push(deps):
    deps.store.put_profile("t1", PROFILE)
    deps.store.put_push("t1", SUB)
    run_all(deps, TODAY)
    run_all(deps, TODAY)
    assert len(deps.pusher.sent) == 1


def test_one_field_failing_does_not_stop_others(deps):
    deps.store.put_profile("t1", PROFILE)
    deps.store.put_profile("bad", dict(PROFILE, soil="no-such-soil"))
    summary = run_all(deps, TODAY)
    assert summary["ok"] == 1 and summary["failed"] == 1


def test_weather_unavailable_skips_cell(deps):
    from boond.weather import WeatherUnavailable

    def down(*args):
        raise WeatherUnavailable("down")
    deps.weather = down
    deps.store.put_profile("t1", PROFILE)
    assert run_all(deps, TODAY) == {"fields": 1, "ok": 0, "skipped": 1, "failed": 0}


def test_field_deleted_during_listing_is_skipped(deps):
    deps.store.put_profile("t1", PROFILE)
    real_get = deps.store.get_profile
    deps.store.get_profile = lambda token: None if token == "gone" else real_get(token)
    real_tokens = deps.store.active_tokens
    deps.store.active_tokens = lambda: real_tokens() + ["gone"]   # index not yet consistent after a delete
    assert run_all(deps, TODAY) == {"fields": 1, "ok": 1, "skipped": 0, "failed": 0}


def test_unexpected_error_in_one_cell_does_not_stop_others(deps):
    deps.store.put_profile("t1", PROFILE)
    deps.store.put_profile("t2", dict(PROFILE, latitude=31.5))
    real = deps.weather

    def flaky(lat, lon, earliest, today):
        if lat == 31.5:
            raise RuntimeError("S3 throttled")
        return real(lat, lon, earliest, today)
    deps.weather = flaky
    assert run_all(deps, TODAY) == {"fields": 2, "ok": 1, "skipped": 1, "failed": 0}


def test_weather_down_tells_the_farmer_advice_is_unavailable(deps):
    from boond.weather import WeatherUnavailable

    def down(*args):
        raise WeatherUnavailable("down")
    deps.store.put_profile("t1", PROFILE)
    deps.store.put_push("t1", SUB)
    deps.weather = down
    run_all(deps, TODAY)
    assert deps.store.latest_day("t1")["advice"]["status"] == "UNAVAILABLE"
    assert len(deps.pusher.sent) == 1


def test_missing_observed_day_tells_the_farmer_advice_is_unavailable(deps):
    from tests.conftest import replay_weather
    deps.store.put_profile("t1", PROFILE)

    def gappy(lat, lon, earliest, today):
        w = replay_weather(earliest.isoformat(), today)
        for k in ("date", "et0_mm", "rain_mm", "tmax_c"):
            del w["observed"][k][5]
        return w, False
    deps.weather = gappy
    summary = run_all(deps, TODAY)
    assert deps.store.latest_day("t1")["advice"]["status"] == "UNAVAILABLE"
    assert summary["skipped"] == 1 and summary["failed"] == 0
