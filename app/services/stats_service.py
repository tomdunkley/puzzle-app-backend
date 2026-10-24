"""Stats stored on each user row; first places only count closed days (scheduled jobs in app/jobs.py)."""
import re
from datetime import date, timedelta
from decimal import Decimal

from app.data.achievements import ACHIEVEMENTS
from app.db import friendships_table, scores_table, users_table
from app.services.achievement_service import get_unlocked
from app.services.puzzle_service import today_iso
from app.services.score_service import _counts_toward_global_rank, _ranking_key
from app.services.user_service import get_user, list_all_users

_GAMES = ("boggle", "numbers", "routes")
_RESPONSE_KEY = {"boggle": "words", "numbers": "numbers", "routes": "routes"}
_DAILY_ID = re.compile(r"^(boggle|numbers|routes)_(\d{4}-\d{2}-\d{2})$")
_LONG_WORD_LENGTH = 8


def _query_all(table, **kwargs) -> list[dict]:
    items: list[dict] = []
    while True:
        response = table.query(**kwargs)
        items.extend(response.get("Items", []))
        if "LastEvaluatedKey" not in response:
            return items
        kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]


def _plain(value):
    if isinstance(value, Decimal):
        return int(value)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def _last_closed_day() -> str:
    return (date.fromisoformat(today_iso()) - timedelta(days=1)).isoformat()


def _daily_scores(user_id: str, game: str, projection: str | None = None) -> list[dict]:
    kwargs = {
        "IndexName": "byUserId",
        "KeyConditionExpression": "user_id = :uid AND begins_with(puzzle_id, :prefix)",
        "ExpressionAttributeValues": {":uid": user_id, ":prefix": f"{game}_"},
    }
    if projection:
        kwargs["ProjectionExpression"] = projection
    return [s for s in _query_all(scores_table, **kwargs) if _DAILY_ID.match(s["puzzle_id"])]


# --- own stats (depend only on the user's own scores) ----------------------------------

def _words_own_stats(scores: list[dict]) -> dict:
    best = max(scores, key=_ranking_key) if scores else None
    longest_word, longest_puzzle = None, None
    total_words = long_words = 0
    for s in scores:
        words = s.get("valid_words", [])
        total_words += len(words)
        for w in words:
            if len(w) >= _LONG_WORD_LENGTH:
                long_words += 1
            if longest_word is None or len(w) > len(longest_word):
                longest_word, longest_puzzle = w, s["puzzle_id"]
    return {
        "completed": len(scores),
        "best_score": {
            "puzzle_id": best["puzzle_id"],
            "score": int(best.get("score", 0)),
            "word_count": len(best.get("valid_words", [])),
        } if best else None,
        "longest_word": {"puzzle_id": longest_puzzle, "word": longest_word} if longest_word else None,
        "total_words": total_words,
        "long_words": long_words,
    }


def _numbers_result(item: dict | None) -> dict | None:
    if item is None:
        return None
    return {
        "puzzle_id": item["puzzle_id"],
        "distance": int(item.get("distance", 0)),
        "result_value": int(item.get("result_value", 0)),
        "duration_seconds": int(item.get("duration_seconds", 0)),
    }


def _routes_result(item: dict | None) -> dict | None:
    if item is None:
        return None
    return {"puzzle_id": item["puzzle_id"], "duration_seconds": int(item.get("duration_seconds", 0))}


def _own_stats(game: str, scores: list[dict]) -> dict:
    if game == "boggle":
        return _words_own_stats(scores)
    to_result = _numbers_result if game == "numbers" else _routes_result
    return {
        "completed": len(scores),
        "best": to_result(max(scores, key=_ranking_key) if scores else None),
        "worst": to_result(min(scores, key=_ranking_key) if scores else None),
    }


def refresh_own_stats(user_id: str, game: str) -> None:
    """Called after a daily score is saved. First places are left alone -- only the jobs touch those."""
    try:
        users_table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="SET #s = :s",
            ConditionExpression="attribute_exists(user_id)",
            ExpressionAttributeNames={"#s": f"stats_{game}"},
            ExpressionAttributeValues={":s": _own_stats(game, _daily_scores(user_id, game))},
        )
    except users_table.meta.client.exceptions.ConditionalCheckFailedException:
        pass


# --- first places ----------------------------------------------------------------------

def _puzzle_winners(puzzle_id: str, counts_cache: dict[str, bool]) -> set[str]:
    """Everyone tied for the best score among players who count toward the global ranking."""
    def counts(uid: str) -> bool:
        if uid not in counts_cache:
            counts_cache[uid] = _counts_toward_global_rank(get_user(uid))
        return counts_cache[uid]

    scores = _query_all(
        scores_table,
        KeyConditionExpression="puzzle_id = :pid",
        ExpressionAttributeValues={":pid": puzzle_id},
    )
    eligible = [s for s in scores if counts(s["user_id"])]
    if not eligible:
        return set()
    top = max(_ranking_key(s) for s in eligible)
    return {s["user_id"] for s in eligible if _ranking_key(s) == top}


