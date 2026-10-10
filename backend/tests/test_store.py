def profile(**kw):
    p = {"language": "hi", "latitude": 30.9, "longitude": 75.85, "crop": "wheat",
         "sowing_date": "2026-11-05", "soil": "loam", "area_acres": 1.5, "lift_m": 30,
         "pump_type": "electric", "pump_eff": 0.4, "status": "ACTIVE"}
    p.update(kw)
    return p


def test_profile_round_trip_and_active_index(store):
    store.put_profile("t1", profile())
    store.put_profile("t2", profile())
    store.set_active("t2", False)
    assert store.get_profile("t1")["soil"] == "loam"
    assert store.get_profile("missing") is None
    assert store.active_tokens() == ["t1"]


def test_events_in_time_order(store):
    store.put_event("t1", {"type": "RAIN", "level": "heavy"}, at="2026-12-02T08:00:00+05:30")
    store.put_event("t1", {"type": "WATERED", "level": "normal"}, at="2026-12-01T08:00:00+05:30")
    assert [e["type"] for e in store.events("t1")] == ["WATERED", "RAIN"]


def test_latest_day_and_push_sent_once(store):
    store.put_day("t1", "2026-12-01", {"advice": {"action": "WAIT"}})
    store.put_day("t1", "2026-12-02", {"advice": {"action": "IRRIGATE"}})
    assert store.latest_day("t1")["advice"]["action"] == "IRRIGATE"
    assert store.mark_push_sent("t1", "2026-12-02") is True
    assert store.mark_push_sent("t1", "2026-12-02") is False


def test_push_subscriptions_and_delete_field(store):
    sub = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "k", "auth": "a"}}
    store.put_profile("t1", profile())
    store.put_push("t1", sub)
    store.put_push("t1", sub)  # same endpoint stored once
    assert store.push_subscriptions("t1") == [sub]
    store.delete_push("t1", sub["endpoint"])
    assert store.push_subscriptions("t1") == []
    store.put_event("t1", {"type": "RAIN"}, at="2026-12-01T08:00:00+05:30")
    store.put_day("t1", "2026-12-01", {"advice": {}})
    store.delete_field("t1")
    assert store.get_profile("t1") is None and store.events("t1") == [] and store.latest_day("t1") is None


def test_rewriting_a_day_keeps_its_push_claim(store):
    store.put_day("t1", "2026-12-02", {"advice": {"action": "WAIT"}})
    assert store.mark_push_sent("t1", "2026-12-02") is True
    store.put_day("t1", "2026-12-02", {"advice": {"action": "IRRIGATE"}})  # e.g. a check-in recompute
    assert store.mark_push_sent("t1", "2026-12-02") is False
    assert store.get_day("t1", "2026-12-02")["advice"]["action"] == "IRRIGATE"
