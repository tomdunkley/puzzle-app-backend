from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependency import get_current_user_id, get_verified_user_id
from app.models.scores import Leaderboard, ScoreDetail, ScoreSubmission, ScoreSubmissionResult
from app.services.achievement_service import check_and_award_on_score
from app.services.friend_service import list_friends
from app.services.numbers_game import InvalidNumbersAttemptError
from app.services.score_service import (
    PuzzleNotFoundError,
    ScoreNotFoundError,
    get_daily_best,
    get_global_leaderboard,
    get_leaderboard,
    get_rank,
    get_score_detail,
    submit_score,
)

router = APIRouter()


@router.post("/scores", response_model=ScoreSubmissionResult, status_code=201)
def post_score(submission: ScoreSubmission, user_id: str = Depends(get_verified_user_id)):
    try:
        item = submit_score(
            puzzle_id=submission.puzzle_id,
            user_id=user_id,
            duration_seconds=submission.duration_seconds,
            words=submission.words,
            result_value=submission.result_value,
            steps=[step.model_dump() for step in submission.steps],
        )
    except PuzzleNotFoundError as exc:
        raise HTTPException(status_code=404, detail="puzzle not found") from exc
    except InvalidNumbersAttemptError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    rank = get_rank(submission.puzzle_id, user_id)
    game = submission.puzzle_id.split("_")[0]
    is_daily = not submission.puzzle_id.startswith(f"{game}_unlimited_")
    newly_unlocked = check_and_award_on_score(
        user_id, game, rank,
        valid_words=item.get("valid_words"),
        validated_steps=item.get("steps"),
        puzzle_id=submission.puzzle_id,
        distance=item.get("distance"),
        current_streak=item.get("current_streak"),
        all_computed_values=submission.all_computed_values or [],
    )
    # Fetch the daily best (across ALL daily puzzles) to show in the results screen.
    # Fall back to the just-submitted item if the GSI hasn't propagated yet (first play).
    daily_best = None
    if is_daily:
        daily_best = get_daily_best(user_id, game) or item
    return ScoreSubmissionResult(
        score_id=item["score_id"],
        rank_today=rank or 0,
        current_streak=item["current_streak"],
        score=item.get("score"),
        valid_words=item.get("valid_words"),
        result_value=item.get("result_value"),
        distance=item.get("distance"),
        steps=item.get("steps"),
        newly_unlocked=newly_unlocked,
        daily_best_score=daily_best.get("score") if daily_best else None,
        daily_best_word_count=len(daily_best.get("valid_words") or []) if daily_best else None,
        daily_best_distance=daily_best.get("distance") if daily_best else None,
        daily_best_result_value=daily_best.get("result_value") if daily_best else None,
        daily_best_duration_seconds=daily_best.get("duration_seconds") if daily_best else None,
    )


@router.get("/leaderboards/{puzzle_id}", response_model=Leaderboard)
def get_puzzle_leaderboard(puzzle_id: str, user_id: str = Depends(get_current_user_id)):
    scope = {friend["user_id"] for friend in list_friends(user_id)} | {user_id}
    entries = get_leaderboard(puzzle_id, user_ids=scope)
    return Leaderboard(puzzle_id=puzzle_id, entries=entries)


@router.get("/leaderboards/{puzzle_id}/global", response_model=Leaderboard)
def get_puzzle_global_leaderboard(puzzle_id: str, _user_id: str = Depends(get_current_user_id)):
    entries = get_global_leaderboard(puzzle_id)
    return Leaderboard(puzzle_id=puzzle_id, entries=entries)


@router.get("/scores/{puzzle_id}/{user_id}", response_model=ScoreDetail)
def get_score(puzzle_id: str, user_id: str, requesting_user_id: str = Depends(get_current_user_id)):
    try:
        detail = get_score_detail(puzzle_id, user_id, requesting_user_id)
    except ScoreNotFoundError as exc:
        raise HTTPException(status_code=404, detail="score not found") from exc
    return ScoreDetail(**detail)
