"""Run one field end to end: engine -> words -> audio -> store -> (push).

Used by the API (right after registration or a check-in) and by the daily job.
"""
import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from boond.advise import run_field
from boond.util import now_iso, token_hash
from boond.wording import UNAVAILABLE_TEXT, template_texts
from engine.messages import render_warnings

log = logging.getLogger(__name__)

PUSH_TITLE = {"hi": "बूँद: आज की सलाह", "en": "Boond: today's advice"}
PUSH_BODY_CHARS = 180


@dataclass
class Deps:
    store: Any
    weather: Callable  # (lat, lon, earliest_sowing: date, today: date) -> (weather dict, stale bool)
    rewriter: Any
    audio: Any
    pusher: Any


def refresh_field(token, deps, today, weather=None, stale=False, notify=False):
    """Recompute today's advice for one field, store it, and notify once a day if asked."""
    profile = deps.store.get_profile(token)
    if weather is None:
        weather, stale = deps.weather(profile["latitude"], profile["longitude"],
                                      date.fromisoformat(profile["sowing_date"]), today)
    advice = run_field(profile, deps.store.events(token), weather, today)
    lang = profile["language"]
    texts = template_texts(advice)
    texts[lang], source = deps.rewriter.rewrite(advice, lang)
    day_key = today.isoformat()
    deps.store.put_day(token, day_key, {
        "advice": advice,
        "advice_text": texts,
        "text_source": source,
        "audio_key": deps.audio.ensure(texts[lang], lang),
        "generated_at": now_iso(),
        "weather_stale": stale,
        # Sowing-window note, a separate sentence beside the advice (engine.messages.render_warnings).
        "warnings_text": {code: render_warnings(advice, code) for code in ("hi", "en")},
    })
    if advice.get("status") == "SEASON_OVER":
        deps.store.set_active(token, False)
    if notify and advice.get("status") == "ACTIVE":
        _notify_once(token, deps, day_key, lang, texts[lang])
    log.info("refreshed field %s: %s %s mm (%s text)", token_hash(token), advice.get("action"),
             advice.get("depth_mm"), source)
    return deps.store.get_day(token, day_key)


def _notify_once(token, deps, day_key, lang, text):
    if not deps.store.mark_push_sent(token, day_key):
        return
    payload = {"title": PUSH_TITLE[lang], "body": text[:PUSH_BODY_CHARS], "url": f"#/f/{token}"}
    for sub in deps.store.push_subscriptions(token):
        if deps.pusher.send(sub, payload) == "gone":
            deps.store.delete_push(token, sub["endpoint"])


def mark_unavailable(token, deps, today, notify=False):
    """No advice could be made today (weather missing): say so instead of leaving yesterday's advice up.
    Real advice already made today is never replaced."""
    day_key = today.isoformat()
    existing = deps.store.get_day(token, day_key)
    if existing and existing["advice"].get("status") != "UNAVAILABLE":
        return existing
    lang = deps.store.get_profile(token)["language"]
    deps.store.put_day(token, day_key, {
        "advice": {"status": "UNAVAILABLE", "date": day_key, "reason_code": "WEATHER_UNAVAILABLE"},
        "advice_text": dict(UNAVAILABLE_TEXT),
        "text_source": "template",
        "audio_key": deps.audio.ensure(UNAVAILABLE_TEXT[lang], lang),
        "generated_at": now_iso(),
        "weather_stale": False,
        "warnings_text": {"hi": [], "en": []},
    })
    if notify:
        _notify_once(token, deps, day_key, lang, UNAVAILABLE_TEXT[lang])
    log.info("field %s: advice unavailable on %s", token_hash(token), day_key)
    return deps.store.get_day(token, day_key)


def field_view(token, deps):
    """GET /fields/{token} body, in the shape frontend/src/live.ts reads."""
    profile = deps.store.get_profile(token)
    if profile is None:
        return None
    day = deps.store.latest_day(token)
    latest = None
    if day:
        latest = dict(day["advice"], advice_text=day["advice_text"], generated_at=day["generated_at"],
                      weather_stale=day["weather_stale"], warnings_text=day.get("warnings_text", {"hi": [], "en": []}),
                      audio_url=deps.audio.url(day["audio_key"]) if day.get("audio_key") else None)
    return {
        "field_token": token,
        "crop": profile["crop"],
        "language": profile["language"],
        "sowing_date": profile["sowing_date"],
        "soil": profile["soil"],
        "area_acres": profile["area_acres"],
        "lift_m": profile["lift_m"],
        "pump_eff": profile.get("pump_eff"),
        "pump_type": profile.get("pump_type"),
        "latitude": profile["latitude"],
        "longitude": profile["longitude"],
        "latest_advice": latest,
    }
