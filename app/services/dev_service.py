from app.db import scores_table, users_table
from app.services.puzzle_service import GAMES, today_iso
from app.services.user_service import is_developer, list_all_users

_STREAK_GAMES = ["boggle", "numbers", "routes"]


class NotADeveloperError(Exception):
    pass


def unlock_all_achievements(user_id: str) -> None:
    if not is_developer(user_id):
        raise NotADeveloperError(user_id)
    from app.services.achievement_service import unlock_all_achievements as _unlock
    _unlock(user_id)


def reset_achievements(user_id: str) -> None:
    if not is_developer(user_id):
        raise NotADeveloperError(user_id)
    from app.services.achievement_service import reset_achievements as _reset
    _reset(user_id)


def grant_streak_freezes_to_eligible(user_id: str) -> dict:
    """Grants a streak freeze to every user/game combination where current streak >= 10
    and no freeze is held. Sets next_freeze_at for the new play-count-based logic.
    Idempotent: safe to run multiple times."""
    if not is_developer(user_id):
        raise NotADeveloperError(user_id)

    updated_users = 0
    updated_grants = 0

    for user in list_all_users():
        uid = user.get("user_id")
        streaks = user.get("streaks", {})
        changed = False
        for game in _STREAK_GAMES:
            streak = dict(streaks.get(game, {}))
            current = streak.get("current", 0)
            if current >= 10 and not streak.get("freeze_available"):
                streak["freeze_available"] = True
                streak["next_freeze_at"] = current + 10
                streaks[game] = streak
                changed = True
                updated_grants += 1
        if changed:
            users_table.update_item(
                Key={"user_id": uid},
                UpdateExpression="SET streaks = :s",
                ExpressionAttributeValues={":s": streaks},
            )
            updated_users += 1

    return {"updated_users": updated_users, "updated_grants": updated_grants}


def streak_freeze_progress(user: dict) -> dict:
    """Returns plays-until-next-freeze per game for a user record.
    0 means they hold a freeze already (or will earn one on next play).
    """
    streaks = user.get("streaks", {})
    result = {}
    for game in _STREAK_GAMES:
        streak = streaks.get(game, {})
        current = streak.get("current", 0)
        if streak.get("freeze_available"):
            result[game] = None  # already has one
        elif current == 0:
            result[game] = 10  # needs a streak first
        else:
            next_at = streak.get("next_freeze_at", 10)
            result[game] = max(0, next_at - current)
    return result


def reset_todays_progress(user_id: str) -> None:
    """Deletes the caller's score row for every game's puzzle today, so a developer
    account can immediately replay them instead of waiting for tomorrow's puzzle.
    Gated to developer_emails -- everyone else gets NotADeveloperError.
    """
    if not is_developer(user_id):
        raise NotADeveloperError(user_id)

    date_iso = today_iso()
    for game in GAMES:
        puzzle_id = f"{game['game']}_{date_iso}"
        scores_table.delete_item(Key={"puzzle_id": puzzle_id, "user_id": user_id})
