import pytest

from engine.water_balance import (
    get_p_table,
    get_root_depth,
    calculate_taw,
    calculate_p,
    calculate_raw,
    calculate_kc_etc,
    calculate_ks,
    calculate_actual_etc,
    effective_rainfall,
    update_depletion
)


def test_root_depth_grows_to_one_metre_and_stops():
    # Punjab wheat: 0.30 m on day 1, 1.0 m from day 68.
    assert get_root_depth(1) == pytest.approx(0.30)
    assert get_root_depth(20) == pytest.approx(0.30 + 19 / 67 * 0.70)
    assert get_root_depth(68) == pytest.approx(1.0)
    # Punjab spring wheat: 1.0 m, not the 1.5 m winter-wheat value.
    assert get_root_depth(145) == pytest.approx(1.0)


def test_root_depth_for_other_crops():
    assert get_root_depth(44, "paddy") == pytest.approx(0.50)
    assert get_root_depth(1, "sugarcane_ratoon") == pytest.approx(0.60)
    assert get_root_depth(200, "sugarcane") == pytest.approx(1.20)


@pytest.mark.parametrize(
    "soil, taw",
    [
        # The three soils in the form.
        ("sandy", 90.0),
        ("loam", 130.0),
        ("clay", 120.0),
        # Extra texture classes.
        ("loamy_sand", 85.0),
        ("sandy_loam", 120.0),
        ("silt_loam", 140.0),
        ("silty_clay_loam", 130.0),
        ("black_vertisol", 180.0),
    ],
)
def test_taw_per_metre_for_each_soil(soil, taw):
    assert calculate_taw(soil, 1.0) == pytest.approx(taw)


@pytest.mark.parametrize("soil", ["peat", "sand", "_meta", "_soilgrids_suggestion"])
def test_unknown_or_documentation_soil_raises(soil):
    with pytest.raises(ValueError):
        calculate_taw(soil, 1.0)


def test_p_adjustment_and_limits():
    assert calculate_p(5.0) == pytest.approx(0.55)
    assert calculate_p(5.75) == pytest.approx(0.52)
    assert calculate_p(-100.0) == 0.80
    assert calculate_p(100.0) == 0.10
    assert calculate_p(5.0, p_table=0.40) == pytest.approx(0.40)
    assert calculate_p(5.0, crop="cotton") == pytest.approx(0.65)


def test_p_by_stage_for_sugarcane():
    # FAO: ~0.30 during establishment, 0.65 afterwards.
    assert get_p_table("sugarcane", 10) == 0.30
    assert get_p_table("sugarcane", 100) == 0.65
    assert calculate_p(5.0, crop="sugarcane", day_after_sowing=10) == pytest.approx(0.30)


def test_stress_chain_on_day_40_loam():
    crop = "wheat_fao56"
    kc, etc = calculate_kc_etc(40, 5.0, crop)
    taw = calculate_taw("loam", get_root_depth(40, crop))
    p = calculate_p(etc, crop=crop)
    raw = calculate_raw(taw, p)

    assert kc == pytest.approx(1.15)
    assert etc == pytest.approx(5.75)
    assert raw == pytest.approx(67.6)

    # Within RAW: no stress.
    assert calculate_ks(45.0, taw, p) == 1.0

    # Past RAW: Ks falls linearly to 0 at TAW.
    ks = calculate_ks(100.0, taw, p)
    assert ks == pytest.approx(30.0 / 62.4)
    assert calculate_ks(taw, taw, p) == 0.0

    actual_etc = calculate_actual_etc(etc, ks)
    depletion, deep_percolation = update_depletion(100.0, 0.0, 0.0, actual_etc, taw)

    assert depletion == pytest.approx(100.0 + actual_etc)
    assert deep_percolation == 0.0


def test_effective_rainfall_ignores_light_rain():
    # 0.2 * ET0 = 1.0 mm
    assert effective_rainfall(0.9, 5.0) == 0.0
    assert effective_rainfall(1.0, 5.0) == 1.0
    assert effective_rainfall(12.0, 5.0) == 12.0


def test_negative_rain_is_rejected():
    with pytest.raises(ValueError):
        effective_rainfall(-1.0, 5.0)


def test_depletion_never_exceeds_taw():
    depletion, deep_percolation = update_depletion(88.0, 0.0, 0.0, 5.0, 90.0)

    assert depletion == 90.0
    assert deep_percolation == 0.0
