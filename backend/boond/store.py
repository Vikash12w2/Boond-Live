"""DynamoDB access. The only module that knows the key layout:

    PK FIELD#<token>   SK PROFILE | DAY#<date> | EVENT#<iso time> | PUSH#<hash>

Payloads live in a JSON string attribute "data", so floats never need Decimal
conversion. Active profiles carry gsi_active="1" so the daily job can list them
through the "active" index instead of scanning the table.
"""
import hashlib

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from boond.util import dumps, loads

TABLE_SCHEMA = {
    "KeySchema": [{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
    "AttributeDefinitions": [
        {"AttributeName": "PK", "AttributeType": "S"},
        {"AttributeName": "SK", "AttributeType": "S"},
        {"AttributeName": "gsi_active", "AttributeType": "S"},
    ],
    "GlobalSecondaryIndexes": [{
        "IndexName": "active",
        "KeySchema": [{"AttributeName": "gsi_active", "KeyType": "HASH"}, {"AttributeName": "PK", "KeyType": "RANGE"}],
        "Projection": {"ProjectionType": "KEYS_ONLY"},
    }],
    "BillingMode": "PAY_PER_REQUEST",
}


def _pk(token):
    return f"FIELD#{token}"


def _push_sk(endpoint):
    return "PUSH#" + hashlib.sha256(endpoint.encode()).hexdigest()[:16]


class Store:
    def __init__(self, table):
        self.table = table

    # Profile

    def put_profile(self, token, profile):
        item = {"PK": _pk(token), "SK": "PROFILE", "data": dumps(profile)}
        if profile.get("status") == "ACTIVE":
            item["gsi_active"] = "1"
        self.table.put_item(Item=item)

    def get_profile(self, token):
        item = self.table.get_item(Key={"PK": _pk(token), "SK": "PROFILE"}).get("Item")
        return loads(item["data"]) if item else None

    def set_active(self, token, active):
        key = {"PK": _pk(token), "SK": "PROFILE"}
        if active:
            self.table.update_item(Key=key, UpdateExpression="SET gsi_active = :one",
                                   ExpressionAttributeValues={":one": "1"})
        else:
            self.table.update_item(Key=key, UpdateExpression="REMOVE gsi_active")

    def active_tokens(self):
        query = {"IndexName": "active", "KeyConditionExpression": Key("gsi_active").eq("1")}
        return sorted(item["PK"].removeprefix("FIELD#") for item in self._query(query))

    # Items under one field

    def _query(self, query):
        items = []
        while True:
            page = self.table.query(**query)
            items += page["Items"]
            if "LastEvaluatedKey" not in page:
                return items
            query = dict(query, ExclusiveStartKey=page["LastEvaluatedKey"])

    def _items(self, token, prefix):
        return self._query({"KeyConditionExpression": Key("PK").eq(_pk(token)) & Key("SK").begins_with(prefix)})

    def put_event(self, token, event, at):
        self.table.put_item(Item={"PK": _pk(token), "SK": f"EVENT#{at}", "data": dumps(event)})

    def events(self, token):
        return [loads(item["data"]) for item in self._items(token, "EVENT#")]

    def put_day(self, token, day, item):
        # An update, not a replace: a recompute must keep the day's push_sent claim.
        self.table.update_item(Key={"PK": _pk(token), "SK": f"DAY#{day}"}, UpdateExpression="SET #d = :data",
                               ExpressionAttributeNames={"#d": "data"}, ExpressionAttributeValues={":data": dumps(item)})

    def get_day(self, token, day):
        item = self.table.get_item(Key={"PK": _pk(token), "SK": f"DAY#{day}"}).get("Item")
        return dict(loads(item["data"]), push_sent=bool(item.get("push_sent"))) if item else None

    def latest_day(self, token):
        page = self.table.query(KeyConditionExpression=Key("PK").eq(_pk(token)) & Key("SK").begins_with("DAY#"),
                                ScanIndexForward=False, Limit=1)
        if not page["Items"]:
            return None
        item = page["Items"][0]
        return dict(loads(item["data"]), push_sent=bool(item.get("push_sent")))

    def mark_push_sent(self, token, day):
        """True if this call claimed the day's notification; False if it was already claimed."""
        try:
            self.table.update_item(
                Key={"PK": _pk(token), "SK": f"DAY#{day}"},
                UpdateExpression="SET push_sent = :yes",
                ConditionExpression="attribute_exists(PK) AND attribute_not_exists(push_sent)",
                ExpressionAttributeValues={":yes": True},
            )
            return True
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise

    def put_push(self, token, sub):
        self.table.put_item(Item={"PK": _pk(token), "SK": _push_sk(sub["endpoint"]), "data": dumps(sub)})

    def push_subscriptions(self, token):
        return [loads(item["data"]) for item in self._items(token, "PUSH#")]

    def delete_push(self, token, endpoint):
        self.table.delete_item(Key={"PK": _pk(token), "SK": _push_sk(endpoint)})

    def delete_field(self, token):
        with self.table.batch_writer() as batch:
            for item in self._query({"KeyConditionExpression": Key("PK").eq(_pk(token))}):
                batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
