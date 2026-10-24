import logging
import uuid
from datetime import datetime, timedelta, timezone

from botocore.exceptions import ClientError

from app.db import challenges_table, friendships_table
from app.services.boggle import score_words
from app.services.numbers_game import validate_numbers_attempt
from app.services.push_service import send_push
from app.services.user_service import get_user

logger = logging.getLogger(__name__)


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
    return challenges_table.get_item(
        Key={"challenge_id": challenge_id},
        ConsistentRead=True,
    ).get("Item")


def _update_challenge_record(
    challenger_id: str, challengee_id: str, game: str,
    challenger_result: dict, challengee_result: dict,
    challenge_id: str,
) -> None:
    """Atomically increment per-game W/D/L counters and store last challenge id on both friendship items."""
    ck = _challenge_ranking_key(game, challenger_result)
    gk = _challenge_ranking_key(game, challengee_result)
    if ck > gk:
        a_field, b_field = f"ch_{game}_w", f"ch_{game}_l"
    elif ck < gk:
        a_field, b_field = f"ch_{game}_l", f"ch_{game}_w"
    else:
        a_field = b_field = f"ch_{game}_d"
    last_id_attr = f"last_ch_{game}_id"
    for user_id, friend_id, field in [
        (challenger_id, challengee_id, a_field),
        (challengee_id, challenger_id, b_field),
    ]:
        friendships_table.update_item(
            Key={"user_id": user_id, "friend_id": friend_id},
            UpdateExpression=f"ADD {field} :one SET {last_id_attr} = :cid",
            ExpressionAttributeValues={":one": 1, ":cid": challenge_id},
        )


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

    # Re-read (strongly consistent) to see if the other player has also submitted.
    # The conditional update ensures only one of two simultaneous completions fires,
    # and only that request updates the W/D/L counters.
    updated = get_challenge(challenge_id)
    completed_by_this_request = False
    if updated.get("challenger_result") is not None and updated.get("challengee_result") is not None:
        try:
            challenges_table.update_item(
                Key={"challenge_id": challenge_id},
                UpdateExpression="SET #s = :completed REMOVE expires_at_epoch",
                ConditionExpression="#s = :open",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":completed": "completed", ":open": "open"},
            )
            completed_by_this_request = True
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise

    both_played = updated.get("challenger_result") is not None and updated.get("challengee_result") is not None

    if completed_by_this_request:
        try:
            _update_challenge_record(
                challenger_id, challengee_id, challenge["game"],
                updated["challenger_result"], updated["challengee_result"],
                challenge_id,
            )
        except Exception:
            logger.exception("failed to update challenge record for %s", challenge_id)
    new_status = "completed" if both_played else "open"

    # Determine the other player's id and the submitting player's display name for notifications
    other_id = challengee_id if user_id == challenger_id else challenger_id
    me = get_user(user_id)
    my_name = me.get("display_name", "Your opponent") if me else "Your opponent"

    game_display = {"boggle": "Words", "numbers": "Numbers", "routes": "Routes"}.get(game, "puzzle")
    if not both_played:
        send_push(
            other_id,
            "New challenge",
            f"{my_name} has created a {game_display} challenge, time to respond!",
            data={"navigate_to": "challenges", "game": game},
        )
    else:
        send_push(
            other_id,
            "Challenge complete",
            f"See how you did against {my_name} in {game_display}.",
            data={"navigate_to": "challenges", "game": game},
        )

    return {**challenge, result_field: play_result, "status": new_status}


