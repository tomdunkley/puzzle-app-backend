import random
import uuid
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.db import (
    achievements_table,
    friend_requests_table,
    friendships_table,
    identities_table,
    password_reset_codes_table,
    users_table,
    verification_codes_table,
)

# Mirrors the icons in the Android client's AvatarIcon.kt.
# Base set (available to everyone) + achievement-unlocked set.
VALID_AVATAR_IDS = frozenset(
    {
        # Default
        "person",
        # Unlocked by achievements
        "numbers", "words", "friend", "flex", "taunt", "owl", "eight", "meta", "queen", "santa",
        "sunglasses", "bullseye",
        # Streak achievements
        "fire", "bolt_icon", "star_icon", "shield", "coffee", "anchor",
        "heart", "music", "snowflake", "sun_icon", "lotus", "pizza",
        # Other achievements
        "cake", "egg", "raven",
        # Routes achievements
        "route", "map", "compass", "trail", "globe", "mountain", "wave", "mouse", "tree", "car",
    }
)
_AVATAR_ID_LIST = sorted(VALID_AVATAR_IDS)

# Base colors (always available) + achievement-unlocked colors.
VALID_AVATAR_COLOR_IDS = frozenset({"red", "green", "blue", "orange", "gold", "black", "silver", "purple", "teal", "pink", "lime"})
_AVATAR_COLOR_ID_LIST = sorted(VALID_AVATAR_COLOR_IDS)


class DisplayNameTakenError(Exception):
    pass


class EmailTakenError(Exception):
    pass


class InvalidAvatarIdError(Exception):
    pass


class InvalidAvatarColorIdError(Exception):
    pass


class ProfanityError(Exception):
    pass


_PROFANITY = frozenset({
    "fuck", "shit", "cunt", "nigger", "nigga", "faggot", "fag", "bitch",
    "asshole", "bastard", "cock", "dick", "pussy", "twat", "wank", "wanker",
    "piss", "arse", "arsehole", "bollocks", "tosser", "shite", "prick",
    "motherfucker", "motherfucking", "fucking", "fucker",
})


def _contains_profanity(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in _PROFANITY)


_GUEST_TTL_SECONDS = 24 * 60 * 60


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _yesterday(date_iso: str) -> str:
    return (datetime.fromisoformat(date_iso).date() - timedelta(days=1)).isoformat()


def get_user(user_id: str) -> dict | None:
    response = users_table.get_item(Key={"user_id": user_id})
    return response.get("Item")


def find_identity(provider: str, provider_subject: str) -> dict | None:
    response = identities_table.get_item(
        Key={"provider": provider, "provider_subject": provider_subject}
    )
    return response.get("Item")


def list_identity_providers(user_id: str) -> set[str]:
    response = identities_table.query(
        IndexName="byUserId",
        KeyConditionExpression="user_id = :uid",
        ExpressionAttributeValues={":uid": user_id},
    )
    return {item["provider"] for item in response.get("Items", [])}


def create_password_identity(user_id: str, email: str, password_hash: str) -> None:
    identities_table.put_item(
        Item={
            "provider": "password",
            "provider_subject": email,
            "user_id": user_id,
            "password_hash": password_hash,
            "created_at": _now_iso(),
        }
    )


def create_google_identity(user_id: str, google_sub: str) -> None:
    identities_table.put_item(
        Item={
            "provider": "google",
            "provider_subject": google_sub,
            "user_id": user_id,
            "created_at": _now_iso(),
        }
    )


def find_user_by_display_name_lower(display_name_lower: str) -> dict | None:
    response = users_table.query(
        IndexName="byDisplayNameLower",
        KeyConditionExpression="display_name_lower = :name",
        ExpressionAttributeValues={":name": display_name_lower},
    )
    items = response.get("Items", [])
    return items[0] if items else None


def find_user_by_email_lower(email_lower: str) -> dict | None:
    response = users_table.query(
        IndexName="byEmailLower",
        KeyConditionExpression="email_lower = :email",
        ExpressionAttributeValues={":email": email_lower},
    )
    items = response.get("Items", [])
    return items[0] if items else None


def create_guest_user() -> dict:
    """Creates a throwaway account for someone playing without signing in: no
    identity (no password/Google), auto-verified since there's no email to verify,
    and tagged with a TTL so it's garbage-collected about a day later if never
    claimed. Guests never accrue a streak -- score_service skips that update for them.
    """
    user_id = f"g_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    display_name = f"Guest{random.randint(1000, 9999)}"
    user = {
        "user_id": user_id,
        "display_name": display_name,
        "display_name_lower": display_name.lower(),
        "created_at": now.isoformat(),
        "email_verified": True,
        "is_guest": True,
        "avatar_id": "person",
        "avatar_color_id": random.choice(["red", "green", "blue", "orange"]),
        "guest_expires_at_epoch": int((now + timedelta(seconds=_GUEST_TTL_SECONDS)).timestamp()),
    }
    users_table.put_item(Item=user)
    return user


def delete_guest_user(user_id: str) -> None:
    users_table.delete_item(Key={"user_id": user_id})


