"""
One-shot script: assign a random avatar_id and avatar_color_id to every user in
UsersTable that doesn't already have one set.

Run from the webapp/ directory:
    $env:AWS_PROFILE = "td-puzzles"
    python scripts/backfill_avatar.py

Safe to re-run: only updates rows where one or both fields are absent.
"""

import random
import sys

import boto3

USERS_TABLE = "td-puzzles-users"
REGION = "us-east-1"

AVATAR_IDS = ["smiley", "pizza", "sun", "lightning", "football", "wine", "paw", "dice"]
COLOR_IDS = ["red", "green", "blue", "orange"]


def main() -> None:
    dynamo = boto3.resource("dynamodb", region_name=REGION)
    table = dynamo.Table(USERS_TABLE)

    paginator = dynamo.meta.client.get_paginator("scan")
    pages = paginator.paginate(TableName=USERS_TABLE)

    updated = 0
    skipped = 0

    for page in pages:
        for item in page["Items"]:
            user_id = item.get("user_id")
            if not user_id:
                continue

            has_avatar = bool(item.get("avatar_id"))
            has_color = bool(item.get("avatar_color_id"))

            if has_avatar and has_color:
                skipped += 1
                continue

            update_expr_parts = []
            expr_values = {}

            if not has_avatar:
                update_expr_parts.append("avatar_id = :a")
                expr_values[":a"] = random.choice(AVATAR_IDS)

            if not has_color:
                update_expr_parts.append("avatar_color_id = :c")
                expr_values[":c"] = random.choice(COLOR_IDS)

            table.update_item(
                Key={"user_id": user_id},
                UpdateExpression="SET " + ", ".join(update_expr_parts),
                ExpressionAttributeValues=expr_values,
            )
            updated += 1
            print(
                f"  updated {user_id}: "
                + (f"avatar={expr_values.get(':a', item.get('avatar_id'))}" )
                + f"  color={expr_values.get(':c', item.get('avatar_color_id'))}"
            )

    print(f"\nDone — {updated} updated, {skipped} already had both fields.")


if __name__ == "__main__":
    main()
