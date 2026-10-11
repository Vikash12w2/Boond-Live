from types import SimpleNamespace

import boto3
from pywebpush import WebPushException

from boond.push import Pusher, load_private_key

SUB = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "k", "auth": "a"}}


def test_sent_and_payload():
    calls = []
    p = Pusher("PRIV", "mailto:team@example.com", send=lambda **kw: calls.append(kw))
    assert p.send(SUB, {"title": "Boond", "body": "आज पानी दें", "url": "#/f/t"}) == "sent"
    assert calls[0]["subscription_info"] == SUB and calls[0]["vapid_private_key"] == "PRIV"
    assert calls[0]["vapid_claims"] == {"sub": "mailto:team@example.com"} and calls[0]["ttl"] == 43200
    assert '"url":"#/f/t"' in calls[0]["data"] and "आज पानी दें" in calls[0]["data"]


def test_gone_subscription():
    def send(**kw):
        raise WebPushException("gone", response=SimpleNamespace(status_code=410))
    assert Pusher("PRIV", "mailto:x@y", send=send).send(SUB, {}) == "gone"


def test_other_failure():
    def send(**kw):
        raise WebPushException("boom", response=None)
    assert Pusher("PRIV", "mailto:x@y", send=send).send(SUB, {}) == "failed"


def test_private_key_from_ssm(aws):
    ssm = boto3.client("ssm", region_name="ap-south-1")
    ssm.put_parameter(Name="/boond/vapid_private_key", Value="PRIV", Type="SecureString")
    assert load_private_key(ssm, "/boond/vapid_private_key") == "PRIV"


def test_network_error_is_a_failed_send_not_a_crash():
    import requests

    def send(**kw):
        raise requests.ConnectionError("unreachable")
    assert Pusher("PRIV", "mailto:x@y", send=send).send(SUB, {}) == "failed"


def test_generated_keys_work_with_real_pywebpush():
    """Keys from boond.vapid encrypt and sign a real Web Push request (captured, never sent)."""
    import base64
    import os
    from functools import partial

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from pywebpush import webpush

    from boond.vapid import generate

    private_key, public_key = generate()
    assert len(base64.urlsafe_b64decode(public_key + "==")) == 65  # what PushManager.subscribe expects

    browser = ec.generate_private_key(ec.SECP256R1())  # the phone's subscription keys
    p256dh = browser.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    b64 = lambda raw: base64.urlsafe_b64encode(raw).decode().rstrip("=")  # noqa: E731
    sub = {"endpoint": "https://fcm.googleapis.com/fcm/send/abc", "keys": {"p256dh": b64(p256dh), "auth": b64(os.urandom(16))}}

    class Session:
        def post(self, url, data, headers, timeout):
            self.url, self.data, self.headers = url, data, headers
            return SimpleNamespace(status_code=201, text="")
    session = Session()
    assert Pusher(private_key, "mailto:team@example.com", send=partial(webpush, requests_session=session)).send(sub, {"body": "hi"}) == "sent"
    assert session.url == sub["endpoint"] and session.headers["authorization"].startswith("vapid t=")
    assert session.headers["content-encoding"] == "aes128gcm" and b"hi" not in session.data