def create_user_with_identity(
    provider: str,
    provider_subject: str,
    display_name: str,
    password_hash: str | None = None,
    email: str | None = None,
    email_verified: bool = False,
) -> dict:
    """Creates a new user and links it to the given identity (e.g. a Google account or
    an email+password pair). password_hash is only set for provider="password".

    Raises EmailTakenError if another user (under a *different* identity provider)
    already has this email -- e.g. registering with a password using an email that
    was already used to sign in with Google. Same-provider duplicates are caught
    earlier, by the identity table's own unique (provider, provider_subject) key.
    """
    if _contains_profanity(display_name):
        raise ProfanityError(display_name)
    email_lower = email.strip().lower() if email is not None else None
    if email_lower is not None and find_user_by_email_lower(email_lower) is not None:
        raise EmailTakenError(email)

    user_id = f"u_{uuid.uuid4().hex[:12]}"
    user = {
        "user_id": user_id,
        "display_name": display_name,
        "display_name_lower": display_name.strip().lower(),
        "created_at": _now_iso(),
        "email_verified": email_verified,
        "avatar_id": "person",
        "avatar_color_id": random.choice(["red", "green", "blue", "orange"]),
    }
    if email is not None:
        user["email"] = email
        user["email_lower"] = email_lower
    users_table.put_item(Item=user)

    identity = {
        "provider": provider,
        "provider_subject": provider_subject,
        "user_id": user_id,
        "created_at": _now_iso(),
    }
    if password_hash is not None:
        identity["password_hash"] = password_hash
    identities_table.put_item(Item=identity)

    return user


def generate_display_name(max_attempts: int = 20) -> str:
    from app.data.wordlist import ADJECTIVES, NOUNS
    for _ in range(max_attempts):
        name = f"{random.choice(ADJECTIVES)}{random.choice(NOUNS)}{random.randint(10, 99)}"
        if find_user_by_display_name_lower(name.lower()) is None:
            return name
    return f"{random.choice(ADJECTIVES)}{random.choice(NOUNS)}{random.randint(1000, 9999)}"


def get_or_create_user_for_identity(
    provider: str,
    provider_subject: str,
    display_name: str | None = None,
    email: str | None = None,
    email_verified: bool = False,
) -> dict:
    identity = find_identity(provider, provider_subject)
    if identity is not None:
        user = get_user(identity["user_id"])
        if user is not None:
            return user

    if display_name is None:
        display_name = generate_display_name()

    return create_user_with_identity(
        provider, provider_subject, display_name, email=email, email_verified=email_verified
    )


_VALID_ICON_COLORS = frozenset({"black", "white", "silver"})


def record_last_login(user_id: str, platform: str) -> None:
    """Records last_login_at and last_login_platform on the user row."""
    users_table.update_item(
        Key={"user_id": user_id},
        UpdateExpression="SET last_login_at = :at, last_login_platform = :pl",
        ExpressionAttributeValues={":at": _now_iso(), ":pl": platform},
    )


def update_profile(
    user_id: str,
    display_name: str | None = None,
    avatar_id: str | None = None,
    avatar_color_id: str | None = None,
    avatar_icon_color: str | None = None,
    visible_on_global_leaderboard: bool | None = None,
) -> dict:
    """Updates the caller's own display name, avatar, and/or avatar color. Any field
    may be omitted (None) to leave it unchanged.
    """
    if avatar_id is not None and avatar_id not in VALID_AVATAR_IDS:
        raise InvalidAvatarIdError(avatar_id)
    if avatar_color_id is not None and avatar_color_id not in VALID_AVATAR_COLOR_IDS:
        raise InvalidAvatarColorIdError(avatar_color_id)
    if avatar_icon_color is not None and avatar_icon_color not in _VALID_ICON_COLORS:
        raise ValueError(f"Invalid icon color: {avatar_icon_color}")

    updates: dict = {}
    if display_name is not None:
        if _contains_profanity(display_name):
            raise ProfanityError(display_name)
        existing = find_user_by_display_name_lower(display_name.strip().lower())
        if existing is not None and existing["user_id"] != user_id:
            raise DisplayNameTakenError(display_name)
        updates["display_name"] = display_name
        updates["display_name_lower"] = display_name.strip().lower()
    if avatar_id is not None:
        updates["avatar_id"] = avatar_id
    if avatar_color_id is not None:
        updates["avatar_color_id"] = avatar_color_id
    if avatar_icon_color is not None:
        updates["avatar_icon_color"] = avatar_icon_color
    if visible_on_global_leaderboard is not None:
        updates["visible_on_global_leaderboard"] = visible_on_global_leaderboard

    if not updates:
        return get_user(user_id)

    set_clause = ", ".join(f"{key} = :{key}" for key in updates)
    users_table.update_item(
        Key={"user_id": user_id},
        UpdateExpression=f"SET {set_clause}",
        ExpressionAttributeValues={f":{key}": value for key, value in updates.items()},
    )
    return get_user(user_id)


