from engine.advisor import (
    predict_depletion,
    find_raw_crossing_day
)


def test_future_depletion_starts_after_today():

    current_depletion = 35.75

    future_etc = [
        5.75,  # tomorrow
        5.75,  # day +2
        5.75   # day +3
    ]

    future_rain = [
        0.0,
        0.0,
        0.0
    ]

    predictions = predict_depletion(
        current_depletion,
        future_etc,
        future_rain
    )

    assert predictions == [
        41.50,
        47.25,
        53.00
    ]


def test_raw_crossing_is_detected_from_tomorrow():

    current_depletion = 35.75
    raw = 46.87

    future_etc = [
        5.75,
        5.75,
        5.75
    ]

    crossing_day = find_raw_crossing_day(
        current_depletion,
        raw,
        future_etc
    )

    assert crossing_day == 2