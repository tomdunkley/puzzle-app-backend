from datetime import datetime, timezone

from app.db import friend_requests_table, friendships_table, users_table
from app.services.achievement_service import check_and_award_on_friend_added
from app.services.user_service import find_identity, get_user


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CannotFriendSelfError(Exception):
    pass


class AlreadyFriendsError(Exception):
    pass


class FriendRequestAlreadyExistsError(Exception):
    pass


class FriendRequestNotFoundError(Exception):
    pass


def are_friends(user_id: str, other_user_id: str) -> bool:
    item = friendships_table.get_item(Key={"user_id": user_id, "friend_id": other_user_id}).get("Item")
    return item is not None


def _get_request(to_user_id: str, from_user_id: str) -> dict | None:
    return friend_requests_table.get_item(
        Key={"to_user_id": to_user_id, "from_user_id": from_user_id}
    ).get("Item")


def _create_friendship(user_id: str, friend_id: str) -> None:
    now = _now_iso()
    friendships_table.put_item(Item={"user_id": user_id, "friend_id": friend_id, "created_at": now})
    friendships_table.put_item(Item={"user_id": friend_id, "friend_id": user_id, "created_at": now})
    check_and_award_on_friend_added(user_id)
    check_and_award_on_friend_added(friend_id)


def send_friend_request(from_user_id: str, to_user_id: str) -> None:
    if from_user_id == to_user_id:
        raise CannotFriendSelfError()
    if are_friends(from_user_id, to_user_id):
        raise AlreadyFriendsError()

    # If the other person already sent *us* a request, mutual interest is
    # detected -- skip the request step entirely and become friends now.
    reverse_request = _get_request(to_user_id=from_user_id, from_user_id=to_user_id)
    if reverse_request is not None:
        friend_requests_table.delete_item(Key={"to_user_id": from_user_id, "from_user_id": to_user_id})
        _create_friendship(from_user_id, to_user_id)
        return

    if _get_request(to_user_id=to_user_id, from_user_id=from_user_id) is not None:
        raise FriendRequestAlreadyExistsError()

    friend_requests_table.put_item(
        Item={"to_user_id": to_user_id, "from_user_id": from_user_id, "created_at": _now_iso()}
    )


def accept_friend_request(user_id: str, from_user_id: str) -> None:
    if _get_request(to_user_id=user_id, from_user_id=from_user_id) is None:
        raise FriendRequestNotFoundError()
    friend_requests_table.delete_item(Key={"to_user_id": user_id, "from_user_id": from_user_id})
    _create_friendship(user_id, from_user_id)


def decline_friend_request(user_id: str, from_user_id: str) -> None:
    if _get_request(to_user_id=user_id, from_user_id=from_user_id) is None:
        raise FriendRequestNotFoundError()
    friend_requests_table.delete_item(Key={"to_user_id": user_id, "from_user_id": from_user_id})


def unfriend(user_id: str, friend_id: str) -> None:
    friendships_table.delete_item(Key={"user_id": user_id, "friend_id": friend_id})
    friendships_table.delete_item(Key={"user_id": friend_id, "friend_id": user_id})


def list_friends(user_id: str) -> list[dict]:
    response = friendships_table.query(
        KeyConditionExpression="user_id = :uid",
        ExpressionAttributeValues={":uid": user_id},
    )
    friends = []
    for item in response.get("Items", []):
        user = get_user(item["friend_id"])
        if user is not None:
            friends.append(user)
    return friends


def list_incoming_requests(user_id: str) -> list[dict]:
    response = friend_requests_table.query(
        KeyConditionExpression="to_user_id = :uid",
        ExpressionAttributeValues={":uid": user_id},
    )
    senders = []
    for item in response.get("Items", []):
        user = get_user(item["from_user_id"])
        if user is not None:
            senders.append(user)
    return senders


def list_outgoing_requests(user_id: str) -> list[dict]:
    response = friend_requests_table.query(
        IndexName="byFromUserId",
        KeyConditionExpression="from_user_id = :uid",
        ExpressionAttributeValues={":uid": user_id},
    )
    recipients = []
    for item in response.get("Items", []):
        user = get_user(item["to_user_id"])
        if user is not None:
            recipients.append(user)
    return recipients


def _friendship_status(requesting_user_id: str, candidate_user_id: str) -> str:
    if are_friends(requesting_user_id, candidate_user_id):
        return "friends"
    if _get_request(to_user_id=candidate_user_id, from_user_id=requesting_user_id) is not None:
        return "request_sent"
    if _get_request(to_user_id=requesting_user_id, from_user_id=candidate_user_id) is not None:
        return "request_received"
    return "none"


def get_friendship_status(requesting_user_id: str, candidate_user_id: str) -> str:
    if requesting_user_id == candidate_user_id:
        return "self"
    return _friendship_status(requesting_user_id, candidate_user_id)


def search_users(query: str, requesting_user_id: str) -> list[dict]:
    """Hobby-scale search: an exact email lookup (via the existing password-identity
    index) if `query` looks like an email, otherwise a full table scan with a
    case-insensitive `contains` filter on display_name. Fine for a small user base;
    would need real search infra (or at least a prefix-indexable shadow attribute)
    at a much larger scale -- same precedent as score_service's full-scan leaderboard.
    """
    candidates: list[dict] = []

    if "@" in query:
        identity = find_identity("password", query.strip().lower())
        if identity is not None:
            user = get_user(identity["user_id"])
            if user is not None:
                candidates.append(user)
    else:
        needle = query.strip().lower()
        if needle:
            response = users_table.scan()
            for user in response.get("Items", []):
                if needle in user.get("display_name", "").lower():
                    candidates.append(user)

    results = []
    for user in candidates:
        if user["user_id"] == requesting_user_id:
            continue
        if user.get("is_test_account"):
            continue
        results.append(
            {
                "user_id": user["user_id"],
                "display_name": user["display_name"],
                "avatar_id": user.get("avatar_id"),
                "avatar_color_id": user.get("avatar_color_id"),
                "avatar_icon_color": user.get("avatar_icon_color"),
                "friendship_status": _friendship_status(requesting_user_id, user["user_id"]),
            }
        )
    return results[:20]
