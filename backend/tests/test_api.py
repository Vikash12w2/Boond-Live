import base64
import json
from datetime import date

from boond.api import route

TODAY = date(2022, 1, 20)
BODY = {"language": "hi", "latitude": 30.9, "longitude": 75.85, "crop": "wheat", "sowing_date": "2021-11-05",
        "soil": "loam", "area_acres": 1.5, "pump_type": "electric", "lift_m": 30, "consent": True}


def call(deps, method, path, body=None, raw=None, b64=False, params=None):
    text = raw if raw is not None else (json.dumps(body) if body is not None else None)
    if b64 and text is not None:
        text = base64.b64encode(text.encode()).decode()
    event = {"routeKey": f"{method} {path}", "pathParameters": params or {}, "body": text, "isBase64Encoded": b64}
    response = route(event, deps, TODAY)
    return response["statusCode"], (json.loads(response["body"]) if response.get("body") else None)


def register(deps, **overrides):
    status, body = call(deps, "POST", "/fields", dict(BODY, **overrides))
    assert status == 201, body
    return body["field_token"]


def test_register_then_get(deps):
    token = register(deps)
    assert len(token) >= 22
    status, view = call(deps, "GET", "/fields/{token}", params={"token": token})
    assert status == 200 and view["latest_advice"]["date"] == "2022-01-20"
    assert deps.store.get_profile(token)["consent_at"]


def test_register_validation(deps):
    for bad in ({"latitude": 300}, {"soil": "rock"}, {"area_acres": 0}, {"lift_m": 0}, {"latitude": True},
                {"sowing_date": "yesterday"}, {"sowing_date": "2020-11-05"}, {"consent": False},
                {"language": "fr"}, {"crop": "maize"}):
        status, body = call(deps, "POST", "/fields", dict(BODY, **bad))
        assert status == 400 and body["error"], bad

def test_register_supports_all_four_crops(deps):
    for crop in ("wheat", "paddy", "cotton", "sugarcane"):
        body = dict(BODY, crop=crop)
        status, result = call(deps, "POST", "/fields", body)

        assert status == 201, (crop, result)

        token = result["field_token"]
        profile = deps.store.get_profile(token)
        assert profile["crop"] == crop

def test_register_succeeds_when_weather_is_down(deps):
    from boond.weather import WeatherUnavailable

    def down(*args):
        raise WeatherUnavailable("down")
    deps.weather = down
    token = register(deps)
    assert call(deps, "GET", "/fields/{token}", params={"token": token})[1]["latest_advice"] is None


def test_bad_json_is_400(deps):
    assert call(deps, "POST", "/fields", raw="{not json")[0] == 400
    assert call(deps, "POST", "/fields", raw="[1, 2]")[0] == 400


def test_base64_body_is_decoded(deps):
    status, body = call(deps, "POST", "/fields", BODY, b64=True)
    assert status == 201 and body["field_token"]


def test_unknown_token_is_404(deps):
    assert call(deps, "GET", "/fields/{token}", params={"token": "nope"})[0] == 404


def test_event_recomputes(deps):
    token = register(deps)
    before = deps.store.latest_day(token)["advice"]["depletion_mm"]
    status, _ = call(deps, "POST", "/fields/{token}/events", {"type": "WATERED", "level": "normal", "date": "2022-01-18"},
                     params={"token": token})
    assert status == 201
    assert deps.store.latest_day(token)["advice"]["depletion_mm"] < before


def test_event_validation(deps):
    token = register(deps)
    for bad in ({"type": "WATERED", "level": "normal", "date": "2022-01-25"},   # future
                {"type": "WATERED", "level": "normal", "date": "2021-11-01"},   # before sowing
                {"type": "WATERED", "level": "flood", "date": "2022-01-18"},    # unknown level
                {"type": "SNOW", "level": "heavy", "date": "2022-01-18"}):
        status, body = call(deps, "POST", "/fields/{token}/events", bad, params={"token": token})
        assert status == 400 and body["error"], bad


def test_push_subscription_and_delete(deps):
    token = register(deps)
    sub = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "k", "auth": "a"}}
    assert call(deps, "POST", "/fields/{token}/push-subscription", sub, params={"token": token})[0] == 201
    assert call(deps, "POST", "/fields/{token}/push-subscription", {"endpoint": "x"}, params={"token": token})[0] == 400
    assert call(deps, "DELETE", "/fields/{token}", params={"token": token})[0] == 204
    assert deps.store.get_profile(token) is None


def test_config_returns_public_key(deps, monkeypatch):
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "PUBKEY")
    assert call(deps, "GET", "/config") == (200, {"vapid_public_key": "PUBKEY"})


def test_register_rejects_a_season_that_is_already_over(deps):
    # sown 2021-08-01 -> "wheat" profile (145 days); 2022-01-20 is day 173: season over
    status, body = call(deps, "POST", "/fields", dict(BODY, sowing_date="2021-08-01"))
    assert status == 400 and "season" in body["error"]
