# One-off: resets every user's avatar_id to "person" and avatar_color_id to "red".
# Safe to re-run (idempotent overwrite).
#
# Usage: AWS_PROFILE=td-puzzles python scripts/reset_user_avatars.py <UsersTableName>

import sys

import boto3


def main(table_name: str) -> None:
    table = boto3.resource("dynamodb", region_name="us-east-1").Table(table_name)

    updated = 0
    response = table.scan()
    while True:
        for item in response.get("Items", []):
            table.update_item(
                Key={"user_id": item["user_id"]},
                UpdateExpression="SET avatar_id = :aid, avatar_color_id = :cid",
                ExpressionAttributeValues={":aid": "person", ":cid": "red"},
            )
            updated += 1

        if "LastEvaluatedKey" not in response:
            break
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])

    print(f"Reset avatar_id/avatar_color_id on {updated} user(s) in {table_name}")


if __name__ == "__main__":
    main(sys.argv[1])
