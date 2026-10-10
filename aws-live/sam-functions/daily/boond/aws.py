"""Real dependencies, built once per Lambda container from environment variables:

TABLE_NAME, BUCKET_NAME, BEDROCK_MODEL_ID (empty = template text only),
VAPID_PARAM (SSM SecureString name), VAPID_CONTACT (mailto: for push services).
The region comes from the Lambda environment.
"""
import os
from functools import lru_cache, partial

import boto3
from botocore.config import Config

from boond.audio import Audio
from boond.push import Pusher, load_private_key
from boond.refresh import Deps
from boond.store import Store
from boond.weather import WeatherCache, http_get_json, weather_for
from boond.wording import Rewriter


@lru_cache(maxsize=2)
def deps(fast=False):
    """fast=True (API requests): one 8 s weather try, so a request stays inside the API Lambda timeout."""
    bucket = os.environ["BUCKET_NAME"]
    # SigV4 presigned audio links on the regional endpoint (ap-south-1 requires SigV4).
    s3 = boto3.client("s3", config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}))
    model = os.environ.get("BEDROCK_MODEL_ID", "")
    return Deps(
        store=Store(boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])),
        weather=partial(weather_for, cache=WeatherCache(s3, bucket),
                        get_json=partial(http_get_json, tries=1, timeout=8) if fast else http_get_json),
        rewriter=Rewriter(boto3.client("bedrock-runtime") if model else None, model),
        audio=Audio(boto3.client("polly"), s3, bucket),
        pusher=Pusher(load_private_key(boto3.client("ssm"), os.environ["VAPID_PARAM"]), os.environ["VAPID_CONTACT"]),
    )
