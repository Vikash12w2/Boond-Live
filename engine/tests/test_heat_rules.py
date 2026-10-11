from engine.heat_rules import (
    assess_heat_risk,
    check_heat_risk,
    get_heat_stage,
    get_heat_threshold
)


# Punjab wheat (crops.json): flowering days 92-110 at 31 C,
# grain filling days 106-140 at 35 C. The windows overlap.


def test_thresholds_are_read_from_crops_json():
    # Bug 1: the thresholds were looked up under a missing key.
    assert get_heat_threshold("flowering") == 31.0
    assert get_heat_threshold("grain_filling") == 35.0
    assert get_heat_threshold("tillering") is None
    assert get_heat_threshold("boll_development", "cotton") == 38.0


def test_check_heat_risk_fires_at_flowering():
    result = check_heat_risk("flowering", [36.0, 36.0, 36.0])

    assert result["heat_risk"] == "HIGH"
    assert result["threshold_c"] == 31.0
    assert result["reason_code"] == "HEAT_THRESHOLD_EXCEEDED"


def test_check_heat_risk_below_threshold():
    result = check_heat_risk("grain_filling", [33.0, 34.0, 34.9])

    assert result["heat_risk"] == "LOW"
    assert result["reason_code"] == "HEAT_THRESHOLD_NOT_EXCEEDED"


def test_check_heat_risk_insensitive_stage():
    result = check_heat_risk("tillering", [40.0])

    assert result["heat_risk"] == "LOW"
    assert result["reason_code"] == "STAGE_NOT_HEAT_SENSITIVE"


def test_heat_stage_is_derived_from_crop_day():
    assert get_heat_stage(91) is None
    assert get_heat_stage(92) == "flowering"
    assert get_heat_stage(110) == "flowering"
    assert get_heat_stage(111) == "grain_filling"
    assert get_heat_stage(140) == "grain_filling"
    assert get_heat_stage(141) is None
    assert get_heat_stage(80, "paddy") == "flowering"


def test_assess_uses_each_days_own_stage():
    # Days 109 and 110 are flowering (31 C); day 111 is grain
    # filling only (35 C), so 33 C there is not hot.
    result = assess_heat_risk(109, [30.0, 30.0, 33.0])

    assert result["heat_risk"] == "LOW"
    assert result["hot_days"] == []

    result = assess_heat_risk(109, [30.0, 32.0, 33.0])

    assert result["heat_risk"] == "HIGH"
    assert result["stage"] == "flowering"
    assert result["hot_days"] == [110]


def test_overlapping_windows_use_the_lowest_threshold_reached():
    # Day 108 is in both windows; 33 C exceeds the flowering 31 C.
    result = assess_heat_risk(108, [33.0])

    assert result["heat_risk"] == "HIGH"
    assert result["stage"] == "flowering"
    assert result["threshold_c"] == 31.0


def test_assess_window_crossing_into_heat_stage():
    # Day 91 is not sensitive, day 92 starts flowering.
    result = assess_heat_risk(91, [36.0, 36.0, 20.0])

    assert result["heat_risk"] == "HIGH"
    assert result["hot_days"] == [92]


def test_assess_outside_heat_windows():
    result = assess_heat_risk(40, [40.0, 40.0, 40.0])

    assert result["heat_risk"] == "LOW"
    assert result["reason_code"] == "STAGE_NOT_HEAT_SENSITIVE"


def test_assess_only_looks_at_forecast_window():
    # Default window is 3 days; the hot 4th day is ignored.
    result = assess_heat_risk(95, [30.0, 30.0, 30.0, 40.0])

    assert result["heat_risk"] == "LOW"

    result = assess_heat_risk(95, [30.0, 30.0, 30.0, 40.0], window_days=4)

    assert result["heat_risk"] == "HIGH"


def test_assess_consecutive_days_required():
    tmax = [32.0, 30.0, 32.0]

    assert assess_heat_risk(95, tmax, consecutive_days_required=1)["heat_risk"] == "HIGH"
    assert assess_heat_risk(95, tmax, consecutive_days_required=2)["heat_risk"] == "LOW"
    assert assess_heat_risk(95, [32.0, 32.0, 30.0], consecutive_days_required=2)["heat_risk"] == "HIGH"


def test_assess_without_forecast():
    result = assess_heat_risk(95, [])

    assert result["heat_risk"] == "UNKNOWN"
    assert result["reason_code"] == "NO_FORECAST_DATA"