def get_friend_challenge_summary(user_id: str, friend_id: str) -> list[dict]:
    """Per-game summary of challenges between two users."""
    challenges = get_challenges_for_pair(user_id, friend_id)
    friendship_item = friendships_table.get_item(
        Key={"user_id": user_id, "friend_id": friend_id}
    ).get("Item") or {}
    result = []

    for game in ("boggle", "numbers", "routes"):
        game_challenges = [c for c in challenges if c["game"] == game]
        active = next((c for c in game_challenges if c["status"] == "open"), None)
        last_completed = next((c for c in game_challenges if c["status"] == "completed"), None)

        wins = int(friendship_item.get(f"ch_{game}_w", 0))
        losses = int(friendship_item.get(f"ch_{game}_l", 0))
        draws = int(friendship_item.get(f"ch_{game}_d", 0))

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
    """Count and by-friend breakdown of challenges waiting on the user to play.
    Also returns completed_ids for the home-screen badge."""
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

    # Collect completed challenge IDs from FriendshipsTable last_ch_{game}_id fields
    completed_ids: list[str] = []
    friends_resp = friendships_table.query(
        KeyConditionExpression="user_id = :uid",
        ExpressionAttributeValues={":uid": user_id},
        ProjectionExpression="last_ch_boggle_id, last_ch_numbers_id, last_ch_routes_id",
    )
    for item in friends_resp.get("Items", []):
        for attr in ("last_ch_boggle_id", "last_ch_numbers_id", "last_ch_routes_id"):
            val = item.get(attr)
            if val:
                completed_ids.append(val)

    return {"count": sum(by_friend.values()), "by_friend": by_friend, "completed_ids": completed_ids}


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
        "opponent_user_id": other_id,
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
        nums = puzzle_data.get("numbers")
        tgt = puzzle_data.get("target")
        sol = None
        if nums and tgt is not None:
            from app.services.numbers_game import find_best_solution
            sol = find_best_solution(nums, tgt)
        detail.update({
            "numbers": nums,
            "target": tgt,
            "result_value": result.get("result_value"),
            "distance": result.get("distance"),
            "duration_seconds": result.get("duration_seconds"),
            "steps": result.get("steps"),
            "solution_steps": sol,
        })
    elif game == "routes":
        detail.update({
            "duration_seconds": result.get("duration_seconds"),
            "grid_size": puzzle_data.get("grid_size"),
        })

    return detail


def backfill_challenge_records() -> dict:
    """Scan all completed challenges and write correct W/D/L to FriendshipsTable.
    Idempotent — overwrites existing counters. Run once after deploy."""
    items: list[dict] = []
    scan_kwargs: dict = {
        "FilterExpression": "#s = :completed",
        "ExpressionAttributeNames": {"#s": "status"},
        "ExpressionAttributeValues": {":completed": "completed"},
    }
    while True:
        resp = challenges_table.scan(**scan_kwargs)
        items.extend(resp.get("Items", []))
        last = resp.get("LastEvaluatedKey")
        if not last:
            break
        scan_kwargs["ExclusiveStartKey"] = last

    # Accumulate per (user_id, friend_id, game)
    records: dict[tuple, list[int]] = {}
    for c in items:
        cr = c.get("challenger_result")
        cgr = c.get("challengee_result")
        if cr is None or cgr is None:
            continue
        chid = c["challenger_id"]
        cgid = c["challengee_id"]
        game = c["game"]
        ck = _challenge_ranking_key(game, cr)
        gk = _challenge_ranking_key(game, cgr)

        for user_id, friend_id, my_key, their_key in [
            (chid, cgid, ck, gk),
            (cgid, chid, gk, ck),
        ]:
            key = (user_id, friend_id, game)
            if key not in records:
                records[key] = [0, 0, 0]
            if my_key > their_key:
                records[key][0] += 1
            elif my_key < their_key:
                records[key][1] += 1
            else:
                records[key][2] += 1

    # Group by (user_id, friend_id) and write with SET (overwrites)
    from collections import defaultdict
    friendship_updates: dict[tuple, dict] = defaultdict(dict)
    for (user_id, friend_id, game), counts in records.items():
        friendship_updates[(user_id, friend_id)][game] = counts

    updated = 0
    for (user_id, friend_id), games in friendship_updates.items():
        set_parts = []
        values: dict = {}
        for game, (w, l, d) in games.items():
            set_parts += [f"ch_{game}_w = :w_{game}", f"ch_{game}_l = :l_{game}", f"ch_{game}_d = :d_{game}"]
            values[f":w_{game}"] = w
            values[f":l_{game}"] = l
            values[f":d_{game}"] = d
        try:
            friendships_table.update_item(
                Key={"user_id": user_id, "friend_id": friend_id},
                UpdateExpression="SET " + ", ".join(set_parts),
                ExpressionAttributeValues=values,
            )
            updated += 1
        except Exception:
            logger.exception("backfill failed for (%s, %s)", user_id, friend_id)

    return {"challenges_scanned": len(items), "friendship_records_updated": updated}
