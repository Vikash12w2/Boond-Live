import boto3

from boond import aws as aws_wiring
from boond.store import TABLE_SCHEMA


def test_deps_from_environment(aws, monkeypatch):
    boto3.resource("dynamodb", region_name="ap-south-1").create_table(TableName="t", **TABLE_SCHEMA)
    boto3.client("ssm", region_name="ap-south-1").put_parameter(
        Name="/boond/vapid_private_key", Value="PRIV", Type="SecureString")
    for key, value in {"TABLE_NAME": "t", "BUCKET_NAME": "b", "BEDROCK_MODEL_ID": "",
                       "VAPID_PARAM": "/boond/vapid_private_key", "VAPID_CONTACT": "mailto:x@y"}.items():
        monkeypatch.setenv(key, value)
    aws_wiring.deps.cache_clear()
    d = aws_wiring.deps()
    assert d.store.table.name == "t" and d.pusher.private_key == "PRIV" and d.audio.bucket == "b"
    advice = {"action": "WAIT", "reason_code": "HEALTHY_WATER_BALANCE", "depth_mm": 0.0, "warnings": []}
    assert d.rewriter.rewrite(advice, "en")[1] == "template"
    aws_wiring.deps.cache_clear()


def test_api_deps_use_a_short_single_try_weather_fetch(aws, monkeypatch):
    boto3.resource("dynamodb", region_name="ap-south-1").create_table(TableName="t", **TABLE_SCHEMA)
    boto3.client("ssm", region_name="ap-south-1").put_parameter(
        Name="/boond/vapid_private_key", Value="PRIV", Type="SecureString")
    for key, value in {"TABLE_NAME": "t", "BUCKET_NAME": "b", "BEDROCK_MODEL_ID": "",
                       "VAPID_PARAM": "/boond/vapid_private_key", "VAPID_CONTACT": "mailto:x@y"}.items():
        monkeypatch.setenv(key, value)
    aws_wiring.deps.cache_clear()
    get_json = aws_wiring.deps(fast=True).weather.keywords["get_json"]
    assert get_json.keywords == {"tries": 1, "timeout": 8}
    aws_wiring.deps.cache_clear()
