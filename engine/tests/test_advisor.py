import pytest

from engine.advisor import decide_irrigation


@pytest.mark.parametrize(
    "current_depletion, future_rain, rain_probability, action, crossing_day, reason_code",
    [
        # Healthy now, but reaches RAW on day 3: reassess tomorrow.
        (20.0, [0.0, 0.0, 0.0], 0.0, "WAIT", 3, "CROSSES_RAW_LATER"),
        # Needs irrigation soon.
        (30.0, [0.0, 0.0, 0.0], 0.0, "IRRIGATE", 1, "CROSSES_RAW_IN_2D"),
        # Rain is expected, but RAW is reached tomorrow, before the rain.
        (30.0, [0.0, 10.0, 0.0], 0.90, "IRRIGATE", 1, "CROSSES_RAW_IN_2D"),
        # Rain is uncertain, so it is not trusted.
        (30.0, [0.0, 10.0, 0.0], 0.40, "IRRIGATE", 1, "CROSSES_RAW_IN_2D"),
        # Rain arrives before the RAW crossing.
        (25.0, [0.0, 15.0, 0.0], 0.90, "SKIP", 2, "RAINFALL_EXPECTED"),
        # Rain arrives after the RAW crossing.
        (30.0, [0.0, 0.0, 15.0], 0.90, "IRRIGATE", 1, "CROSSES_RAW_IN_2D"),
    ],
    ids=[
        "healthy_field",
        "irrigation_needed",
        "rain_expected_too_late",
        "uncertain_rain",
        "rain_before_raw_crossing",
        "rain_after_raw_crossing",
    ],
)
def test_decide_irrigation_scenarios(
    current_depletion,
    future_rain,
    rain_probability,
    action,
    crossing_day,
    reason_code
):
    result = decide_irrigation(
        current_depletion=current_depletion,
        raw=35.0,
        future_etc=[5.0, 5.0, 5.0],
        future_rain=future_rain,
        rain_probability=rain_probability
    )

    assert result == {
        "action": action,
        "crossing_day": crossing_day,
        "reason_code": reason_code
    }


def test_no_crossing_is_healthy():
    result = decide_irrigation(
        current_depletion=10.0,
        raw=35.0,
        future_etc=[5.0, 5.0, 5.0],
        future_rain=[0.0, 0.0, 0.0],
        rain_probability=0.0
    )

    assert result["action"] == "WAIT"
    assert result["reason_code"] == "HEALTHY_WATER_BALANCE"
    assert result["crossing_day"] is None


def test_already_past_raw_irrigates_even_with_rain_tomorrow():
    # Bug 3: the root zone is already stressed today.
    result = decide_irrigation(
        current_depletion=60.0,
        raw=50.0,
        future_etc=[5.0, 5.0, 5.0],
        future_rain=[30.0, 0.0, 0.0],
        rain_probability=0.90
    )

    assert result["action"] == "IRRIGATE"
    assert result["reason_code"] == "ALREADY_PAST_RAW"
    assert result["crossing_day"] == 0


def test_per_day_probability_list_is_accepted():
    result = decide_irrigation(
        current_depletion=25.0,
        raw=35.0,
        future_etc=[5.0, 5.0, 5.0],
        future_rain=[0.0, 15.0, 0.0],
        rain_probability=[0.1, 0.9, 0.1]
    )

    assert result["action"] == "SKIP"


def test_missing_probability_is_not_trusted():
    result = decide_irrigation(
        current_depletion=25.0,
        raw=35.0,
        future_etc=[5.0, 5.0, 5.0],
        future_rain=[0.0, 15.0, 0.0],
        rain_probability=None
    )

    assert result["action"] == "IRRIGATE"


def test_mismatched_lengths_raise():
    with pytest.raises(ValueError):
        decide_irrigation(
            current_depletion=25.0,
            raw=35.0,
            future_etc=[5.0, 5.0, 5.0],
            future_rain=[0.0, 15.0],
            rain_probability=0.9
        )