def award_first_places() -> dict:
    """Adds 1 per winner of the day that just closed; first_places_through_<game> stops double counting."""
    day = _last_closed_day()
    counts_cache: dict[str, bool] = {}
    awarded = 0
    for game in _GAMES:
        for uid in _puzzle_winners(f"{game}_{day}", counts_cache):
            try:
                users_table.update_item(
                    Key={"user_id": uid},
                    UpdateExpression="ADD #fp :one SET #through = :day",
                    ConditionExpression="attribute_exists(user_id) AND (attribute_not_exists(#through) OR #through < :day)",
                    ExpressionAttributeNames={"#fp": f"first_places_{game}", "#through": f"first_places_through_{game}"},
                    ExpressionAttributeValues={":one": 1, ":day": day},
                )
                awarded += 1
            except users_table.meta.client.exceptions.ConditionalCheckFailedException:
                pass
    return {"day": day, "awarded": awarded}


def rebuild_all_stats() -> dict:
    """Recomputes every real user's stored stats from their full history."""
    day = _last_closed_day()
    users = [u for u in list_all_users() if not u.get("is_guest")]

    closed_puzzle_ids: set[str] = set()
    for u in users:
        for game in _GAMES:
            for s in _daily_scores(u["user_id"], game, projection="puzzle_id"):
                if _DAILY_ID.match(s["puzzle_id"]).group(2) <= day:
                    closed_puzzle_ids.add(s["puzzle_id"])

    counts_cache: dict[str, bool] = {}
    winners = {pid: _puzzle_winners(pid, counts_cache) for pid in closed_puzzle_ids}

    for u in users:
        uid = u["user_id"]
        names: dict[str, str] = {}
        values: dict[str, object] = {":day": day}
        clauses: list[str] = []
        for game in _GAMES:
            # Re-read right before writing so a score submitted mid-rebuild isn't overwritten with stale stats.
            scores = _daily_scores(uid, game)
            names.update({f"#s_{game}": f"stats_{game}", f"#fp_{game}": f"first_places_{game}",
                          f"#th_{game}": f"first_places_through_{game}"})
            values[f":s_{game}"] = _own_stats(game, scores)
            values[f":fp_{game}"] = sum(1 for s in scores if uid in winners.get(s["puzzle_id"], ()))
            clauses += [f"#s_{game} = :s_{game}", f"#fp_{game} = :fp_{game}", f"#th_{game} = :day"]
        try:
            users_table.update_item(
                Key={"user_id": uid},
                UpdateExpression="SET " + ", ".join(clauses),
                ConditionExpression="attribute_exists(user_id)",
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=values,
            )
        except users_table.meta.client.exceptions.ConditionalCheckFailedException:
            pass

    return {"day": day, "users": len(users), "closed_puzzles": len(closed_puzzle_ids)}


# --- read path -------------------------------------------------------------------------

def _challenge_record(user_id: str) -> tuple[int, int, int]:
    friendships = _query_all(
        friendships_table,
        KeyConditionExpression="user_id = :uid",
        ExpressionAttributeValues={":uid": user_id},
    )
    wins = draws = losses = 0
    for f in friendships:
        for game in _GAMES:
            wins += int(f.get(f"ch_{game}_w", 0))
            draws += int(f.get(f"ch_{game}_d", 0))
            losses += int(f.get(f"ch_{game}_l", 0))
    return wins, draws, losses


def get_user_stats(user_id: str) -> dict:
    user = get_user(user_id) or {}
    per_game: dict[str, dict] = {}
    for game in _GAMES:
        own = user.get(f"stats_{game}")
        if own is None:  # not yet built for this user (e.g. new since the last rebuild)
            own = _own_stats(game, _daily_scores(user_id, game))
        per_game[_RESPONSE_KEY[game]] = {
            **_plain(own),
            "first_places": int(user.get(f"first_places_{game}", 0)),
            "longest_streak": int(user.get("streaks", {}).get(game, {}).get("longest", 0)),
        }

    wins, draws, losses = _challenge_record(user_id)
    return {
        "user_id": user_id,
        "trophies_unlocked": len(get_unlocked(user_id) & ACHIEVEMENTS.keys()),
        "trophies_total": len(ACHIEVEMENTS),
        "challenge_wins": wins,
        "challenge_draws": draws,
        "challenge_losses": losses,
        "daily_completed": sum(g["completed"] for g in per_game.values()),
        "first_places": sum(g["first_places"] for g in per_game.values()),
        **per_game,
    }
