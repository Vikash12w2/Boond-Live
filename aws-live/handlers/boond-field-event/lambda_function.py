
import boto3
import json
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from decimal import Decimal

from engine.checkins import make_event

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("boond")

IST = ZoneInfo("Asia/Kolkata")


def to_decimal(value):
    """Convert floats recursively to DynamoDB-compatible Decimals."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: to_decimal(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_decimal(v) for v in value]
    return value


def response(status_code, data):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(data, default=str)
    }


def lambda_handler(event, context):

    # Read field token from /fields/{token}/events
    path_parameters = event.get("pathParameters") or {}
    field_token = path_parameters.get("token")

    if not field_token:
        return response(400, {"error": "Field token is required"})

    # Parse request body
    body = event.get("body", {})

    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            return response(400, {"error": "Invalid JSON body"})

    if not isinstance(body, dict):
        return response(400, {"error": "Body must be a JSON object"})

    # Map existing API event names to engine event types
    requested_event = str(body.get("event", "")).strip().lower()

    event_mapping = {
        "watered": "WATERED",
        "rained": "RAIN",
        "rain": "RAIN"
    }

    engine_type = event_mapping.get(requested_event)

    if not engine_type:
        return response(
            400,
            {"error": "event must be 'watered' or 'rained'"}
        )

    # Defaults for event level
    default_level = (
        "normal" if engine_type == "WATERED" else "moderate"
    )
    level = str(body.get("level", default_level)).strip().lower()

    # Use supplied date or today's date in India
    event_date = str(
        body.get("date", datetime.now(IST).date().isoformat())
    )

    try:
        datetime.strptime(event_date, "%Y-%m-%d")
    except ValueError:
        return response(
            400,
            {"error": "date must use YYYY-MM-DD format"}
        )

    # Fetch the field profile
    pk = f"FIELD#{field_token}"

    try:
        result = table.get_item(
            Key={"pk": pk, "sk": "PROFILE"}
        )
    except Exception as exc:
        print(f"Could not read field profile: {exc}")
        return response(500, {"error": "Could not read field profile"})

    field = result.get("Item")

    if not field:
        return response(404, {"error": "Field not found"})

    # Build the event using the engine's function
    try:
        engine_event = make_event(
            engine_type,
            level,
            event_date,
            field["crop"]
        )
    except (ValueError, TypeError, KeyError) as exc:
        return response(400, {"error": str(exc)})

    timestamp = datetime.now(IST).isoformat()
    event_id = uuid.uuid4().hex

    # Convert all numeric floats before saving to DynamoDB
    item = {
        "pk": pk,
        "sk": f"EVENT#{event_date}#{timestamp}#{event_id}",
        **engine_event,
        "event": requested_event,
        "timestamp": timestamp
    }
    item = to_decimal(item)

    # Save the event
    try:
        table.put_item(Item=item)
    except Exception as exc:
        print(f"Could not save check-in: {exc}")
        return response(500, {"error": "Could not save check-in"})

    return response(201, {
        "message": "Event recorded successfully",
        "field_token": field_token,
        "event": engine_type,
        "date": event_date,
        "level": engine_event["level"],
        "mm_assumed": engine_event["mm_assumed"]
    })
