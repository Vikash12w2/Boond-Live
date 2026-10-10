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
