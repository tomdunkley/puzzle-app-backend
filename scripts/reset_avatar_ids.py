"""One-off script: set every user's avatar_id to 'person'.

Run from the webapp/ directory:
    python scripts/reset_avatar_ids.py
"""
import boto3
from boto3.dynamodb.conditions import Attr

dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
table = dynamodb.Table("td-puzzles-UsersTable")

paginator = dynamodb.meta.client.get_paginator("scan")
pages = paginator.paginate(TableName=table.name, ProjectionExpression="user_id")

updated = 0
for page in pages:
    for item in page["Items"]:
        table.update_item(
            Key={"user_id": item["user_id"]},
            UpdateExpression="SET avatar_id = :p",
            ExpressionAttributeValues={":p": "person"},
        )
        updated += 1

print(f"Updated {updated} users.")
