
import boto3
import json

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("boond")


def lambda_handler(event, context):
    path_parameters = event.get("pathParameters") or {}
    field_token = path_parameters.get("token")

    if not field_token:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Field token is required"})
        }

    pk = f"FIELD#{field_token}"

    # Check whether the field exists
    response = table.get_item(
        Key={"pk": pk, "sk": "PROFILE"},
        ConsistentRead=True
    )

    if "Item" not in response:
        return {
            "statusCode": 404,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Field not found"})
        }

    # Query every item belonging to this field
    items = []
    query_kwargs = {
        "KeyConditionExpression": (
            boto3.dynamodb.conditions.Key("pk").eq(pk)
        ),
        "ProjectionExpression": "pk, sk"
    }

    while True:
        result = table.query(**query_kwargs)
        items.extend(result.get("Items", []))

        if "LastEvaluatedKey" not in result:
            break

        query_kwargs["ExclusiveStartKey"] = result["LastEvaluatedKey"]

    # Delete in batches of at most 25 items
    with table.batch_writer() as batch:
        for item in items:
            batch.delete_item(
                Key={"pk": item["pk"], "sk": item["sk"]}
            )

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "message": "Field and associated data deleted successfully",
            "field_token": field_token,
            "deleted_items": len(items)
        })
    }
