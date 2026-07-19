from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependency import get_current_user_id, get_verified_user_id
from app.models.puzzles import AllWordsResponse, Puzzle, WordEntry
from app.services.puzzle_service import get_or_create_today_puzzle, get_puzzle, get_puzzle_all_words
from app.services.score_service import get_user_score_item
from app.services.user_service import get_user

router = APIRouter()


def _to_response(puzzle: dict, user_id: str) -> Puzzle:
    score_item = get_user_score_item(puzzle["puzzle_id"], user_id)
    user = get_user(user_id)
    streak = (user or {}).get("streaks", {}).get(puzzle["game"])

    if puzzle["game"] == "numbers":
        return Puzzle(
            puzzle_id=puzzle["puzzle_id"],
            game=puzzle["game"],
            date=puzzle["date"],
            duration_seconds=puzzle["duration_seconds"],
            already_played=score_item is not None,
            streak=streak,
            numbers=puzzle["numbers"],
            target=puzzle["target"],
            solution=puzzle["solution"],
            your_result_value=score_item.get("result_value") if score_item else None,
            your_distance=score_item.get("distance") if score_item else None,
        )

    return Puzzle(
        puzzle_id=puzzle["puzzle_id"],
        game=puzzle["game"],
        date=puzzle["date"],
        duration_seconds=puzzle["duration_seconds"],
        already_played=score_item is not None,
        streak=streak,
        board=puzzle["board"],
        your_score=score_item.get("score") if score_item else None,
    )


# Browsing the games list (router/games.py) stays public so Home can show what's
# available, but actually fetching a board -- i.e. playing -- requires sign-in.
@router.get("/puzzles/today", response_model=Puzzle)
def get_today_puzzle(game: str, user_id: str = Depends(get_verified_user_id)):
    puzzle = get_or_create_today_puzzle(game)
    return _to_response(puzzle, user_id)


@router.get("/puzzles/{puzzle_id}/all-words", response_model=AllWordsResponse)
def get_all_words_for_puzzle(puzzle_id: str, _user_id: str = Depends(get_current_user_id)):
    words = get_puzzle_all_words(puzzle_id)
    if words is None:
        raise HTTPException(status_code=404, detail="puzzle not found or not a boggle puzzle")
    return AllWordsResponse(words=[WordEntry(**w) for w in words])


@router.get("/puzzles/{puzzle_id}", response_model=Puzzle)
def get_puzzle_by_id(puzzle_id: str, user_id: str = Depends(get_current_user_id)):
    puzzle = get_puzzle(puzzle_id)
    if puzzle is None:
        raise HTTPException(status_code=404, detail="puzzle not found")
    return _to_response(puzzle, user_id)
