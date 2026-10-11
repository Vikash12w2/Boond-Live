import pytest

from engine.daily_engine import generate_daily_decision, generate_daily_decision_paddy
from engine.paddy import initial_paddy_state


def run_engine(**overrides):
    # The FAO-56 120-day profile keeps the arithmetic easy to check.
    inputs = {
        "day_after_sowing": 40,
        "soil": "loam",
        "et0": 5.0,
        "rain": 0.0,
        "irrigation": 0.0,
        "previous_depletion": 30.0,
        "future_et0": [5.0, 5.0, 5.0],
        "future_rain": [0.0, 0.0, 0.0],
        "rain_probability": 0.20,
        "forecast_tmax": [28.0, 29.0, 30.0],
        "area_acres": 1.0,
        "lift_m": 30.0,
        "pump_efficiency": 0.40,
        "electricity_tariff": 8.0,
        "grid_factor": 0.70,
        "maximum_irrigation_depth": 60,
        "crop": "wheat_fao56",
    }
    inputs.update(overrides)

    return generate_daily_decision(**inputs)


def test_complete_daily_decision():
    result = run_engine()

    assert result["action"] == "WAIT"
    assert result["depth_mm"] == 0.0
    assert result["heat_risk"] == "LOW"

    # Bug 5: stage comes from the crop day, not the caller.
    assert result["stage"] == "development"
    assert result["heat_stage"] is None

    assert result["depletion_mm"] < result["raw_mm"]

    assert result["taw_mm"] > 0
    assert result["raw_mm"] > 0

    assert result["litres"] == 0.0
    assert result["volume_m3"] == 0.0
    assert result["kwh"] == 0.0
    assert result["cost_inr"] == 0.0
    assert result["co2_kg"] == 0.0


def test_heat_window_is_derived_from_crop_day():
    # Punjab wheat: days 96-98 are in the flowering window (31 C).
    result = run_engine(
        crop="wheat",
        day_after_sowing=95,
        previous_depletion=45.0,
        forecast_tmax=[36.0, 36.0, 36.0],
        maximum_irrigation_depth=None
    )

    assert result["stage"] == "mid"
    assert result["heat_stage"] == "flowering"
    assert result["heat_risk"] == "HIGH"
    assert result["action"] == "HEAT_PROTECTION"
    # config irrigation.light_depth_mm
    assert result["depth_mm"] == 40.0
    assert result["kwh"] > 0.0


def test_already_past_raw_irrigates_despite_rain_tomorrow():
    # Bug 3: today's depletion is already above RAW (67.6 mm).
    result = run_engine(
        day_after_sowing=60,
        previous_depletion=70.0,
        future_rain=[30.0, 0.0, 0.0],
        rain_probability=[0.9, 0.1, 0.1]
    )

    assert result["depletion_mm"] > result["raw_mm"]
    assert result["action"] == "IRRIGATE"
    assert result["reason_code"] == "ALREADY_PAST_RAW"
    assert result["depth_mm"] == 60.0


def test_sixteen_day_forecast_rain_skip():
    # Bug 4: without rain RAW is crossed on day 3; confident
    # rain on day 2 delays it to day 6, outside the 3-day window.
    future_rain = [0.0, 20.0] + [0.0] * 14
    probability = [0.1, 0.9] + [0.1] * 14

    result = run_engine(
        day_after_sowing=60,
        previous_depletion=50.0,
        future_et0=[5.0] * 16,
        future_rain=future_rain,
        rain_probability=probability,
        forecast_tmax=[25.0] * 16
    )

    assert result["action"] == "SKIP"
    assert result["reason_code"] == "RAINFALL_EXPECTED"
    assert result["crossing_day"] == 3
    assert result["rain_next_3d_mm"] == 20.0


def test_sandy_soil_from_form_is_accepted():
    result = run_engine(soil="sandy")

    assert result["taw_mm"] == pytest.approx(90.0)


def test_defaults_come_from_config_and_crop():
    result = run_engine(
        previous_depletion=70.0,
        pump_efficiency=None,
        electricity_tariff=None,
        grid_factor=None,
        maximum_irrigation_depth=None
    )

    assert result["action"] == "IRRIGATE"
    # Crop cap: irrigation.max_advised_depth_mm = 75 (PAU 7.5 cm).
    assert result["depth_mm"] == 75.0
    # Gross pumped depth = net / application_efficiency 0.70.
    assert result["gross_depth_mm"] == pytest.approx(75.0 / 0.70, abs=0.01)
    assert result["volume_m3"] == pytest.approx(75.0 / 0.70 * 4.0469, abs=0.001)
    assert result["cost_inr"] == pytest.approx(result["kwh"] * 8.0, abs=0.01)
    # CEA v22 grid factor, 0.675 kg CO2 per kWh.
    assert result["co2_kg"] == pytest.approx(result["kwh"] * 0.675, abs=0.001)


def test_paddy_daily_decision_keeps_the_pond_in_the_first_two_weeks():
    state = {"pond_mm": 25.0, "depletion_mm": 0.0, "dry_days": 0}

    result = generate_daily_decision_paddy(
        day_after_transplanting=5,
        soil="loam",
        et0=6.0,
        rain=0.0,
        irrigation=0.0,
        state=state,
        future_rain=[0.0, 0.0, 0.0],
        rain_probability=0.1,
        forecast_tmax=[34.0, 34.0, 34.0],
        area_acres=1.0,
        lift_m=30.0
    )

    # 25 - 5 percolation - 6.3 ETc = 13.7 mm, below 20 mm.
    assert result["pond_mm"] == pytest.approx(13.7)
    assert result["action"] == "IRRIGATE"
    assert result["reason_code"] == "KEEP_POND_FIRST_2_WEEKS"
    assert result["depth_mm"] == pytest.approx(75.0 - 13.7)
    assert result["state"]["pond_mm"] == pytest.approx(13.7)
    assert result["kwh"] > 0


def test_paddy_starts_flooded():
    assert initial_paddy_state()["pond_mm"] == 75.0
