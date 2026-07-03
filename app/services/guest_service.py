from app.auth.jwt import InvalidTokenError, decode_token
from app.db import scores_table
from app.services.puzzle_service import get_or_create_today_puzzle, list_games
from app.services.user_service import delete_guest_user, get_user, update_streak_for_play


def claim_guest_score_for_today(new_user_id: str, guest_access_token: str | None) -> None:
    """Called right after a successful register/login/Google sign-in. If the caller
    was just playing as a guest, moves *today's* guest score (for each game) onto
    the now-signed-in account -- but only for a puzzle the new account hasn't already
    played today. If the account already has a score for that puzzle (e.g. they
    already played today on another device), the existing score wins and the
    guest's is silently dropped -- the same "keep the best" rule submit_score
    already applies to resubmissions. The guest account is deleted either way.
    """
    if not guest_access_token:
        return
    try:
        guest_user_id = decode_token(guest_access_token, expected_type="access")
    except InvalidTokenError:
        return
    if guest_user_id == new_user_id:
        return

    guest = get_user(guest_user_id)
    if guest is None or not guest.get("is_guest"):
        return

    for game_info in list_games():
        puzzle = get_or_create_today_puzzle(game_info["game"])
        guest_key = {"puzzle_id": puzzle["puzzle_id"], "user_id": guest_user_id}
        guest_score = scores_table.get_item(Key=guest_key).get("Item")
        if guest_score is None:
            continue

        new_key = {"puzzle_id": puzzle["puzzle_id"], "user_id": new_user_id}
        if scores_table.get_item(Key=new_key).get("Item") is None:
            scores_table.put_item(Item={**guest_score, "user_id": new_user_id})
            update_streak_for_play(new_user_id, puzzle["game"], puzzle["date"])
        scores_table.delete_item(Key=guest_key)

    delete_guest_user(guest_user_id)
