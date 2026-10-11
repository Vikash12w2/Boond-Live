import boto3
import json
from decimal import Decimal
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")

TABLE_NAME = "boond"
table = dynamodb.Table(TABLE_NAME)


def decimal_to_number(value):
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)

    if isinstance(value, dict):
        return {
            key: decimal_to_number(val)
            for key, val in value.items()
        }

    if isinstance(value, list):
        return [decimal_to_number(val) for val in value]

    return value


def response(status_code, data):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(data)
    }


def lambda_handler(event, context):
    path_parameters = event.get("pathParameters") or {}
    field_token = path_parameters.get("token")

    if not field_token:
        return response(400, {
            "error": "Field token is required"
        })

    pk = f"FIELD#{field_token}"

    # 1. Get the field profile
    profile_response = table.get_item(
        Key={"pk": pk, "sk": "PROFILE"}
    )

    if "Item" not in profile_response:
        return response(404, {
            "error": "Field not found"
        })

    field = profile_response["Item"]
    field.pop("pk", None)
    field.pop("sk", None)

    # 2. Get the latest saved state
    state_response = table.get_item(
        Key={"pk": pk, "sk": "STATE"}
    )

    state = state_response.get("Item")

    if state:
        state.pop("pk", None)
        state.pop("sk", None)

    # 3. Get the latest daily advice
    day_response = table.query(
        KeyConditionExpression=(
            Key("pk").eq(pk) &
            Key("sk").begins_with("DAY#")
        ),
        ScanIndexForward=False,
        Limit=1
    )

    day_items = day_response.get("Items", [])
    latest_day = day_items[0] if day_items else None

    latest_advice = None
    if latest_day:
        latest_advice = {
            "date": latest_day.get("date"),
            "advice": latest_day.get("advice"),
            "advice_text": latest_day.get("advice_text"),
            "language": latest_day.get("language")
        }

    result = {
        **field,
        "field_token": field_token,
        "state": state,
        "latest_advice": latest_advice
    }

    return response(200, decimal_to_number(result))