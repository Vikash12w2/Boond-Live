from engine.advisor import decide_irrigation_from_forecast


def make_balance(previous, actual_etc, raw):
    return {
        "previous_depletion_mm": previous,
        "actual_etc_mm": actual_etc,
        "raw_mm": raw
    }


def test_high_confidence_rain_prevents_irrigation():
    forecast = [
        make_balance(40.0, 5.0, 50.0),
        make_balance(45.0, 5.0, 50.0),
        make_balance(50.0, 5.0, 50.0),
    ]

    result = decide_irrigation_from_forecast(
        forecast_balances=forecast,
        future_rain=[0.0, 20.0, 0.0],
        rain_probability=[0.20, 0.90, 0.20]
    )

    assert result["action"] == "SKIP"
    assert result["reason_code"] == "RAINFALL_EXPECTED"


def test_low_confidence_rain_is_not_trusted():
    forecast = [
        make_balance(45.0, 5.0, 48.0),
        make_balance(50.0, 5.0, 48.0),
        make_balance(55.0, 5.0, 48.0),
    ]

    result = decide_irrigation_from_forecast(
        forecast_balances=forecast,
        future_rain=[20.0, 0.0, 0.0],
        rain_probability=[0.30, 0.20, 0.20]
    )

    assert result["action"] == "IRRIGATE"
    assert result["reason_code"] == "CROSSES_RAW_IN_2D"


def test_rain_after_raw_crossing_does_not_prevent_irrigation():
    forecast = [
        make_balance(46.0, 5.0, 48.0),
        make_balance(51.0, 5.0, 48.0),
        make_balance(56.0, 5.0, 48.0),
    ]

    result = decide_irrigation_from_forecast(
        forecast_balances=forecast,
        future_rain=[0.0, 0.0, 30.0],
        rain_probability=[0.20, 0.20, 0.90]
    )

    assert result["action"] == "IRRIGATE"
    assert result["crossing_day"] == 1


def test_high_confidence_rain_that_is_insufficient_does_not_skip():
    forecast = [
        make_balance(45.0, 5.0, 48.0),
        make_balance(49.0, 5.0, 48.0),
        make_balance(54.0, 5.0, 48.0),
    ]

    result = decide_irrigation_from_forecast(
        forecast_balances=forecast,
        future_rain=[0.0, 2.0, 0.0],
        rain_probability=[0.20, 0.90, 0.20]
    )

    assert result["action"] == "IRRIGATE"


def test_no_rain_behaves_normally():
    forecast = [
        make_balance(40.0, 5.0, 50.0),
        make_balance(45.0, 5.0, 50.0),
        make_balance(50.0, 5.0, 50.0),
    ]

    result = decide_irrigation_from_forecast(
        forecast_balances=forecast,
        future_rain=[0.0, 0.0, 0.0],
        rain_probability=[0.0, 0.0, 0.0]
    )

    assert result["action"] == "IRRIGATE"
    assert result["crossing_day"] == 2

def test_already_past_raw_with_rain_tomorrow_irrigates():
    # Bug 3: was SKIP.
    forecast = [
        make_balance(60.0, 5.0, 50.0),
        make_balance(65.0, 5.0, 50.0),
        make_balance(70.0, 5.0, 50.0),
    ]

    result = decide_irrigation_from_forecast(
        forecast_balances=forecast,
        future_rain=[30.0, 0.0, 0.0],
        rain_probability=[0.90, 0.10, 0.10]
    )

    assert result["action"] == "IRRIGATE"
    assert result["reason_code"] == "ALREADY_PAST_RAW"


def test_sixteen_day_forecast_uses_three_day_rain_window():
    # Bug 4: without rain RAW is crossed on day 2. Confident rain
    # on day 2 delays the crossing to day 6, so skip today.
    forecast = [make_balance(40.0, 5.0, 50.0)] * 16
    future_rain = [0.0, 20.0] + [0.0] * 14
    probability = [0.10, 0.90] + [0.10] * 14

    result = decide_irrigation_from_forecast(
        forecast_balances=forecast,
        future_rain=future_rain,
        rain_probability=probability
    )

    assert result["action"] == "SKIP"
    assert result["reason_code"] == "RAINFALL_EXPECTED"
    assert result["crossing_day"] == 2


def test_confident_rain_after_the_window_does_not_skip():
    forecast = [make_balance(40.0, 5.0, 50.0)] * 16
    future_rain = [0.0, 0.0, 0.0, 30.0] + [0.0] * 12
    probability = [0.10, 0.10, 0.10, 0.90] + [0.10] * 12

    result = decide_irrigation_from_forecast(
        forecast_balances=forecast,
        future_rain=future_rain,
        rain_probability=probability
    )

    assert result["action"] == "IRRIGATE"
    assert result["crossing_day"] == 2


def test_missing_probability_is_not_trusted():
    forecast = [
        make_balance(40.0, 5.0, 50.0),
        make_balance(45.0, 5.0, 50.0),
        make_balance(50.0, 5.0, 50.0),
    ]

    result = decide_irrigation_from_forecast(
        forecast_balances=forecast,
        future_rain=[0.0, 20.0, 0.0],
        rain_probability=[None, None, None]
    )

    assert result["action"] == "IRRIGATE"


def test_light_forecast_rain_follows_the_0_2_et0_rule():
    # Bug 10: 1.5 mm is below 0.2 * ET0 = 2 mm, so it is not
    # effective and cannot delay the crossing.
    forecast = [
        {
            "previous_depletion_mm": 40.0,
            "actual_etc_mm": 5.0,
            "potential_etc_mm": 5.0,
            "raw_mm": 50.0,
            "taw_mm": 100.0,
            "p": 0.5,
            "et0_mm": 10.0,
        }
    ] * 3

    result = decide_irrigation_from_forecast(
        forecast_balances=forecast,
        future_rain=[0.0, 1.5, 0.0],
        rain_probability=[0.90, 0.90, 0.90]
    )

    assert result["action"] == "IRRIGATE"
    assert result["crossing_day"] == 2


def test_empty_forecast():
    result = decide_irrigation_from_forecast(
        forecast_balances=[],
        future_rain=[],
        rain_probability=[]
    )

    assert result["action"] == "WAIT"
    assert result["reason_code"] == "NO_FORECAST_DATA"
