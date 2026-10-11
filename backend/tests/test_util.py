from datetime import date, datetime, timezone

from boond.util import dumps, loads, today_ist, token_hash


def test_today_ist_rolls_over_at_1830_utc():
    assert today_ist(datetime(2026, 10, 10, 18, 29, tzinfo=timezone.utc)) == date(2026, 10, 10)
    assert today_ist(datetime(2026, 10, 10, 18, 30, tzinfo=timezone.utc)) == date(2026, 10, 11)


def test_token_hash_is_short_and_stable():
    assert token_hash("abc") == token_hash("abc")
    assert len(token_hash("abc")) == 8 and "abc" not in token_hash("abc")


def test_json_round_trip_keeps_unicode_and_floats():
    obj = {"t": "आज पानी दें", "x": 1.5, "n": None}
    assert loads(dumps(obj)) == obj


def test_package_logs_at_info_in_lambda():
    import logging

    import boond  # noqa: F401
    assert logging.getLogger("boond.refresh").getEffectiveLevel() == logging.INFO
