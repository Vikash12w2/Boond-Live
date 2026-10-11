import boto3
import json
from decimal import Decimal

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("boond")


def lambda_handler(event, context):

    # Get token from /fields/{token}
    path_parameters = event.get("pathParameters") or {}
    field_token = path_parameters.get("token")

    if not field_token:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "Field token is required"
            })
        }

    # Get request body
    body = event.get("body", {})

    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "error": "Invalid JSON body"
                })
            }

    # Fields that can be updated
    allowed_fields = [
        "language",
        "latitude",
        "longitude",
        "crop",
        "sowing_date",
        "soil",
        "area_acres",
        "pump_type"
    ]

    updates = {
        key: body[key]
        for key in allowed_fields
        if key in body
    }

    if not updates:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "No valid fields to update"
            })
        }

    # Check that field exists
    response = table.get_item(
        Key={
            "pk": f"FIELD#{field_token}",
            "sk": "PROFILE"
        }
    )

    if "Item" not in response:
        return {
            "statusCode": 404,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "Field not found"
            })
        }

    # Build UpdateExpression
    expression_names = {}
    expression_values = {}
    set_parts = []

    for i, (key, value) in enumerate(updates.items()):
        name = f"#f{i}"
        val = f":v{i}"

        expression_names[name] = key

        # DynamoDB does not accept Python floats
        if key in ["latitude", "longitude", "area_acres"]:
            value = Decimal(str(value))

        expression_values[val] = value
        set_parts.append(f"{name} = {val}")

    update_expression = "SET " + ", ".join(set_parts)

    table.update_item(
        Key={
            "pk": f"FIELD#{field_token}",
            "sk": "PROFILE"
        },
        UpdateExpression=update_expression,
        ExpressionAttributeNames=expression_names,
        ExpressionAttributeValues=expression_values
    )

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps({
            "message": "Field updated successfully",
            "field_token": field_token,
            "updated_fields": list(updates.keys())
        })
    }