# One-off: replaces spaces with underscores in display_name (and display_name_lower)
# for any user whose current display name contains a space.
# Safe to re-run (skips users already without spaces).
#
# Usage: AWS_PROFILE=td-puzzles python scripts/backfill_spaces_in_names.py <UsersTableName>

import sys

import boto3


def main(table_name: str) -> None:
    table = boto3.resource("dynamodb", region_name="us-east-1").Table(table_name)

    updated = 0
    skipped = 0
    conflicts = []

    # Collect all users first so we can detect conflicts before writing.
    all_users = []
    response = table.scan()
    while True:
        all_users.extend(response.get("Items", []))
        if "LastEvaluatedKey" not in response:
            break
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])

    existing_lower = {u["display_name_lower"] for u in all_users if "display_name_lower" in u}

    for item in all_users:
        display_name = item.get("display_name", "")
        if " " not in display_name:
            skipped += 1
            continue

        new_name = display_name.replace(" ", "_")
        new_lower = new_name.lower()

        # Check for conflict with another user (excluding self).
        old_lower = item.get("display_name_lower", display_name.lower())
        if new_lower != old_lower and new_lower in existing_lower:
            conflicts.append({
                "user_id": item["user_id"],
                "old": display_name,
                "new": new_name,
            })
            print(f"  CONFLICT: '{display_name}' -> '{new_name}' already taken — skipping {item['user_id']}")
            continue

        table.update_item(
            Key={"user_id": item["user_id"]},
            UpdateExpression="SET display_name = :name, display_name_lower = :lower",
            ExpressionAttributeValues={":name": new_name, ":lower": new_lower},
        )
        # Update our in-memory set so later iterations see the new name.
        existing_lower.discard(old_lower)
        existing_lower.add(new_lower)
        print(f"  Updated: '{display_name}' -> '{new_name}'  ({item['user_id']})")
        updated += 1

    print(f"\nDone. Updated {updated}, skipped {skipped} (no spaces), conflicts {len(conflicts)}.")


if __name__ == "__main__":
    main(sys.argv[1])
