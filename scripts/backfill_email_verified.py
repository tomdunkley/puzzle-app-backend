# One-off: every user created before email verification existed has no email_verified
# attribute at all, and get_email_verified() defaults a missing attribute to False --
# which would incorrectly block pre-existing accounts (dev-login, Google, old password
# signups) from gameplay. They were never subject to the verification requirement when
# they signed up, so backfill them as verified rather than retroactively gating them.
# Safe to re-run: only touches rows missing the attribute.
#
# Usage: AWS_PROFILE=td-puzzles python scripts/backfill_email_verified.py <UsersTableName>

import sys

import boto3


def main(table_name: str) -> None:
    table = boto3.resource("dynamodb", region_name="us-east-1").Table(table_name)

    updated = 0
    response = table.scan()
    while True:
        for item in response.get("Items", []):
            if "email_verified" in item:
                continue
            table.update_item(
                Key={"user_id": item["user_id"]},
                UpdateExpression="SET email_verified = :true",
                ExpressionAttributeValues={":true": True},
            )
            updated += 1

        if "LastEvaluatedKey" not in response:
            break
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])

    print(f"Backfilled email_verified=true on {updated} pre-existing user(s) in {table_name}")


if __name__ == "__main__":
    main(sys.argv[1])
