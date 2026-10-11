import pytest

from engine.paddy import decide_paddy, update_paddy_day


LOW_HEAT = {"heat_risk": "LOW"}


def state(pond=0.0, depletion=0.0, dry_days=0):
    return {"pond_mm": pond, "depletion_mm": depletion, "dry_days": dry_days}


def test_pond_loses_percolation_and_etc():
    # Paddy Kc ini 1.05: ETc = 5.25 mm. Loam percolation 5 mm/day.
    new_state, details = update_paddy_day(1, "loam", 5.0, 0.0, 0.0, state(pond=50.0))

    assert details["percolation_mm"] == 5.0
    assert details["actual_etc_mm"] == pytest.approx(5.25)
    assert new_state["pond_mm"] == pytest.approx(39.75)
    assert new_state["dry_days"] == 0


def test_percolation_depends_on_soil():
    sandy, _ = update_paddy_day(1, "sandy", 5.0, 0.0, 0.0, state(pond=50.0))
    clay, _ = update_paddy_day(1, "clay", 5.0, 0.0, 0.0, state(pond=50.0))

    assert sandy["pond_mm"] == pytest.approx(50.0 - 8.0 - 5.25)
    assert clay["pond_mm"] == pytest.approx(50.0 - 2.0 - 5.25)


def test_rain_overflows_the_bund():
    new_state, details = update_paddy_day(1, "loam", 5.0, 120.0, 0.0, state(pond=50.0))

    assert new_state["pond_mm"] == 100.0
    assert details["overflow_mm"] == pytest.approx(50.0 + 120.0 - 5.0 - 5.25 - 100.0)


def test_rain_refills_the_soil_before_the_pond():
    new_state, details = update_paddy_day(30, "loam", 5.0, 20.0, 0.0, state(depletion=8.0, dry_days=3))

    # Day 30: Kc = 1.05 + 8/22 x 0.15. 8 mm refills the soil,
    # 12 mm reaches the pond, 5 mm percolates, then ETc.
    etc = 5.0 * (1.05 + 8 / 22 * 0.15)

    assert details["actual_etc_mm"] == pytest.approx(etc)
    assert new_state["depletion_mm"] == 0.0
    assert new_state["pond_mm"] == pytest.approx(12.0 - 5.0 - etc)
    assert new_state["dry_days"] == 0


def test_soil_dries_once_the_pond_has_gone():
    new_state, details = update_paddy_day(30, "loam", 5.0, 0.0, 0.0, state(pond=0.0, dry_days=1))

    assert new_state["pond_mm"] == 0.0
    assert new_state["depletion_mm"] > 0.0
    assert new_state["dry_days"] == 2
    assert details["percolation_mm"] == 0.0


def test_irrigate_two_days_after_the_pond_disappears():
    # Day 30 is after the 14 days of continuous ponding.
    assert decide_paddy(30, state(dry_days=1), [0, 0, 0], 0.1, LOW_HEAT)["action"] == "WAIT"

    result = decide_paddy(30, state(depletion=10.0, dry_days=2), [0, 0, 0], 0.1, LOW_HEAT)

    assert result["action"] == "IRRIGATE"
    assert result["reason_code"] == "POND_GONE_2_DAYS"
    assert result["depth_mm"] == 85.0


def test_irrigation_depth_is_capped_at_10_cm():
    result = decide_paddy(30, state(depletion=40.0, dry_days=5), [0, 0, 0], 0.1, LOW_HEAT)

    assert result["depth_mm"] == 100.0


def test_confident_rain_skips_paddy_irrigation():
    result = decide_paddy(30, state(dry_days=2), [80, 0, 0], [0.9, 0.1, 0.1], LOW_HEAT)

    assert result["action"] == "SKIP"

    result = decide_paddy(30, state(dry_days=2), [80, 0, 0], [0.4, 0.1, 0.1], LOW_HEAT)

    assert result["action"] == "IRRIGATE"


def test_paddy_does_not_wait_for_rain_after_tomorrow():
    # PAU allows 2 dry days; rain on day 2-3 of the forecast must not delay irrigation.
    result = decide_paddy(30, state(dry_days=2), [0, 80, 80], [0.1, 0.9, 0.9], LOW_HEAT)

    assert result["action"] == "IRRIGATE"


def test_no_irrigation_after_stop_day():
    result = decide_paddy(96, state(dry_days=5), [0, 0, 0], 0.1, LOW_HEAT)

    assert result["action"] == "WAIT"
    assert result["reason_code"] == "IRRIGATION_STOPPED"


def test_heat_keeps_5_cm_standing_water():
    result = decide_paddy(80, state(pond=30.0), [0, 0, 0], 0.1, {"heat_risk": "HIGH"})

    assert result["action"] == "HEAT_PROTECTION"
    assert result["depth_mm"] == 20.0

    result = decide_paddy(80, state(pond=60.0), [0, 0, 0], 0.1, {"heat_risk": "HIGH"})

    assert result["action"] == "WAIT"
