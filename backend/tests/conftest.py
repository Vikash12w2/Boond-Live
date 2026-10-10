import boto3
import pytest
from moto import mock_aws

from boond.store import TABLE_SCHEMA, Store

REGION = "ap-south-1"


@pytest.fixture(autouse=True)
def aws_env(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")


@pytest.fixture
def aws():
    with mock_aws():
        yield


@pytest.fixture
def store(aws):
    table = boto3.resource("dynamodb", region_name=REGION).create_table(TableName="boond-test", **TABLE_SCHEMA)
    return Store(table)


import io  # noqa: E402


class FakePolly:
    def __init__(self, fail=False):
        self.fail, self.calls = fail, []

    def synthesize_speech(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("polly down")
        return {"AudioStream": io.BytesIO(b"ID3fake-mp3")}


@pytest.fixture
def bucket(aws):
    s3 = boto3.client("s3", region_name=REGION)
    s3.create_bucket(Bucket="boond-test", CreateBucketConfiguration={"LocationConstraint": REGION})
    return s3


import json as _json  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

from boond.audio import Audio  # noqa: E402
from boond.refresh import Deps  # noqa: E402

_REPLAY = _json.loads((_Path(__file__).resolve().parents[2] / "replay/cache/ludhiana_actual_2021_22.json").read_text())["daily"]


def replay_weather(sowing, today):
    """Real 2021-22 Ludhiana weather in the shape weather_for() returns."""
    i, s = _REPLAY["date"].index(today.isoformat()), _REPLAY["date"].index(sowing)
    obs = {k: _REPLAY[k][s:i] for k in ("date", "et0_mm", "rain_mm", "tmax_c")}
    fc = {k: _REPLAY[k][i:i + 16] for k in ("date", "et0_mm", "rain_mm", "tmax_c")}
    fc["rain_prob"] = [0.0] * len(fc["date"])
    return {"observed": obs, "forecast": fc, "fetched_for": today.isoformat(), "earliest_sowing": sowing}


class FakeRewriter:
    def rewrite(self, advice, lang):
        from boond.wording import template_texts
        return template_texts(advice)[lang], "template"


class FakePusher:
    def __init__(self, result="sent"):
        self.result, self.sent = result, []

    def send(self, subscription, payload):
        self.sent.append((subscription, payload))
        return self.result


@pytest.fixture
def deps(store, bucket):
    calls = []

    def weather(lat, lon, earliest_sowing, today):
        calls.append((lat, lon, earliest_sowing, today))
        return replay_weather(earliest_sowing.isoformat(), today), False

    d = Deps(store=store, weather=weather, rewriter=FakeRewriter(),
             audio=Audio(FakePolly(), bucket, "boond-test"), pusher=FakePusher())
    d.weather_calls = calls
    return d
