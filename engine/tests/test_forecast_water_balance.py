from engine.water_balance import forecast_water_balance


def test_forecast_recalculates_daily_water_balance():

    predictions = forecast_water_balance(
        start_day_after_sowing=40,
        soil="loam",
        future_et0=[5.0, 5.0, 5.0],
        future_rain=[0.0, 0.0, 0.0],
        initial_depletion=35.75,
        crop="wheat_fao56"
    )

    assert len(predictions) == 3

    # Tomorrow starts from today's depletion.
    assert predictions[0]["previous_depletion_mm"] == 35.75

    # With Kc = 1.15 at this stage:
    # ETc = 1.15 * 5 = 5.75 mm
    assert predictions[0]["potential_etc_mm"] == 5.75

    assert predictions[0]["depletion_mm"] == 41.5
    assert predictions[1]["depletion_mm"] == 47.25
    assert predictions[2]["depletion_mm"] == 53.0