def update_password_hash(provider_subject: str, password_hash: str) -> None:
    identities_table.update_item(
        Key={"provider": "password", "provider_subject": provider_subject},
        UpdateExpression="SET password_hash = :h",
        ExpressionAttributeValues={":h": password_hash},
    )


def mark_email_verified(user_id: str) -> None:
    users_table.update_item(
        Key={"user_id": user_id},
        UpdateExpression="SET email_verified = :true",
        ExpressionAttributeValues={":true": True},
    )


def get_email_verified(user_id: str) -> bool:
    user = get_user(user_id)
    return bool((user or {}).get("email_verified", False))


def is_developer(user_id: str) -> bool:
    user = get_user(user_id)
    if not user:
        return False
    if user.get("is_developer"):
        return True
    email = user.get("email")
    return bool(email) and email.strip().lower() in settings.developer_emails


def update_streak_for_play(user_id: str, game: str, played_date: str) -> dict:
    """Advances the given game's streak for a play on `played_date` (the puzzle's own
    date, not "today", so this stays correct under test/replay scenarios). Idempotent
    per date: calling this twice for the same date (e.g. a resubmitted best score)
    does not double-count.
    """
    user = get_user(user_id)
    streaks = (user or {}).get("streaks", {})
    streak = streaks.get(game, {"current": 0, "longest": 0, "last_played_date": None})

    if streak["last_played_date"] == played_date:
        return streak

    if streak["last_played_date"] == _yesterday(played_date):
        streak["current"] += 1
    else:
        streak["current"] = 1
    streak["longest"] = max(streak["longest"], streak["current"])
    streak["last_played_date"] = played_date

    streaks[game] = streak
    users_table.update_item(
        Key={"user_id": user_id},
        UpdateExpression="SET streaks = :streaks",
        ExpressionAttributeValues={":streaks": streaks},
    )
    return streak


def delete_account(user_id: str) -> None:
    """Permanently deletes a user and all associated data across every table."""
    # Identities (password / google) — query via byUserId GSI
    identity_items = identities_table.query(
        IndexName="byUserId",
        KeyConditionExpression="user_id = :uid",
        ExpressionAttributeValues={":uid": user_id},
    ).get("Items", [])
    for identity in identity_items:
        identities_table.delete_item(
            Key={"provider": identity["provider"], "provider_subject": identity["provider_subject"]}
        )

    # Friendships — query all where this user is the requester, then delete both directions
    friend_items = friendships_table.query(
        KeyConditionExpression="user_id = :uid",
        ExpressionAttributeValues={":uid": user_id},
    ).get("Items", [])
    for item in friend_items:
        friendships_table.delete_item(Key={"user_id": user_id, "friend_id": item["friend_id"]})
        friendships_table.delete_item(Key={"user_id": item["friend_id"], "friend_id": user_id})

    # Friend requests — incoming (PK) and outgoing (GSI byFromUserId)
    incoming = friend_requests_table.query(
        KeyConditionExpression="to_user_id = :uid",
        ExpressionAttributeValues={":uid": user_id},
    ).get("Items", [])
    for item in incoming:
        friend_requests_table.delete_item(
            Key={"to_user_id": user_id, "from_user_id": item["from_user_id"]}
        )
    outgoing = friend_requests_table.query(
        IndexName="byFromUserId",
        KeyConditionExpression="from_user_id = :uid",
        ExpressionAttributeValues={":uid": user_id},
    ).get("Items", [])
    for item in outgoing:
        friend_requests_table.delete_item(
            Key={"to_user_id": item["to_user_id"], "from_user_id": user_id}
        )

    # Single-row tables keyed by user_id
    achievements_table.delete_item(Key={"user_id": user_id})
    verification_codes_table.delete_item(Key={"user_id": user_id})
    password_reset_codes_table.delete_item(Key={"user_id": user_id})

    # User row last so auth still works if anything above fails mid-way
    users_table.delete_item(Key={"user_id": user_id})


def list_all_users() -> list[dict]:
    """Full table scan of all users (developer admin use only)."""
    items = []
    response = users_table.scan()
    items.extend(response.get("Items", []))
    while "LastEvaluatedKey" in response:
        response = users_table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))
    items.sort(key=lambda u: u.get("created_at", ""), reverse=True)
    return items


def admin_update_user(
    user_id: str,
    email_verified: bool | None = None,
    is_developer_flag: bool | None = None,
    visible_on_global_leaderboard: bool | None = None,
) -> dict | None:
    updates: dict = {}
    if email_verified is not None:
        updates["email_verified"] = email_verified
    if is_developer_flag is not None:
        updates["is_developer"] = is_developer_flag
    if visible_on_global_leaderboard is not None:
        updates["visible_on_global_leaderboard"] = visible_on_global_leaderboard
    if not updates:
        return get_user(user_id)
    set_clause = ", ".join(f"#{key} = :{key}" for key in updates)
    users_table.update_item(
        Key={"user_id": user_id},
        UpdateExpression=f"SET {set_clause}",
        ExpressionAttributeNames={f"#{key}": key for key in updates},
        ExpressionAttributeValues={f":{key}": value for key, value in updates.items()},
    )
    return get_user(user_id)
