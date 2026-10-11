from datetime import date

from boond.refresh import field_view, refresh_field

PROFILE = {"language": "hi", "latitude": 30.9, "longitude": 75.85, "crop": "wheat", "sowing_date": "2021-11-05",
           "soil": "loam", "area_acres": 1.0, "lift_m": 30, "pump_eff": 0.4, "pump_type": "electric",
           "status": "ACTIVE", "created_at": "2021-11-01T10:00:00+05:30"}
TODAY = date(2022, 1, 20)
SUB = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "k", "auth": "a"}}


def test_refresh_stores_day_with_text_and_audio(deps):
    deps.store.put_profile("t1", PROFILE)
    day = refresh_field("t1", deps, TODAY)
    assert day["advice"]["date"] == "2022-01-20"
    assert set(day["advice_text"]) == {"hi", "en"} and day["text_source"] == "template"
    assert day["audio_key"].startswith("audio/") and day["weather_stale"] is False
    assert deps.store.latest_day("t1") == day


def test_notify_sends_once_and_drops_gone_subscriptions(deps):
    deps.store.put_profile("t1", PROFILE)
    deps.store.put_push("t1", SUB)
    refresh_field("t1", deps, TODAY, notify=True)
    refresh_field("t1", deps, TODAY, notify=True)
    assert len(deps.pusher.sent) == 1
    assert deps.pusher.sent[0][1]["url"] == "#/f/t1"
    deps.pusher.result = "gone"
    refresh_field("t1", deps, date(2022, 1, 21), notify=True)
    assert deps.store.push_subscriptions("t1") == []


def test_refresh_without_notify_keeps_an_earlier_claim(deps):
    deps.store.put_profile("t1", PROFILE)
    deps.store.put_push("t1", SUB)
    refresh_field("t1", deps, TODAY, notify=True)
    refresh_field("t1", deps, TODAY)                # e.g. a check-in recomputes the day
    refresh_field("t1", deps, TODAY, notify=True)   # scheduler retry
    assert len(deps.pusher.sent) == 1


def test_field_view_shape_matches_frontend(deps):
    deps.store.put_profile("t1", PROFILE)
    refresh_field("t1", deps, TODAY)
    view = field_view("t1", deps)
    assert view["field_token"] == "t1" and view["latitude"] == 30.9 and view["language"] == "hi"
    a = view["latest_advice"]
    assert a["action"] in ("IRRIGATE", "SKIP", "WAIT", "HEAT_PROTECTION")
    assert a["advice_text"]["hi"] and a["audio_url"].startswith("https://") and a["generated_at"]
    assert field_view("missing", deps) is None


def test_field_view_before_any_run(deps):
    deps.store.put_profile("t1", PROFILE)
    assert field_view("t1", deps)["latest_advice"] is None


def test_sowing_window_note_reaches_the_page_in_both_languages(deps):
    deps.store.put_profile("late", dict(PROFILE, sowing_date="2021-12-28"))  # 8 days after the 20 Dec window
    refresh_field("late", deps, TODAY)
    notes = field_view("late", deps)["latest_advice"]["warnings_text"]
    assert notes["en"] == ["Note: sowing was 8 days after the recommended window (22 Nov – 20 Dec). "
                           "Yield may be lower; the irrigation advice still follows the crop's water need."]
    assert notes["hi"][0].startswith("ध्यान दें: बुवाई")


def test_no_note_inside_the_window(deps):
    deps.store.put_profile("t1", PROFILE)
    refresh_field("t1", deps, TODAY)
    assert field_view("t1", deps)["latest_advice"]["warnings_text"] == {"hi": [], "en": []}


def test_unavailable_day_replaces_yesterdays_advice_and_notifies_once(deps):
    from boond.refresh import mark_unavailable
    deps.store.put_profile("t1", PROFILE)
    deps.store.put_push("t1", SUB)
    refresh_field("t1", deps, TODAY)                      # yesterday-style advice exists
    tomorrow = date(2022, 1, 21)
    mark_unavailable("t1", deps, tomorrow, notify=True)
    mark_unavailable("t1", deps, tomorrow, notify=True)   # scheduler retry
    latest = field_view("t1", deps)["latest_advice"]
    assert latest["status"] == "UNAVAILABLE" and latest["date"] == "2022-01-21"
    assert "check the soil yourself" in latest["advice_text"]["en"]
    assert latest["advice_text"]["hi"]
    assert len(deps.pusher.sent) == 1 and "check the soil yourself" not in deps.pusher.sent[0][1]["body"]  # Hindi field
    assert deps.pusher.sent[0][1]["body"] == latest["advice_text"]["hi"][:180]


def test_unavailable_never_overwrites_real_advice_from_today(deps):
    from boond.refresh import mark_unavailable
    deps.store.put_profile("t1", PROFILE)
    refresh_field("t1", deps, TODAY)
    mark_unavailable("t1", deps, TODAY, notify=True)
    assert field_view("t1", deps)["latest_advice"]["status"] == "ACTIVE"
