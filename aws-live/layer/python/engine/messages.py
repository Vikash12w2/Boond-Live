"""
Turn an engine decision into the farmer-facing sentence.

    from engine.messages import render
    render(generate_daily_decision(...), "hi")

Depths are shown in whole millimetres (farmers cannot apply 0.3 mm),
and every message ends with the decision-support footer (spec 11).
"""

import re

from engine.data import load_json


LANGUAGES = ("en", "hi")

# Shown as whole numbers in the message.
WHOLE_NUMBER_KEYS = ("depth_mm", "gross_depth_mm")


def _format_number(value):
    """
    40.0 -> "40", 36.4 -> "36.4": the farmer sees whole numbers
    where possible.
    """
    if isinstance(value, float):
        value = round(value, 1)
        return str(int(value)) if value.is_integer() else str(value)

    return value


def _display_values(result):
    values = {key: _format_number(value) for key, value in result.items()}

    for key in WHOLE_NUMBER_KEYS:
        if isinstance(result.get(key), (int, float)):
            values[key] = str(int(round(result[key])))

    return values


def _stage_text(messages, stage, lang):
    if not stage:
        return ""

    return messages["stages"].get(stage, {}).get(lang, stage)


def render(result, lang="hi", footer=True):
    """
    result is the dict returned by generate_daily_decision or
    generate_daily_decision_paddy.
    """
    if lang not in LANGUAGES:
        raise ValueError(f"Unknown language: {lang}")

    messages = load_json("messages.json")
    reason_code = result["reason_code"]

    if reason_code not in messages["reasons"]:
        raise ValueError(f"No message for reason code: {reason_code}")

    values = _display_values(result)
    values["heat_stage"] = _stage_text(messages, result.get("heat_stage"), lang)
    values["critical_stage"] = _stage_text(messages, result.get("critical_stage"), lang)

    text = messages["reasons"][reason_code][lang].format(**values)

    if footer:
        text = f"{text} {messages['footer'][lang]}"

    return text


def allowed_numbers(result):
    """
    Every number a correct message may contain: the values in the
    engine result as rendered (whole-mm depths, 1-decimal values)
    plus the numbers fixed in the templates. Use it to validate a
    Bedrock rewrite: reject the rewrite if it contains any other
    number (spec 8).
    """
    messages = load_json("messages.json")
    allowed = {str(number) for number in messages["fixed_numbers"]}

    for value in _display_values(result).values():
        if isinstance(value, str) and re.fullmatch(r"\d+(\.\d+)?", value):
            allowed.add(value)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            allowed.add(str(value))

    return allowed


def numbers_in(text):
    """All numbers written in a message (ASCII digits)."""
    return set(re.findall(r"\d+(?:\.\d+)?", text))
