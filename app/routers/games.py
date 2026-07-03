from fastapi import APIRouter

from app.models.puzzles import GameSummary
from app.services.puzzle_service import list_games

router = APIRouter()


@router.get("/games", response_model=list[GameSummary])
def get_games():
    return list_games()
