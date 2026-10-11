import re
from pathlib import Path

import pytest

from engine.daily_engine import generate_daily_decision, generate_daily_decision_paddy
from engine.data import entries, load_json
from engine.messages import LANGUAGES, allowed_numbers, numbers_in, render


ENGINE = Path(__file__).resolve().parents[1]
ACTIONS = {"IRRIGATE", "WAIT", "SKIP", "HEAT_PROTECTION", "HIGH", "LOW"}


def reason_codes_in(source_file):
    text = (ENGINE / source_file).read_text()
    return set(re.findall(r'"([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)"', text)) - ACTIONS


def test_every_reason_code_has_english_and_hindi_text():
    codes = reason_codes_in("advisor.py") | reason_codes_in("paddy.py") | reason_codes_in("field_runner.py")
    reasons = load_json("messages.json")["reasons"]

    assert {"HEAT_RISK_SOIL_MOIST", "HEAT_RISK_RAIN_EXPECTED", "IRRIGATION_STOPPED", "NOT_SOWN_YET"} <= codes
    assert codes - set(reasons) == set()

    for code, text in reasons.items():
        assert set(text) == set(LANGUAGES), code


def test_every_heat_window_has_a_stage_name():
    stages = load_json("messages.json")["stages"]

    for crop in entries(load_json("crops.json")).values():
        for window in crop.get("heat_windows", []):
            assert set(stages[window["name"]]) == set(LANGUAGES)


def wheat_heat_day(**overrides):
    # Punjab wheat, day 95: days 96-98 are in the flowering window.
    inputs = {
        "day_after_sowing": 95,
        "soil": "loam",
        "et0": 5.0,
        "rain": 0.0,
        "irrigation": 0.0,
        "previous_depletion": 5.0,
        "future_et0": [5.0, 5.0, 5.0],
        "future_rain": [0.0, 0.0, 0.0],
        "rain_probability": 0.1,
        "forecast_tmax": [36.4, 35.0, 34.0],
        "area_acres": 1.0,
        "lift_m": 30.0,
    }
    inputs.update(overrides)

    return generate_daily_decision(**inputs)


def test_heat_on_moist_soil_message():
    result = wheat_heat_day()

    assert result["reason_code"] == "HEAT_RISK_SOIL_MOIST"
    assert render(result, "hi", footer=False) == (
        "गर्मी की चेतावनी: फूल आने के समय तापमान 36.4°C तक जा सकता है। "
        "मिट्टी में अभी नमी है, इसलिए आज सिंचाई न करें। बूंद कल फिर जाँच करेगा।"
    )
    assert render(result, "en").startswith("Heat alert: up to 36.4°C expected during flowering.")


def test_heat_with_rain_expected_message():
    result = wheat_heat_day(future_rain=[0.0, 20.0, 0.0], rain_probability=[0.1, 0.9, 0.1])

    assert result["reason_code"] == "HEAT_RISK_RAIN_EXPECTED"
    assert render(result, "hi", footer=False) == (
        "गर्मी की चेतावनी: फूल आने के समय तापमान 36.4°C तक जा सकता है, "
        "लेकिन अगले 3 दिनों में बारिश की संभावना है (20 मिमी का अनुमान)। "
        "गर्मी से बचाव के लिए सिंचाई की ज़रूरत नहीं है।"
    )


def test_heat_protection_message_shows_whole_mm():
    result = wheat_heat_day(previous_depletion=45.0)

    assert result["action"] == "HEAT_PROTECTION"
    assert "लगभग 40 मिमी हल्की सिंचाई करें" in render(result, "hi")


def test_paddy_message():
    result = generate_daily_decision_paddy(
        day_after_transplanting=30,
        soil="loam",
        et0=5.0,
        rain=0.0,
        irrigation=0.0,
        state={"pond_mm": 40.0, "depletion_mm": 0.0, "dry_days": 0},
        future_rain=[0.0, 0.0, 0.0],
        rain_probability=0.1,
        forecast_tmax=[30.0, 30.0, 30.0],
        area_acres=1.0,
        lift_m=30.0
    )

    assert result["reason_code"] == "POND_PRESENT"
    assert "खेत में अभी पानी खड़ा है" in render(result, "hi")


def test_unknown_language_or_code_raises():
    with pytest.raises(ValueError):
        render({"reason_code": "HEALTHY_WATER_BALANCE"}, "pa")

    with pytest.raises(ValueError):
        render({"reason_code": "NOT_A_CODE"}, "hi")


def test_every_message_ends_with_the_decision_support_footer():
    result = wheat_heat_day()

    assert render(result, "hi").endswith("यह सलाह है, अंतिम फैसला आपका है।")
    assert render(result, "en").endswith("This is advice; the final decision is yours.")


def test_depth_is_shown_in_whole_mm():
    result = wheat_heat_day(day_after_sowing=80, previous_depletion=67.4,
                            future_et0=[4.3, 4.3, 4.3], forecast_tmax=[25.0, 25.0, 25.0])

    assert result["action"] == "IRRIGATE"
    assert result["depth_mm"] != round(result["depth_mm"])
    assert f"लगभग {round(result['depth_mm'])} मिमी" in render(result, "hi")


def test_heat_irrigation_is_for_the_evening():
    result = wheat_heat_day(previous_depletion=45.0)

    assert "आज शाम लगभग 40 मिमी" in render(result, "hi")
    assert "this evening" in render(result, "en")


def test_critical_stage_message():
    result = wheat_heat_day(day_after_sowing=27, previous_depletion=10.0,
                            forecast_tmax=[22.0, 22.0, 22.0],
                            water_since_sowing_mm=0.0, sowing_date="2021-11-05")

    assert result["reason_code"] == "CRITICAL_STAGE_IRRIGATION"
    assert "शिखर जड़ (क्राउन रूट) बनने के समय लगभग 50 मिमी" in render(result, "hi")


def test_rendered_numbers_pass_the_bedrock_number_check():
    for result in (
        wheat_heat_day(),
        wheat_heat_day(previous_depletion=45.0),
        wheat_heat_day(day_after_sowing=80, previous_depletion=67.4,
                       future_et0=[4.3, 4.3, 4.3], forecast_tmax=[25.0, 25.0, 25.0]),
    ):
        for lang in LANGUAGES:
            assert numbers_in(render(result, lang)) <= allowed_numbers(result)


def test_bedrock_check_rejects_a_changed_amount():
    result = wheat_heat_day(previous_depletion=45.0)
    rewritten = render(result, "en").replace("40 mm", "45 mm")

    assert not numbers_in(rewritten) <= allowed_numbers(result)
