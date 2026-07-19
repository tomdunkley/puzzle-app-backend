import uuid
from datetime import datetime, timezone

from app.db import scores_table
from app.services.boggle import score_words
from app.services.numbers_game import validate_numbers_attempt
from app.services.puzzle_service import get_puzzle
from app.services.user_service import get_user, update_streak_for_play


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PuzzleNotFoundError(Exception):
    pass


class ScoreNotFoundError(Exception):
    pass


def _ranking_key(item: dict) -> tuple[int, int]:
    """Higher is always better, so every caller can sort(reverse=True) regardless of
    game. Boggle ties on score are broken by word count. Numbers ranks by closeness
    to the target (so distance is negated -- 0 away is the best possible) and ties
    on an exact match are broken by who took less time.
    """
    if item.get("game") == "numbers":
        distance = item.get("distance", 10**9)
        duration = item.get("duration_seconds", 10**9)
        return (-distance, -duration)
    return (item.get("score", 0), len(item.get("valid_words", [])))


def submit_score(
    puzzle_id: str,
    user_id: str,
    duration_seconds: int,
    words: list[str] | None = None,
    result_value: int | None = None,
    steps: list[dict] | None = None,
) -> dict:
    """Re-validates every submission against the puzzle's real data server-side --
    Boggle words against the board and dictionary, Numbers steps against the actual
    starting numbers -- and keeps the user's best attempt per puzzle. The client's
    claim is always evidence, never a trusted result.
    """
    puzzle = get_puzzle(puzzle_id)
    if puzzle is None:
        raise PuzzleNotFoundError(puzzle_id)

    game = puzzle["game"]
    if game == "numbers":
        validated = validate_numbers_attempt(puzzle["numbers"], puzzle["target"], result_value, steps or [])
        new_fields = {
            "game": "numbers",
            "result_value": validated["result_value"],
            "distance": validated["distance"],
            "steps": validated["steps"],
        }
    else:
        valid_words, score = score_words(puzzle["board"], words or [])
        new_fields = {"game": "boggle", "score": score, "valid_words": valid_words}

    existing = scores_table.get_item(Key={"puzzle_id": puzzle_id, "user_id": user_id}).get("Item")
    candidate = {**new_fields, "duration_seconds": duration_seconds}
    if existing is not None and _ranking_key(existing) >= _ranking_key(candidate):
        return {**existing, "current_streak": _current_streak(user_id, game), "is_new_daily_best": False}

    # Guests never accrue a streak -- they have no persistent identity to track one
    # against, and a claimed guest score gets its streak applied separately, once,
    # against the real account it lands on (see guest_service.claim_guest_score_for_today).
    user = get_user(user_id)
    is_guest = bool((user or {}).get("is_guest"))
    if existing is None and not is_guest:
        update_streak_for_play(user_id, game, puzzle["date"])

    item = {
        "puzzle_id": puzzle_id,
        "user_id": user_id,
        "score_id": existing["score_id"] if existing else f"sc_{uuid.uuid4().hex[:12]}",
        "duration_seconds": duration_seconds,
        "submitted_at": _now_iso(),
        **new_fields,
    }
    # A guest who never signs in would otherwise leave this row behind forever after
    # their UsersTable record expires (claiming deletes it explicitly instead -- see
    # guest_service.claim_guest_score_for_today). Piggyback on the guest's own expiry
    # so the two disappear together, rather than tracking a second TTL clock.
    if is_guest and user is not None and "guest_expires_at_epoch" in user:
        item["guest_expires_at_epoch"] = user["guest_expires_at_epoch"]
    scores_table.put_item(Item=item)
    return {**item, "current_streak": _current_streak(user_id, game), "is_new_daily_best": True}


def _current_streak(user_id: str, game: str) -> int:
    user = get_user(user_id)
    streaks = (user or {}).get("streaks", {})
    return streaks.get(game, {}).get("current", 0)


def _all_scores_for_puzzle(puzzle_id: str) -> list[dict]:
    # Hobby-scale assumption: one puzzle's score list comfortably fits in a single Query
    # page. Revisit with pagination (ExclusiveStartKey) if a puzzle ever gets thousands
    # of players.
    response = scores_table.query(
        KeyConditionExpression="puzzle_id = :pid",
        ExpressionAttributeValues={":pid": puzzle_id},
    )
    return response.get("Items", [])


def get_user_score_item(puzzle_id: str, user_id: str) -> dict | None:
    return scores_table.get_item(Key={"puzzle_id": puzzle_id, "user_id": user_id}).get("Item")


def get_daily_scores_for_user(user_id: str, game: str) -> list[dict]:
    """All daily (not unlimited) puzzle scores for a user for a given game."""
    unlimited_prefix = f"{game}_unlimited_"
    response = scores_table.query(
        IndexName="byUserId",
        KeyConditionExpression="user_id = :uid AND begins_with(puzzle_id, :prefix)",
        ExpressionAttributeValues={":uid": user_id, ":prefix": f"{game}_"},
    )
    return [item for item in response.get("Items", []) if not item["puzzle_id"].startswith(unlimited_prefix)]


def get_daily_best(user_id: str, game: str) -> dict | None:
    """The user's best daily score for a game (None if never played)."""
    scores = get_daily_scores_for_user(user_id, game)
    if not scores:
        return None
    return max(scores, key=_ranking_key)


def get_today_score_for_user(user_id: str, game: str) -> dict | None:
    """The user's score for today's daily puzzle (None if not played today)."""
    today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return get_user_score_item(f"{game}_{today_iso}", user_id)


