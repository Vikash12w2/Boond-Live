import boto3
import json

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("boond")


def lambda_handler(event, context):

    # Get field token
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

    # Get body
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

    # Use real browser subscription if provided.
    # Otherwise use dummy values for testing.
    endpoint = body.get(
        "endpoint",
        "https://example.com/push/dummy"
    )

    keys = body.get(
        "keys",
        {
            "p256dh": "dummy-p256dh-key",
            "auth": "dummy-auth-key"
        }
    )

    item = {
        "pk": f"FIELD#{field_token}",
        "sk": "PUSH",
        "endpoint": endpoint,
        "keys": keys
    }

    table.put_item(Item=item)

    return {
        "statusCode": 201,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps({
            "message": "Push subscription saved successfully",
            "field_token": field_token
        })
    }