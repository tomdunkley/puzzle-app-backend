from app.db import scores_table
from app.services.puzzle_service import GAMES, today_iso
from app.services.user_service import is_developer


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
