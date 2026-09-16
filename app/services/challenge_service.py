import uuid
from datetime import datetime, timedelta, timezone

from botocore.exceptions import ClientError

from app.db import challenges_table
from app.services.boggle import score_words
from app.services.numbers_game import validate_numbers_attempt
from app.services.user_service import get_user


class ChallengeNotFoundError(Exception):
    pass


class ChallengeAlreadyExistsError(Exception):
    pass


class ChallengeNotOpenError(Exception):
    pass


class AlreadyPlayedError(Exception):
    pass


class NotAParticipantError(Exception):
    pass


class PlayNotFoundError(Exception):
    pass


def _make_pair_key(a: str, b: str) -> str:
    return f"{min(a, b)}#{max(a, b)}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _format_result_summary(game: str, result: dict) -> str:
    if game == "boggle":
        return f"{result.get('score', 0)} pts"
    elif game == "numbers":
        distance = result.get("distance", 0)
        secs = result.get("duration_seconds", 0)
        return f"Exact ({secs}s)" if distance == 0 else f"{distance} away"
    else:
        secs = result.get("duration_seconds", 0)
        m, s = divmod(secs, 60)
        return f"{m}m {s}s" if m > 0 else f"{s}s"


def _challenge_ranking_key(game: str, result: dict) -> tuple:
    if game == "numbers":
        distance = result.get("distance", 10**9)
        duration = result.get("duration_seconds", 10**9)
        # Time only breaks ties when both got exact (distance == 0); same non-zero distance = draw
        return (0, -duration) if distance == 0 else (-distance, 0)
    if game == "routes":
        duration = result.get("duration_seconds", 10**9)
        return (-duration, 0)
    return (result.get("score", 0), len(result.get("valid_words", [])))


def create_challenge(challenger_id: str, friend_id: str, game: str, seed: str, puzzle_data: dict) -> dict:
    """Create a new challenge. Raises ChallengeAlreadyExistsError if an open challenge exists."""
    pair_key = _make_pair_key(challenger_id, friend_id)

    existing = challenges_table.query(
        IndexName="byPair",
        KeyConditionExpression="pair_key = :pk",
        FilterExpression="#s = :open AND game = :game",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":pk": pair_key, ":open": "open", ":game": game},
    )
    if existing.get("Items"):
        raise ChallengeAlreadyExistsError(f"Open {game} challenge already exists for this pair")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=7)
    challenge_id = f"ch_{uuid.uuid4().hex[:12]}"

    item = {
        "challenge_id": challenge_id,
        "pair_key": pair_key,
        "game": game,
        "challenger_id": challenger_id,
        "challengee_id": friend_id,
        "status": "open",
        "created_at": now.isoformat(),
        "expires_at_epoch": int(expires_at.timestamp()),
        "seed": seed,
        "puzzle_data": puzzle_data,
    }
    challenges_table.put_item(Item=item)
    return item


def get_challenge(challenge_id: str) -> dict | None:
    return challenges_table.get_item(Key={"challenge_id": challenge_id}).get("Item")


def get_challenges_for_pair(user_id: str, friend_id: str) -> list[dict]:
    """All challenges between two users, newest first."""
    pair_key = _make_pair_key(user_id, friend_id)
    response = challenges_table.query(
        IndexName="byPair",
        KeyConditionExpression="pair_key = :pk",
        ScanIndexForward=False,
        ExpressionAttributeValues={":pk": pair_key},
    )
    return response.get("Items", [])


