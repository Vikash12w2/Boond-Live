from engine.water_balance import update_depletion


def test_excess_water_becomes_deep_percolation():
    depletion, deep_percolation = update_depletion(
        previous_depletion=20.0,
        effective_rain=50.0,
        irrigation=0.0,
        actual_etc=5.0,
        taw=90.0
    )

    assert depletion == 0.0
    assert deep_percolation == 25.0