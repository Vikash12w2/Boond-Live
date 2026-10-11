import pytest

import engine.kc as kc_module
from engine.kc import get_kc, get_season_length, get_stage, get_wheat_stage


@pytest.mark.parametrize(
    "day, stage, kc",
    [
        (1, "initial", 0.30),
        (15, "initial", 0.30),
        # FAO-56 Eq. 66: (16 - 15) / 25 of the way from 0.30 to 1.15.
        (16, "development", 0.334),
        (20, "development", 0.470),
        (40, "development", 1.15),
        (41, "mid", 1.15),
        (90, "mid", 1.15),
        # (91 - 90) / 30 of the way from 1.15 to 0.40.
        (91, "late", 1.125),
        (120, "late", 0.40),
        (121, "post_harvest", 0.0),
    ],
)
def test_fao56_wheat_stage_and_kc(day, stage, kc):
    assert get_stage(day, "wheat_fao56") == stage
    assert get_kc(day, "wheat_fao56") == pytest.approx(kc, abs=1e-3)


@pytest.mark.parametrize(
    "day, stage, kc",
    [
        # DATA_GUIDE 4.2: days 1, 25, 72 and 145 of Punjab wheat
        # (24/44/47/30 days, Kc 0.40 / 1.15 / 0.30).
        (1, "initial", 0.40),
        (24, "initial", 0.40),
        (25, "development", 0.40 + 1 / 44 * 0.75),
        (68, "development", 1.15),
        (72, "mid", 1.15),
        (115, "mid", 1.15),
        (116, "late", 1.15 - 1 / 30 * 0.85),
        (145, "late", 0.30),
        (146, "post_harvest", 0.0),
    ],
)
def test_punjab_wheat_stage_and_kc(day, stage, kc):
    assert get_wheat_stage(day) == stage
    assert get_kc(day) == pytest.approx(kc)


def test_season_lengths_match_total_days():
    assert get_season_length("wheat") == 145
    assert get_season_length("wheat_late") == 133
    assert get_season_length("paddy") == 110
    assert get_season_length("sugarcane") == 360


def test_day_zero_is_rejected():
    with pytest.raises(ValueError):
        get_wheat_stage(0)


def test_one_day_stage_does_not_divide_by_zero(monkeypatch):
    crop = {
        "stages": {
            "initial": {"days": 2, "kc_start": 0.5, "kc_end": 0.5},
            "development": {"days": 1, "kc_start": 0.5, "kc_end": 1.0},
            "mid": {"days": 2, "kc_start": 1.0, "kc_end": 1.0},
            "late": {"days": 1, "kc_start": 1.0, "kc_end": 0.6},
        },
    }
    monkeypatch.setattr(kc_module, "get_crop", lambda crop_name="wheat": crop)

    assert get_stage(3, "test") == "development"
    assert get_kc(3, "test") == pytest.approx(1.0)
    assert get_kc(6, "test") == pytest.approx(0.6)
