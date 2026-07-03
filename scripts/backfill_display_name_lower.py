# One-off: backfills display_name_lower onto every existing user row so they show
# up in the new byDisplayNameLower GSI. Safe to re-run (idempotent overwrite).
#
# Usage: AWS_PROFILE=td-puzzles python scripts/backfill_display_name_lower.py <UsersTableName>

import sys

import boto3


def main(table_name: str) -> None:
    table = boto3.resource("dynamodb", region_name="us-east-1").Table(table_name)

    updated = 0
    response = table.scan()
    while True:
        for item in response.get("Items", []):
            display_name = item.get("display_name", "")
            table.update_item(
                Key={"user_id": item["user_id"]},
                UpdateExpression="SET display_name_lower = :lower",
                ExpressionAttributeValues={":lower": display_name.strip().lower()},
            )
            updated += 1

        if "LastEvaluatedKey" not in response:
            break
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])

    print(f"Backfilled display_name_lower on {updated} user(s) in {table_name}")


if __name__ == "__main__":
    main(sys.argv[1])