def submit_challenge_play(
    challenge_id: str,
    user_id: str,
    duration_seconds: int,
    words: list[str] | None = None,
    result_value: int | None = None,
    steps: list[dict] | None = None,
) -> dict:
    """Submit a play result for a challenge. Returns the updated challenge."""
    challenge = get_challenge(challenge_id)
    if challenge is None:
        raise ChallengeNotFoundError(challenge_id)
    if challenge["status"] != "open":
        raise ChallengeNotOpenError(challenge_id)

    challenger_id = challenge["challenger_id"]
    challengee_id = challenge["challengee_id"]

    if user_id == challenger_id:
        result_field = "challenger_result"
        other_result_field = "challengee_result"
    elif user_id == challengee_id:
        result_field = "challengee_result"
        other_result_field = "challenger_result"
    else:
        raise NotAParticipantError(user_id)

    game = challenge["game"]
    puzzle_data = challenge["puzzle_data"]
    play_result = {"submitted_at": _now_iso(), "duration_seconds": duration_seconds}

    if game == "boggle":
        board = puzzle_data.get("board", [])
        valid_words, score = score_words(board, words or [])
        play_result["score"] = score
        play_result["valid_words"] = valid_words
    elif game == "numbers":
        validated = validate_numbers_attempt(
            puzzle_data.get("numbers", []),
            puzzle_data.get("target", 0),
            result_value,
            steps or [],
        )
        play_result["result_value"] = validated["result_value"]
        play_result["distance"] = validated["distance"]
        play_result["steps"] = validated["steps"]
    # routes: just duration, no additional validation needed

    # Write result atomically — condition prevents double-submission even under concurrent requests
    try:
        challenges_table.update_item(
            Key={"challenge_id": challenge_id},
            UpdateExpression="SET #rf = :result",
            ConditionExpression="attribute_not_exists(#rf)",
            ExpressionAttributeNames={"#rf": result_field},
            ExpressionAttributeValues={":result": play_result},
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise AlreadyPlayedError(user_id)
        raise

    # Re-read to see if the other player has also submitted; if so, mark completed.
    # Using a conditional update here means two simultaneous second-submissions both
    # attempt the transition but only one wins — either way the final state is correct.
    updated = get_challenge(challenge_id)
    if updated.get("challenger_result") is not None and updated.get("challengee_result") is not None:
        try:
            challenges_table.update_item(
                Key={"challenge_id": challenge_id},
                UpdateExpression="SET #s = :completed",
                ConditionExpression="#s = :open",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":completed": "completed", ":open": "open"},
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise

    new_status = "completed" if (updated.get("challenger_result") and updated.get("challengee_result")) else "open"
    return {**challenge, result_field: play_result, "status": new_status}


def get_friend_challenge_summary(user_id: str, friend_id: str) -> list[dict]:
    """Per-game summary of challenges between two users."""
    challenges = get_challenges_for_pair(user_id, friend_id)
    result = []

    for game in ("boggle", "numbers", "routes"):
        game_challenges = [c for c in challenges if c["game"] == game]
        active = next((c for c in game_challenges if c["status"] == "open"), None)
        last_completed = next((c for c in game_challenges if c["status"] == "completed"), None)

        wins, losses, draws = 0, 0, 0
        for c in game_challenges:
            if c["status"] != "completed":
                continue
            cr = c.get("challenger_result")
            cgr = c.get("challengee_result")
            if cr is None or cgr is None:
                continue
            my_result = cr if c["challenger_id"] == user_id else cgr
            their_result = cgr if c["challenger_id"] == user_id else cr
            my_key = _challenge_ranking_key(game, my_result)
            their_key = _challenge_ranking_key(game, their_result)
            if my_key > their_key:
                wins += 1
            elif my_key < their_key:
                losses += 1
            else:
                draws += 1

        active_status = None
        if active is not None:
            if active["challenger_id"] == user_id:
                active_status = "waiting" if active.get("challenger_result") is not None else "open"
            else:
                active_status = "waiting" if active.get("challengee_result") is not None else "open"

        pd = active.get("puzzle_data") if active else None
        # Inject seed into puzzle_data for all games so clients can display it in the title.
        if active and pd is not None:
            pd = {**pd, "seed": active.get("seed", "")}

        last_result = None
        if last_completed is not None:
            cr = last_completed.get("challenger_result")
            cgr = last_completed.get("challengee_result")
            if cr is not None and cgr is not None:
                my_r = cr if last_completed["challenger_id"] == user_id else cgr
                their_r = cgr if last_completed["challenger_id"] == user_id else cr
                my_key = _challenge_ranking_key(game, my_r)
                their_key = _challenge_ranking_key(game, their_r)
                outcome = "win" if my_key > their_key else ("loss" if my_key < their_key else "draw")
                last_result = {
                    "outcome": outcome,
                    "my_summary": _format_result_summary(game, my_r),
                    "their_summary": _format_result_summary(game, their_r),
                }

        result.append({
            "game": game,
            "challenge_id": active["challenge_id"] if active else None,
            "status": active_status,
            "puzzle_data": pd,
            "record_wins": wins,
            "record_losses": losses,
            "record_draws": draws,
            "last_challenge_id": last_completed["challenge_id"] if last_completed else None,
            "last_result": last_result,
            "expires_at_epoch": active.get("expires_at_epoch") if active else None,
        })

    return result


def get_pending_challenges(user_id: str) -> dict:
    """Count and by-friend breakdown of challenges waiting on the user to play (challengee only)."""
    challengee_resp = challenges_table.query(
        IndexName="byChallengee",
        KeyConditionExpression="challengee_id = :uid",
        FilterExpression="#s = :open",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":uid": user_id, ":open": "open"},
    )

    by_friend: dict[str, int] = {}
    for item in challengee_resp.get("Items", []):
        if item.get("challengee_result") is None:
            fid = item["challenger_id"]
            by_friend[fid] = by_friend.get(fid, 0) + 1

    return {"count": sum(by_friend.values()), "by_friend": by_friend}


