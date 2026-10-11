from engine.water_balance import calculate_ks, calculate_actual_etc


def test_fao56_example_37():
    """
    Reproduce the daily soil-water-stress calculation
    from FAO-56 Example 37.

    Source:
    FAO-56, Chapter 8, Example 37.
    """

    # FAO-56 Example 37 inputs
    taw = 160.0
    p = 0.40
    raw = 64.0

    et0 = 5.0
    kc = 1.2
    potential_etc = et0 * kc

    depletion = 55.0

    expected_depletion = [
        61.0,
        67.0,
        72.8,
        78.3,
        83.4,
        88.2,
        92.6,
        96.9,
        100.8,
        104.5,
    ]

    expected_ks = [
        1.00,
        1.00,
        0.97,
        0.91,
        0.85,
        0.80,
        0.75,
        0.70,
        0.66,
        0.62,
    ]

    for day in range(10):
        ks = calculate_ks(
            depletion=depletion,
            taw=taw,
            p=p
        )

        actual_etc = calculate_actual_etc(
            potential_etc,
            ks
        )

        depletion = depletion + actual_etc

        assert round(ks, 2) == expected_ks[day]
        assert round(depletion, 1) == expected_depletion[day]

    assert raw == 64.0
    assert taw == 160.0