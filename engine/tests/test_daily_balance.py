import pytest

from engine.water_balance import calculate_daily_balance


def test_healthy_field():
    # FAO-56 spring wheat profile, day 40, loam: root depth 1.0 m, TAW = 130 mm,
    # Kc = 1.15, ETc = 5.75 mm, p = 0.52, RAW = 67.6 mm.
    result = calculate_daily_balance(
        day_after_sowing=40,
        soil="loam",
        et0=5.0,
        rain=10.0,
        irrigation=0.0,
        previous_depletion=20.0,
        crop="wheat_fao56"
    )

    assert result["root_depth_m"] == pytest.approx(1.0)
    assert result["taw_mm"] == pytest.approx(130.0)
    assert result["kc"] == pytest.approx(1.15)
    assert result["p"] == pytest.approx(0.52)
    assert result["raw_mm"] == pytest.approx(67.6)
    assert result["ks"] == 1.0
    assert result["effective_rain_mm"] == 10.0

    # 20 - 10 + 5.75
    assert result["depletion_mm"] == pytest.approx(15.75)
    assert result["deep_percolation_mm"] == 0.0


def test_stressed_field():
    result = calculate_daily_balance(
        day_after_sowing=40,
        soil="loam",
        et0=5.0,
        rain=0.0,
        irrigation=0.0,
        previous_depletion=100.0,
        crop="wheat_fao56"
    )

    # Ks = (130 - 100) / ((1 - 0.52) * 130)
    expected_ks = 30.0 / 62.4

    assert result["ks"] == pytest.approx(expected_ks)
    assert result["actual_etc_mm"] == pytest.approx(5.75 * expected_ks)
    assert result["depletion_mm"] == pytest.approx(100.0 + 5.75 * expected_ks)


def test_irrigation_refills_and_excess_percolates():
    result = calculate_daily_balance(
        day_after_sowing=40,
        soil="loam",
        et0=5.0,
        rain=0.0,
        irrigation=60.0,
        previous_depletion=40.0,
        crop="wheat_fao56"
    )

    assert result["depletion_mm"] == 0.0
    assert result["deep_percolation_mm"] == pytest.approx(60.0 - 40.0 - 5.75)


def test_carried_depletion_is_capped_at_todays_taw():
    result = calculate_daily_balance(
        day_after_sowing=40,
        soil="loam",
        et0=5.0,
        rain=0.0,
        irrigation=0.0,
        previous_depletion=500.0,
        crop="wheat_fao56"
    )

    assert result["previous_depletion_mm"] == pytest.approx(130.0)
    assert result["ks"] == 0.0
    assert result["depletion_mm"] == pytest.approx(130.0)