def has_played(puzzle_id: str, user_id: str) -> bool:
    return get_user_score_item(puzzle_id, user_id) is not None


def _counts_toward_global_rank(user: dict | None) -> bool:
    if user is None:
        return True
    if user.get("is_test_account"):
        return False
    return user.get("visible_on_global_leaderboard", True)


def get_rank(puzzle_id: str, user_id: str) -> int | None:
    """The user's global rank for this puzzle -- None if they've opted out of the
    global leaderboard themselves (they shouldn't see a global rank for the same
    reason their own score is excluded from everyone else's). Opted-out users' scores
    are also excluded from the ranking pool entirely, so they never affect anyone
    else's rank either.
    """
    requester = get_user(user_id)
    if not _counts_toward_global_rank(requester):
        return None

    scores = [
        item
        for item in _all_scores_for_puzzle(puzzle_id)
        if _counts_toward_global_rank(get_user(item["user_id"]))
    ]
    scores.sort(key=_ranking_key, reverse=True)
    for rank, item in enumerate(scores, start=1):
        if item["user_id"] == user_id:
            return rank
    return None


def get_score_detail(puzzle_id: str, user_id: str, requesting_user_id: str) -> dict:
    """`requesting_user_id` is whoever is asking (often, but not always, `user_id`
    themselves) -- if they haven't completed this same puzzle yet, the puzzle's own
    content (board/numbers/target/words/steps) is withheld so viewing a leaderboard
    entry can never spoil today's puzzle for someone who hasn't played it yet.
    """
    item = scores_table.get_item(Key={"puzzle_id": puzzle_id, "user_id": user_id}).get("Item")
    if item is None:
        raise ScoreNotFoundError()

    puzzle = get_puzzle(puzzle_id)
    user = get_user(user_id)
    game = item.get("game", "boggle")
    locked = requesting_user_id != user_id and not has_played(puzzle_id, requesting_user_id)
    detail = {
        "puzzle_id": puzzle_id,
        "user_id": user_id,
        "display_name": user["display_name"] if user else "Unknown",
        "avatar_id": user.get("avatar_id") if user else None,
        "avatar_color_id": user.get("avatar_color_id") if user else None,
        "avatar_icon_color": user.get("avatar_icon_color") if user else None,
        "game": game,
        "rank_today": get_rank(puzzle_id, user_id) or 0,
        "locked": locked,
    }
    if game == "numbers":
        detail.update(
            {
                "numbers": puzzle["numbers"] if puzzle and not locked else None,
                "target": puzzle["target"] if puzzle and not locked else None,
                "result_value": item.get("result_value"),
                "distance": item.get("distance"),
                "duration_seconds": item.get("duration_seconds"),
                "steps": item.get("steps", []) if not locked else None,
            }
        )
    else:
        detail.update(
            {
                "score": item["score"],
                "valid_words": item["valid_words"] if not locked else None,
                "board": (puzzle["board"] if puzzle else []) if not locked else None,
            }
        )
    return detail


def _leaderboard_entry(rank: int, item: dict, user: dict | None) -> dict:
    entry = {
        "rank": rank,
        "user_id": item["user_id"],
        "display_name": user["display_name"] if user else "Unknown",
        "avatar_id": user.get("avatar_id") if user else None,
        "avatar_color_id": user.get("avatar_color_id") if user else None,
        "avatar_icon_color": user.get("avatar_icon_color") if user else None,
        "game": item.get("game", "boggle"),
    }
    if entry["game"] == "numbers":
        entry["result_value"] = item.get("result_value")
        entry["distance"] = item.get("distance")
        entry["duration_seconds"] = item.get("duration_seconds")
    else:
        entry["score"] = item.get("score", 0)
        entry["word_count"] = len(item.get("valid_words", []))
    return entry


def get_leaderboard(puzzle_id: str, user_ids: set[str] | None = None) -> list[dict]:
    """If user_ids is given, restricts the leaderboard to that set (e.g. a friends scope)."""
    scores = _all_scores_for_puzzle(puzzle_id)
    if user_ids is not None:
        scores = [item for item in scores if item["user_id"] in user_ids]
    users = {item["user_id"]: get_user(item["user_id"]) for item in scores}
    scores = [s for s in scores if not (users[s["user_id"]] or {}).get("is_test_account")]
    scores.sort(key=_ranking_key, reverse=True)
    return [
        _leaderboard_entry(rank, item, users[item["user_id"]])
        for rank, item in enumerate(scores, start=1)
    ]


def get_global_leaderboard(puzzle_id: str, limit: int = 10) -> list[dict]:
    """Top `limit` scores across everyone, skipping guests (no persistent identity to
    show on a public board) and anyone who's opted out via
    UsersTable.visible_on_global_leaderboard (defaults to True/visible when absent).
    Ranks are contiguous over the *visible* entries only -- a skipped player simply
    never appears, rather than leaving a gap in the numbering.
    """
    scores = _all_scores_for_puzzle(puzzle_id)
    scores.sort(key=_ranking_key, reverse=True)

    entries = []
    for item in scores:
        user = get_user(item["user_id"])
        if user is not None and (user.get("is_guest") or not user.get("visible_on_global_leaderboard", True) or user.get("is_test_account")):
            continue
        entries.append(_leaderboard_entry(len(entries) + 1, item, user))
        if len(entries) >= limit:
            break
    return entries
