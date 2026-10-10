from boond.wording import Rewriter, is_faithful, template_texts

ADVICE = {"action": "IRRIGATE", "depth_mm": 51.51, "reason_code": "CROSSES_RAW_IN_2D", "crossing_day": 2,
          "rain_next_3d_mm": 0.0, "max_forecast_tmax_c": 20.0, "heat_stage": None, "critical_stage": None,
          "warnings": []}


class FakeBedrock:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {"output": {"message": {"content": [{"text": self.reply}]}}}


def test_templates_in_both_languages_carry_the_depth():
    t = template_texts(ADVICE)
    assert "52" in t["en"] and "52" in t["hi"]


def test_faithful_rewrite_accepted():
    assert is_faithful("आज खेत में लगभग 52 मिमी पानी दें। 2 दिन में कमी होगी।", ADVICE, "hi")


def test_extra_number_rejected():
    assert not is_faithful("आज 60 मिमी पानी दें।", ADVICE, "hi")


def test_devanagari_digit_not_in_engine_output_rejected():
    assert not is_faithful("आज ५२ मिमी पानी दें।", ADVICE, "hi")


def test_number_words_rejected_in_both_languages():
    assert not is_faithful("आज बावन मिमी पानी दें।", ADVICE, "hi")
    assert not is_faithful("Irrigate about fifty two mm today.", ADVICE, "en")


def test_hindi_must_be_devanagari_and_length_bounded():
    assert not is_faithful("Irrigate about 52 mm today.", ADVICE, "hi")
    assert not is_faithful("", ADVICE, "en")
    assert not is_faithful("52 " * 200, ADVICE, "en")


def test_rewriter_uses_bedrock_when_faithful_else_template():
    good = Rewriter(FakeBedrock("आज लगभग 52 मिमी पानी दें।"), "model-x")
    assert good.rewrite(ADVICE, "hi")[1] == "bedrock"
    bad = Rewriter(FakeBedrock("आज 99 मिमी पानी दें।"), "model-x")
    assert bad.rewrite(ADVICE, "hi") == (template_texts(ADVICE)["hi"], "template")


def test_rewriter_falls_back_on_error_or_no_model():
    assert Rewriter(FakeBedrock(error=RuntimeError("throttled")), "m").rewrite(ADVICE, "en")[1] == "template"
    assert Rewriter(None, "").rewrite(ADVICE, "en")[1] == "template"


def test_rewriter_request_shape():
    fake = FakeBedrock("Irrigate about 52 mm today.")
    Rewriter(fake, "model-x").rewrite(ADVICE, "en")
    call = fake.calls[0]
    assert call["modelId"] == "model-x"
    assert call["inferenceConfig"] == {"maxTokens": 200, "temperature": 0.2}


def test_hindi_number_words_match_whole_words_only():
    # "एकड़" (acre) contains "एक", "बरसात" (rain) contains "सात", "दोपहर" (noon) contains "दो"
    assert is_faithful("हर एकड़ में 52 मिमी पानी दें, बरसात नहीं होगी, दोपहर से पहले।", ADVICE, "hi")


def test_accepted_rewrite_keeps_the_decision_support_footer():
    from engine.data import load_json
    text, source = Rewriter(FakeBedrock("आज लगभग 52 मिमी पानी दें।"), "m").rewrite(ADVICE, "hi")
    assert source == "bedrock" and text.endswith(load_json("messages.json")["footer"]["hi"])


def test_rewrite_must_keep_the_depth_for_irrigation():
    assert not is_faithful("आज खेत में पानी दें।", ADVICE, "hi")
    wait = dict(ADVICE, action="WAIT", depth_mm=0.0, reason_code="HEALTHY_WATER_BALANCE")
    assert is_faithful("आज पानी की ज़रूरत नहीं है।", wait, "hi")
