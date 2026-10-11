"""HTTP API (API Gateway HTTP API, payload format 2.0). Routes are declared in infra/template.yaml."""
import base64
import json
import logging
import os
import secrets
from datetime import date, timedelta

from engine.checkins import make_event
from engine.data import farmer_soil_choices, select_profile
from engine.kc import get_season_length

from boond.refresh import field_view, refresh_field
from boond.util import now_iso, today_ist, token_hash

log = logging.getLogger(__name__)

# select_profile maps any wheat date to a profile, so the API bounds it: a field
# is registered within about one season of its sowing.
SOWING_WINDOW = timedelta(days=180)


class BadRequest(Exception):
    pass


def _response(status, body=None):
    response = {"statusCode": status, "headers": {"content-type": "application/json"}}
    if body is not None:
        response["body"] = json.dumps(body, ensure_ascii=False)
    return response


def _body(event):
    raw = event.get("body") or ""
    try:
        if event.get("isBase64Encoded"):
            raw = base64.b64decode(raw).decode()
        body = json.loads(raw)
    except ValueError:
        raise BadRequest("body must be JSON")
    if not isinstance(body, dict):
        raise BadRequest("body must be a JSON object")
    return body


def _number(body, key, low, high):
    value = body.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
        raise BadRequest(f"{key} must be a number from {low} to {high}")
    return value


def _date(body, key):
    try:
        return date.fromisoformat(str(body.get(key)))
    except ValueError:
        raise BadRequest(f"{key} must be a date YYYY-MM-DD")


def _refresh(token, deps, today):
    """Recompute now so the page is current; a failure here leaves the data saved for the next run."""
    try:
        refresh_field(token, deps, today)
    except Exception:
        log.exception("immediate refresh failed for field %s", token_hash(token))


def register(body, deps, today):
    if body.get("consent") is not True:
        raise BadRequest("consent is required")
    if body.get("language") not in ("hi", "en"):
        raise BadRequest("language must be hi or en")
    crop = str(body.get("crop", "")).strip().lower()
    allowed_crops = {"wheat", "paddy", "cotton", "sugarcane"}
    if crop not in allowed_crops:
        raise BadRequest("crop must be wheat, paddy, cotton, or sugarcane")
    soils = farmer_soil_choices()
    if body.get("soil") not in soils:
        raise BadRequest("soil must be one of " + ", ".join(soils))
    sowing = _date(body, "sowing_date")
    if abs(sowing - today) > SOWING_WINDOW:
        raise BadRequest("sowing_date must be within 180 days of today")
    crop_profile = select_profile(crop, sowing.isoformat())
    if (today - sowing).days + 1 > get_season_length(crop_profile):
        raise BadRequest(f"the {crop} season for this sowing date is already over")
    profile = {
        "language": body["language"],
        "latitude": round(_number(body, "latitude", -90, 90), 2),
        "longitude": round(_number(body, "longitude", -180, 180), 2),
        "crop": crop,
        "sowing_date": sowing.isoformat(),
        "soil": body["soil"],
        "area_acres": _number(body, "area_acres", 0.1, 100),
        "lift_m": _number(body, "lift_m", 1, 300),
        "pump_type": "electric",
        "pump_eff": None,  # the engine uses its default pump efficiency
        "status": "ACTIVE",
        "consent_at": now_iso(),
        "created_at": now_iso(),
    }
    token = secrets.token_urlsafe(16)
    deps.store.put_profile(token, profile)
    _refresh(token, deps, today)
    log.info("registered field %s", token_hash(token))
    return _response(201, {"field_token": token})


def add_event(token, body, deps, today):
    profile = deps.store.get_profile(token)
    if body.get("type") not in ("WATERED", "RAIN"):
        raise BadRequest("type must be WATERED or RAIN")
    on = _date(body, "date")
    if on > today or on < date.fromisoformat(profile["sowing_date"]):
        raise BadRequest("date must be between the sowing date and today")
    try:
        event = make_event(body["type"], str(body.get("level", "")), on.isoformat(),
                           select_profile("crop", profile["sowing_date"]))
    except ValueError as error:
        raise BadRequest(str(error))
    deps.store.put_event(token, event, at=now_iso())
    _refresh(token, deps, today)
    return _response(201, {"ok": True})


def add_push(token, body, deps):
    keys = body.get("keys")
    if not str(body.get("endpoint", "")).startswith("https://") or not isinstance(keys, dict) \
            or not keys.get("p256dh") or not keys.get("auth"):
        raise BadRequest("not a push subscription")
    deps.store.put_push(token, {"endpoint": body["endpoint"],
                                "keys": {"p256dh": keys["p256dh"], "auth": keys["auth"]}})
    return _response(201, {"ok": True})


def route(event, deps, today):
    key = event.get("routeKey", "")
    token = (event.get("pathParameters") or {}).get("token")
    try:
        if key == "GET /config":
            return _response(200, {"vapid_public_key": os.environ.get("VAPID_PUBLIC_KEY", "")})
        if key == "POST /fields":
            return register(_body(event), deps, today)
        if token is None or deps.store.get_profile(token) is None:
            return _response(404, {"error": "field not found"})
        if key == "GET /fields/{token}":
            return _response(200, field_view(token, deps))
        if key == "POST /fields/{token}/events":
            return add_event(token, _body(event), deps, today)
        if key == "POST /fields/{token}/push-subscription":
            return add_push(token, _body(event), deps)
        if key == "DELETE /fields/{token}":
            deps.store.delete_field(token)
            return _response(204)
        return _response(404, {"error": "no such route"})
    except BadRequest as error:
        return _response(400, {"error": str(error)})
    except Exception:
        log.exception("request failed: %s", key)
        return _response(500, {"error": "internal error"})


def handler(event, context):
    from boond.aws import deps
    return route(event, deps(fast=True), today_ist())
