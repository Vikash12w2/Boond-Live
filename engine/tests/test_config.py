import copy

import engine.data as data
from engine.advisor import make_daily_decision
from engine.water_balance import effective_rainfall


def patch_config(monkeypatch, section, key, value):
    config = copy.deepcopy(data.load_config())
    config[section][key] = value
    monkeypatch.setattr(data, "load_config", lambda: config)


def test_rain_threshold_ratio_comes_from_config(monkeypatch):
    assert effective_rainfall(1.5, 5.0) == 1.5

    patch_config(monkeypatch, "rain", "effective_threshold_ratio", 0.5)

    assert effective_rainfall(1.5, 5.0) == 0.0


def test_skip_probability_threshold_comes_from_config(monkeypatch):
    inputs = {
        "current_depletion": 25,
        "raw": 35,
        "future_etc": [5, 5, 5],
        "future_rain": [0, 15, 0],
        "rain_probability": 0.6,
        "heat_result": {"heat_risk": "LOW"},
    }

    assert make_daily_decision(**inputs)["action"] == "IRRIGATE"

    patch_config(monkeypatch, "rain", "skip_probability_threshold", 0.5)

    assert make_daily_decision(**inputs)["action"] == "SKIP"


def test_heat_depth_comes_from_config(monkeypatch):
    patch_config(monkeypatch, "irrigation", "light_depth_mm", 20)

    result = make_daily_decision(
        current_depletion=25,
        raw=60,
        future_etc=[5, 5, 5],
        future_rain=[0, 0, 0],
        rain_probability=0.1,
        heat_result={"heat_risk": "HIGH"}
    )

    assert result["depth_mm"] == 20


def test_check_data_rejects_the_unimplemented_kc_climate_adjustment(monkeypatch):
    from engine.check_data import check_config

    config = copy.deepcopy(data.load_config())
    assert check_config(config) == []

    config["kc_climate_adjustment"]["enabled"] = True

    assert any("kc_climate_adjustment" in problem for problem in check_config(config))
