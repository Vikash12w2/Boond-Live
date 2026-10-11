from boond.audio import Audio, audio_key
from tests.conftest import FakePolly


def test_synthesises_once_per_text(bucket):
    polly = FakePolly()
    audio = Audio(polly, bucket, "boond-test")
    key = audio.ensure("आज पानी दें।", "hi")
    assert key == audio_key("आज पानी दें।", "hi") and key.startswith("audio/") and key.endswith(".mp3")
    assert audio.ensure("आज पानी दें।", "hi") == key
    assert len(polly.calls) == 1
    call = polly.calls[0]
    assert (call["VoiceId"], call["Engine"], call["LanguageCode"], call["OutputFormat"]) == ("Kajal", "neural", "hi-IN", "mp3")
    assert bucket.get_object(Bucket="boond-test", Key=key)["Body"].read() == b"ID3fake-mp3"


def test_english_uses_indian_english(bucket):
    polly = FakePolly()
    Audio(polly, bucket, "boond-test").ensure("Water today.", "en")
    assert polly.calls[0]["LanguageCode"] == "en-IN"


def test_polly_failure_gives_none(bucket):
    assert Audio(FakePolly(fail=True), bucket, "boond-test").ensure("x", "hi") is None


def test_presigned_url(bucket):
    url = Audio(FakePolly(), bucket, "boond-test").url("audio/abc.mp3")
    assert "audio/abc.mp3" in url and "X-Amz-Expires=3600" in url
