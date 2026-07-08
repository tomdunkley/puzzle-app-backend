from pydantic import BaseModel

from app.models.users import StreakInfo


class WordEntry(BaseModel):
    word: str
    score: int


class AllWordsResponse(BaseModel):
    words: list[WordEntry]


class NumbersStep(BaseModel):
    a: int
    op: str
    b: int
    result: int


class GameSummary(BaseModel):
    game: str
    title: str
    description: str


class Puzzle(BaseModel):
    puzzle_id: str
    game: str
    date: str
    duration_seconds: int
    already_played: bool = False
    streak: StreakInfo | None = None
    # boggle
    board: list[str] | None = None
    your_score: int | None = None
    # numbers
    numbers: list[int] | None = None
    target: int | None = None
    solution: list[NumbersStep] | None = None
    your_result_value: int | None = None
    your_distance: int | None = None
