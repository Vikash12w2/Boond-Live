
import boto3
import json
import uuid
from datetime import date
from decimal import Decimal

from engine.data import select_profile
from engine.field_runner import start_state

dynamodb = boto3.resource("dynamodb")

TABLE_NAME = "boond"
table = dynamodb.Table(TABLE_NAME)


def to_decimal(value):
    """Convert floats recursively for DynamoDB compatibility."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: to_decimal(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_decimal(v) for v in value]
    return value


def lambda_handler(event, context):

    body = event.get("body", {})

    # API Gateway sends the body as a JSON string.
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Invalid JSON body"})
            }

    if not isinstance(body, dict):
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Body must be a JSON object"})
        }

    required_fields = [
        "language",
        "latitude",
        "longitude",
        "crop",
        "sowing_date",
        "soil",
        "area_acres",
        "pump_type"
    ]

    for field_name in required_fields:
        if field_name not in body:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "error": f"Missing field: {field_name}"
                })
            }

    # Validate input and initialize engine state.
    try:
        crop_name = str(body["crop"]).strip().lower()
        soil = str(body["soil"]).strip().lower()

        if not crop_name or not soil:
            raise ValueError("Crop and soil must not be empty")

        sowing_date = date.fromisoformat(
            body["sowing_date"]
        ).isoformat()

        latitude = Decimal(str(body["latitude"]))
        longitude = Decimal(str(body["longitude"]))
        area_acres = Decimal(str(body["area_acres"]))

        if not (-90 <= latitude <= 90):
            raise ValueError("Latitude must be between -90 and 90")

        if not (-180 <= longitude <= 180):
            raise ValueError("Longitude must be between -180 and 180")

        if area_acres <= 0:
            raise ValueError("Area must be greater than zero")

        # Defaults from the engine example.
        # Use actual farmer-provided values when available.
        lift_m = Decimal(str(body.get("lift_m", 30)))
        pump_eff = Decimal(str(body.get("pump_eff", 0.4)))

        if lift_m < 0:
            raise ValueError("lift_m cannot be negative")

        if not (0 < pump_eff <= 1):
            raise ValueError(
                "pump_eff must be greater than 0 and at most 1"
            )

        # Select the appropriate crop profile.
        engine_crop = select_profile(crop_name, sowing_date)

        field_for_engine = {
            "crop": engine_crop,
            "soil": soil,
            "sowing_date": sowing_date,
            "area_acres": float(area_acres),
            "lift_m": float(lift_m),
            "pump_eff": float(pump_eff)
        }

        # Initialize the irrigation engine's state.
        initial_state = to_decimal(
            start_state(field_for_engine)
        )

    except (ValueError, TypeError, KeyError) as exc:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(exc)})
        }

    # Generate a unique field token.
    field_token = uuid.uuid4().hex
    pk = f"FIELD#{field_token}"

    profile_item = {
        "pk": pk,
        "sk": "PROFILE",
        "language": body["language"],
        "latitude": latitude,
        "longitude": longitude,
        "crop": engine_crop,
        "crop_name": crop_name,
        "sowing_date": sowing_date,
        "soil": soil,
        "area_acres": area_acres,
        "pump_type": body["pump_type"],
        "lift_m": lift_m,
        "pump_eff": pump_eff
    }

    state_item = {
        "pk": pk,
        "sk": "STATE",
        **initial_state
    }

    # Save both items using the DynamoDB resource API.
    try:
        table.put_item(Item=profile_item)
        table.put_item(Item=state_item)

    except Exception as exc:
        print(f"Could not save field registration: {exc}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "Could not save field registration"
            })
        }

    return {
        "statusCode": 201,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "message": "Field registered successfully",
            "field_token": field_token
        })
    }
