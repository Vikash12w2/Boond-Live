from engine.advisor import calculate_irrigation_depth


def test_refills_current_depletion():
    assert calculate_irrigation_depth(current_depletion=55.0, maximum_depth=60.0) == 55.0


def test_small_need_is_rounded_up_to_the_minimum_flood_depth():
    # config irrigation.minimum_advised_depth_mm = 40
    assert calculate_irrigation_depth(current_depletion=18.0, maximum_depth=60.0) == 40.0
    assert calculate_irrigation_depth(18.0, maximum_depth=60.0, minimum_depth=0.0) == 18.0


def test_minimum_never_exceeds_the_maximum():
    assert calculate_irrigation_depth(18.0, maximum_depth=30.0) == 30.0


def test_capped_at_maximum_depth():
    assert calculate_irrigation_depth(current_depletion=75.0, maximum_depth=60.0) == 60.0


def test_full_root_zone_needs_nothing():
    assert calculate_irrigation_depth(current_depletion=0.0, maximum_depth=60.0) == 0.0


def test_maximum_depth_defaults_to_config():
    # config.json irrigation.maximum_depth_mm = 75 (PAU 7.5 cm)
    assert calculate_irrigation_depth(current_depletion=90.0) == 75.0
