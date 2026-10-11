from datetime import date

import pytest

from engine.checkins import apply_checkins, rain_mm, watered_mm
from engine.data import crop_names, farmer_soil_choices, max_advised_depth, select_profile


def test_watered_levels_use_the_crops_depths():
    assert watered_mm("light") == 50.0
    assert watered_mm("Normal") == 75.0
    assert watered_mm("heavy", "paddy") == 100.0


def test_rain_levels_use_imd_anchored_values():
    assert rain_mm("little") == 8.0
    assert rain_mm("moderate") == 30.0
    assert rain_mm("heavy") == 65.0


def test_unknown_level_raises():
    with pytest.raises(ValueError):
        watered_mm("flood")


def test_rain_checkin_replaces_gridded_rain():
    rain, irrigation = apply_checkins(12.0, [{"type": "RAIN", "level": "moderate"}])

    assert rain == 30.0
    assert irrigation == 0.0


def test_watered_checkins_add_up_and_keep_gridded_rain():
    rain, irrigation = apply_checkins(
        3.0,
        [{"type": "WATERED", "level": "normal"}, {"type": "WATERED", "level": "light"}],
    )

    assert rain == 3.0
    assert irrigation == 125.0


@pytest.mark.parametrize(
    "crop, sowing_date, extra, profile",
    [
        ("wheat", date(2021, 11, 5), {}, "wheat"),
        ("wheat", date(2021, 11, 21), {}, "wheat"),
        ("wheat", date(2021, 11, 22), {}, "wheat_late"),
        ("wheat", date(2021, 12, 31), {}, "wheat_late"),
        ("wheat", "2022-01-05", {}, "wheat_january"),
        ("wheat", date(2022, 2, 10), {}, "wheat_january"),
        ("paddy", date(2021, 6, 25), {}, "paddy"),
        ("paddy", date(2021, 6, 25), {"variety": "PR 126"}, "paddy_short"),
        ("sugarcane", date(2021, 3, 1), {}, "sugarcane"),
        ("sugarcane", date(2021, 3, 1), {"ratoon": True}, "sugarcane_ratoon"),
        ("sugarcane", date(2021, 7, 31), {}, "sugarcane"),
        ("sugarcane", date(2021, 8, 1), {}, "sugarcane_autumn"),
        ("sugarcane", date(2021, 10, 5), {}, "sugarcane_autumn"),
        ("sugarcane", date(2021, 10, 5), {"ratoon": True}, "sugarcane_ratoon"),
        ("sugarcane", date(2022, 1, 20), {}, "sugarcane"),
        ("cotton", date(2021, 5, 1), {}, "cotton"),
    ],
)
def test_select_profile(crop, sowing_date, extra, profile):
    assert select_profile(crop, sowing_date, **extra) == profile


def test_documentation_keys_are_not_crops_or_soils():
    assert "_meta" not in crop_names()
    assert farmer_soil_choices() == ["sandy", "loam", "clay"]


def test_crop_depth_caps():
    assert max_advised_depth("wheat") == 75
    assert max_advised_depth("paddy") == 100
