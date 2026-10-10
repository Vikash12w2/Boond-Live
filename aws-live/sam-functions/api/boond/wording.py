"""Farmer-facing text: the engine's template, optionally reworded by Bedrock.

A rewrite is used only if it is faithful: every number in it comes from the
engine result, it spells no number out in words, Hindi text is in Devanagari,
and it is 1-300 characters. Otherwise the template is used. Accepted rewrites
keep the engine's decision-support footer.
"""
import logging
import re

from engine.data import load_json
from engine.messages import allowed_numbers, numbers_in, render

log = logging.getLogger(__name__)

MAX_CHARS = 300

_EN_WORDS = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
             "sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred "
             "thousand lakh dozen half double twice").split()
_HI_WORDS = ("शून्य एक दो तीन चार पाँच पांच छह छः सात आठ नौ दस ग्यारह बारह तेरह चौदह पंद्रह सोलह सत्रह अठारह "
             "उन्नीस बीस पच्चीस तीस चालीस पचास बावन साठ सत्तर अस्सी नब्बे सौ हज़ार हजार लाख आधा दुगना दोगुना").split()

# Number words a rewrite could use to slip a value past the digit check. Hindi
# words must stand alone: "एक" inside "एकड़" (acre) or "सात" inside "बरसात" (rain)
# is not a number. Python's \b breaks inside Devanagari at vowel signs, so the
# Hindi pattern uses explicit Devanagari-block lookarounds instead.
NUMBER_WORDS = {
    "en": re.compile(r"\b(" + "|".join(_EN_WORDS) + r")\b", re.IGNORECASE),
    "hi": re.compile(r"(?<![ऀ-ॿ])(" + "|".join(_HI_WORDS) + r")(?![ऀ-ॿ])"),
}

SYSTEM = (
    "You reword irrigation advice for a farmer. Keep the meaning exactly. Use only the numbers that appear "
    "in the advice, written as digits 0-9. Never write a number as a word. At most two short sentences. "
    "Reply with the reworded advice only, in the same language as the advice."
)


# Shown and sent when no advice could be made today (weather missing). Engine Design Doc,
# "When data is missing or late": tell the farmer rather than advise on a gap.
UNAVAILABLE_TEXT = {
    "hi": "आज की सलाह नहीं बन सकी: मौसम की जानकारी नहीं मिली। पानी देने से पहले खेत की नमी खुद जाँच लें।",
    "en": "Today's advice could not be made: weather data did not arrive. Please check the soil yourself before irrigating.",
}


def template_texts(advice):
    return {lang: render(advice, lang) for lang in ("hi", "en")}


def _devanagari_share(text):
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for ch in letters if "ऀ" <= ch <= "ॿ") / len(letters)


def is_faithful(text, advice, lang):
    text = (text or "").strip()
    if not 1 <= len(text) <= MAX_CHARS:
        return False
    found = numbers_in(text)
    if not found <= allowed_numbers(advice):
        return False
    if advice.get("action") in ("IRRIGATE", "HEAT_PROTECTION") and str(round(advice.get("depth_mm") or 0)) not in found:
        return False  # the depth is the one number the farmer acts on
    if NUMBER_WORDS[lang].search(text):
        return False
    if lang == "hi" and _devanagari_share(text) < 0.8:
        return False
    return True


class Rewriter:
    def __init__(self, bedrock, model_id):
        self.bedrock, self.model_id = bedrock, model_id

    def rewrite(self, advice, lang):
        template = render(advice, lang)
        if not self.bedrock or not self.model_id:
            return template, "template"
        try:
            response = self.bedrock.converse(
                modelId=self.model_id,
                system=[{"text": SYSTEM}],
                messages=[{"role": "user", "content": [{"text": render(advice, lang, footer=False)}]}],
                inferenceConfig={"maxTokens": 200, "temperature": 0.2},
            )
            text = response["output"]["message"]["content"][0]["text"].strip()
        except Exception as error:  # any Bedrock failure falls back to the template
            log.warning("bedrock rewrite failed: %s", error)
            return template, "template"
        if is_faithful(text, advice, lang):
            return f"{text} {load_json('messages.json')['footer'][lang]}", "bedrock"
        log.info("bedrock rewrite rejected by validation")
        return template, "template"