def get_challenge_result(challenge_id: str, target_user_id: str, requesting_user_id: str) -> dict:
    """Return ScoreDetail-compatible dict for a user's challenge result."""
    challenge = get_challenge(challenge_id)
    if challenge is None:
        raise ChallengeNotFoundError(challenge_id)

    participants = {challenge["challenger_id"], challenge["challengee_id"]}
    if requesting_user_id not in participants:
        raise NotAParticipantError(requesting_user_id)
    if target_user_id not in participants:
        raise NotAParticipantError(target_user_id)

    result = (
        challenge.get("challenger_result")
        if target_user_id == challenge["challenger_id"]
        else challenge.get("challengee_result")
    )
    if result is None:
        raise PlayNotFoundError(target_user_id)

    game = challenge["game"]
    puzzle_data = challenge["puzzle_data"]
    user = get_user(target_user_id)
    other_id = challenge["challengee_id"] if target_user_id == challenge["challenger_id"] else challenge["challenger_id"]
    other_user = get_user(other_id)

    detail = {
        "puzzle_id": challenge_id,
        "user_id": target_user_id,
        "display_name": user["display_name"] if user else "Unknown",
        "avatar_id": user.get("avatar_id") if user else None,
        "avatar_color_id": user.get("avatar_color_id") if user else None,
        "avatar_icon_color": user.get("avatar_icon_color") if user else None,
        "game": game,
        "rank_today": 0,
        "rank_today_is_tied": False,
        "locked": False,
        "seed": challenge.get("seed"),
        "opponent_name": other_user["display_name"] if other_user else None,
        "opponent_avatar_id": other_user.get("avatar_id") if other_user else None,
        "opponent_avatar_color_id": other_user.get("avatar_color_id") if other_user else None,
        "opponent_avatar_icon_color": other_user.get("avatar_icon_color") if other_user else None,
    }

    if game == "boggle":
        detail.update({
            "score": result.get("score"),
            "valid_words": result.get("valid_words"),
            "board": puzzle_data.get("board"),
        })
    elif game == "numbers":
        detail.update({
            "numbers": puzzle_data.get("numbers"),
            "target": puzzle_data.get("target"),
            "result_value": result.get("result_value"),
            "distance": result.get("distance"),
            "duration_seconds": result.get("duration_seconds"),
            "steps": result.get("steps"),
        })
    elif game == "routes":
        detail.update({"duration_seconds": result.get("duration_seconds")})

    return detail
