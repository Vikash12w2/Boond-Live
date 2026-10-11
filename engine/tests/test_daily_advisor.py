from engine.advisor import make_daily_decision


def test_healthy_field_waits():

    result = make_daily_decision(
        current_depletion=20,
        raw=35,
        future_etc=[5, 5, 5],
        future_rain=[0, 0, 0],
        rain_probability=0.20,
        heat_result={
            "heat_risk": "LOW"
        },
        maximum_depth=60
    )

    assert result["action"] == "WAIT"


def test_irrigation_needed():

    result = make_daily_decision(
        current_depletion=30,
        raw=35,
        future_etc=[5, 5, 5],
        future_rain=[0, 0, 0],
        rain_probability=0.20,
        heat_result={
            "heat_risk": "LOW"
        },
        maximum_depth=60
    )

    assert result["action"] == "IRRIGATE"
    # 30 mm need, rounded up to the 40 mm minimum flood depth.
    assert result["depth_mm"] == 40


def test_reliable_rain_causes_skip():

    result = make_daily_decision(
        current_depletion=25,
        raw=35,
        future_etc=[5, 5, 5],
        future_rain=[0, 15, 0],
        rain_probability=0.90,
        heat_result={
            "heat_risk": "LOW"
        },
        maximum_depth=60
    )

    assert result["action"] == "SKIP"


def test_uncertain_rain_does_not_cause_skip():

    result = make_daily_decision(
        current_depletion=30,
        raw=35,
        future_etc=[5, 5, 5],
        future_rain=[0, 15, 0],
        rain_probability=0.40,
        heat_result={
            "heat_risk": "LOW"
        },
        maximum_depth=60
    )

    assert result["action"] == "IRRIGATE"


def test_heat_protection_has_priority():

    result = make_daily_decision(
        current_depletion=45,
        raw=60,
        future_etc=[5, 5, 5],
        future_rain=[0, 0, 0],
        rain_probability=0.20,
        heat_result={
            "heat_risk": "HIGH"
        },
        maximum_depth=60
    )

    assert result["action"] == "HEAT_PROTECTION"
    # config irrigation.light_depth_mm
    assert result["depth_mm"] == 40


def test_heat_with_reliable_rain_does_not_trigger_protection():

    result = make_daily_decision(
        current_depletion=20,
        raw=35,
        future_etc=[5, 5, 5],
        future_rain=[0, 15, 0],
        rain_probability=0.90,
        heat_result={
            "heat_risk": "HIGH"
        },
        maximum_depth=60
    )

    assert result["action"] == "SKIP"

def test_heat_protection_accepts_per_day_probabilities():
    # Bug 2: a list of probabilities used to raise TypeError.
    result = make_daily_decision(
        current_depletion=45,
        raw=60,
        future_etc=[5, 5, 5],
        future_rain=[0, 0, 0],
        rain_probability=[0.1, 0.2, 0.1],
        heat_result={
            "heat_risk": "HIGH"
        },
        maximum_depth=60
    )

    assert result["action"] == "HEAT_PROTECTION"
    assert result["depth_mm"] == 40


def test_heat_protection_with_light_confident_rain():
    # 5 mm of confident rain is below the 10 mm that
    # counts as meaningful, so heat protection still applies.
    result = make_daily_decision(
        current_depletion=45,
        raw=60,
        future_etc=[5, 5, 5],
        future_rain=[0, 5, 0],
        rain_probability=[0.1, 0.9, 0.1],
        heat_result={
            "heat_risk": "HIGH"
        },
        maximum_depth=60
    )

    assert result["action"] == "HEAT_PROTECTION"


def test_heat_protection_is_at_least_the_full_refill():
    result = make_daily_decision(
        current_depletion=50,
        raw=55,
        future_etc=[5, 5, 5],
        future_rain=[0, 0, 0],
        rain_probability=0.1,
        heat_result={
            "heat_risk": "HIGH"
        },
        maximum_depth=60
    )

    assert result["action"] == "HEAT_PROTECTION"
    assert result["depth_mm"] == 50


def test_heat_protection_ignores_missing_probability():
    result = make_daily_decision(
        current_depletion=45,
        raw=60,
        future_etc=[5, 5, 5],
        future_rain=[0, 15, 0],
        rain_probability=None,
        heat_result={
            "heat_risk": "HIGH"
        },
        maximum_depth=60
    )

    assert result["action"] == "HEAT_PROTECTION"


def test_already_past_raw_irrigates_with_rain_forecast():
    result = make_daily_decision(
        current_depletion=40,
        raw=35,
        future_etc=[5, 5, 5],
        future_rain=[30, 0, 0],
        rain_probability=0.9,
        heat_result={
            "heat_risk": "LOW"
        },
        maximum_depth=60
    )

    assert result["action"] == "IRRIGATE"
    assert result["depth_mm"] == 40
    assert result["reason_code"] == "ALREADY_PAST_RAW"


def test_no_heat_irrigation_while_the_soil_is_still_wet():
    # 20 mm depletion has no room for a 40 mm light irrigation,
    # e.g. the day after a heat irrigation.
    result = make_daily_decision(
        current_depletion=20,
        raw=60,
        future_etc=[5, 5, 5],
        future_rain=[0, 0, 0],
        rain_probability=0.1,
        heat_result={
            "heat_risk": "HIGH"
        },
        maximum_depth=60
    )

    assert result["action"] == "WAIT"


def test_heat_on_moist_soil_waits_but_keeps_heat_reason():
    # Soil too wet for a 40 mm heat irrigation: no water, but the farmer is warned.
    result = make_daily_decision(
        current_depletion=10,
        raw=60,
        future_etc=[4, 4, 4],
        future_rain=[0, 0, 0],
        rain_probability=0.1,
        heat_result={"heat_risk": "HIGH"},
        maximum_depth=75
    )

    assert result["action"] == "WAIT"
    assert result["reason_code"] == "HEAT_RISK_SOIL_MOIST"


def test_heat_with_meaningful_rain_waits_with_heat_reason():
    result = make_daily_decision(
        current_depletion=10,
        raw=60,
        future_etc=[4, 4, 4],
        future_rain=[0, 20, 0],
        rain_probability=[0.1, 0.9, 0.1],
        heat_result={"heat_risk": "HIGH"},
        maximum_depth=75
    )

    assert result["action"] == "WAIT"
    assert result["reason_code"] == "HEAT_RISK_RAIN_EXPECTED"


def test_no_heat_keeps_normal_reason():
    result = make_daily_decision(
        current_depletion=10,
        raw=60,
        future_etc=[4, 4, 4],
        future_rain=[0, 0, 0],
        rain_probability=0.1,
        heat_result={"heat_risk": "LOW"},
        maximum_depth=75
    )

    assert result["reason_code"] == "HEALTHY_WATER_BALANCE"
