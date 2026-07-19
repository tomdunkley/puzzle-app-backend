"""
Deletes test/throwaway accounts from all relevant DynamoDB tables.
Run with: python cleanup_test_users.py
"""
import boto3

REGION = "us-east-1"
PROFILE = "td-puzzles"

session = boto3.Session(profile_name=PROFILE)
ddb = session.resource("dynamodb", region_name=REGION)

USERS_TABLE       = "td-puzzles-api-UsersTable-1AT91GSAC5CLY"
IDENTITIES_TABLE  = "td-puzzles-api-IdentitiesTable-SVATSFFX3JNN"
SCORES_TABLE      = "td-puzzles-api-ScoresTable-1MR0LE4CUF1VL"
FRIENDSHIPS_TABLE = "td-puzzles-api-FriendshipsTable-1KZIKJUXV1Z5K"
REQUESTS_TABLE    = "td-puzzles-api-FriendRequestsTable-1SI6KYNS1KZIA"
ACHIEVEMENTS_TABLE= "td-puzzles-api-AchievementsTable-48U437R65F7U"

# Test accounts to delete (user_id → display_name for confirmation)
TEST_USERS = {
    "u_2d427d346335": "abc123",
    "u_06d7687621c8": "DiagTest99887",
    "u_8d642dad69dc": "dte",
    "u_90ae09e665f5": "example user",
    "u_4ccae7cae7ee": "FeatureTest",
    "u_14907566d012": "GuestClaimTest",
    "u_cfcde94fa53e": "QaCheck",
    "u_81d2353d057f": "SettingsTester",
    "u_5265fad2ad67": "TestUser",
    "u_7722eacb51c2": "tud",
    "u_ffcd9aec8af5": "VerBugTest1",
    "u_2ce143feec86": "VerifyTest1",
    "u_0e4ecbe06d18": "VerifyTest2",
    "u_debca8ffa1dc": "VerifyTest3",
    "u_f5b9576698f1": "VerifyTest4",
    "u_6a5571acd4af": "VerifyTest5",
    "u_923af7f393e8": "WordTest",
    "u_c346f25ccb34": "jonfromgarfield",
    "u_f75d7bd2ff77": "Toby Hatchell",
}

users_table       = ddb.Table(USERS_TABLE)
identities_table  = ddb.Table(IDENTITIES_TABLE)
scores_table      = ddb.Table(SCORES_TABLE)
friendships_table = ddb.Table(FRIENDSHIPS_TABLE)
requests_table    = ddb.Table(REQUESTS_TABLE)
achievements_table= ddb.Table(ACHIEVEMENTS_TABLE)


def delete_user(user_id: str, display_name: str):
    print(f"\n--- Deleting {display_name} ({user_id}) ---")

    # 1. UsersTable
    users_table.delete_item(Key={"user_id": user_id})
    print(f"  Deleted from UsersTable")

    # 2. IdentitiesTable — query byUserId GSI
    resp = identities_table.query(
        IndexName="byUserId",
        KeyConditionExpression="user_id = :uid",
        ExpressionAttributeValues={":uid": user_id},
    )
    for item in resp.get("Items", []):
        identities_table.delete_item(Key={"provider": item["provider"], "provider_subject": item["provider_subject"]})
    print(f"  Deleted {len(resp.get('Items', []))} identity record(s)")

    # 3. ScoresTable — query byUserId GSI
    resp = scores_table.query(
        IndexName="byUserId",
        KeyConditionExpression="user_id = :uid",
        ExpressionAttributeValues={":uid": user_id},
    )
    for item in resp.get("Items", []):
        scores_table.delete_item(Key={"puzzle_id": item["puzzle_id"], "user_id": user_id})
    print(f"  Deleted {len(resp.get('Items', []))} score record(s)")

    # 4. FriendshipsTable — rows where user_id = X
    resp = friendships_table.query(
        KeyConditionExpression="user_id = :uid",
        ExpressionAttributeValues={":uid": user_id},
    )
    outgoing = resp.get("Items", [])
    for item in outgoing:
        friendships_table.delete_item(Key={"user_id": user_id, "friend_id": item["friend_id"]})
        # Also delete the reverse row
        friendships_table.delete_item(Key={"user_id": item["friend_id"], "friend_id": user_id})
    print(f"  Deleted {len(outgoing)} friendship pair(s)")

    # 5. FriendRequestsTable — rows where from_user_id = X (outgoing requests)
    resp = requests_table.query(
        IndexName="byFromUserId",
        KeyConditionExpression="from_user_id = :uid",
        ExpressionAttributeValues={":uid": user_id},
    )
    for item in resp.get("Items", []):
        requests_table.delete_item(Key={"to_user_id": item["to_user_id"], "from_user_id": user_id})
    # Rows where to_user_id = X (incoming requests)
    resp2 = requests_table.query(
        KeyConditionExpression="to_user_id = :uid",
        ExpressionAttributeValues={":uid": user_id},
    )
    for item in resp2.get("Items", []):
        requests_table.delete_item(Key={"to_user_id": user_id, "from_user_id": item["from_user_id"]})
    print(f"  Deleted friend request records")

    # 6. AchievementsTable
    achievements_table.delete_item(Key={"user_id": user_id})
    print(f"  Deleted achievements record")


if __name__ == "__main__":
    print(f"About to delete {len(TEST_USERS)} test accounts:")
    for uid, name in TEST_USERS.items():
        print(f"  {name} ({uid})")
    confirm = input("\nType 'yes' to proceed: ")
    if confirm.strip().lower() != "yes":
        print("Aborted.")
        exit(0)
    for uid, name in TEST_USERS.items():
        delete_user(uid, name)
    print("\nDone! All test users deleted.")
