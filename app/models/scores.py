from pydantic import BaseModel

from app.models.puzzles import NumbersStep


class ScoreSubmission(BaseModel):
    puzzle_id: str
    duration_seconds: int
    words: list[str] = []  # boggle
    result_value: int | None = None  # numbers
    steps: list[NumbersStep] = []  # numbers
    all_computed_values: list[int] = []  # numbers: every intermediate result, including abandoned branches


class ScoreSubmissionResult(BaseModel):
    score_id: str
    rank_today: int
    current_streak: int
    score: int | None = None  # boggle
    valid_words: list[str] | None = None  # boggle
    result_value: int | None = None  # numbers
    distance: int | None = None  # numbers
    steps: list[NumbersStep] | None = None  # numbers
    newly_unlocked: list[str] = []  # achievement IDs unlocked by this submission
    daily_best_score: int | None = None  # boggle: best score across all daily puzzles
    daily_best_word_count: int | None = None  # boggle
    daily_best_distance: int | None = None  # numbers: best (lowest) distance across all daily puzzles
    daily_best_result_value: int | None = None  # numbers
    daily_best_duration_seconds: int | None = None  # numbers: time taken for best score (relevant when distance==0)
    is_new_daily_best: bool = False


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: str
    display_name: str
    avatar_id: str | None = None
    avatar_color_id: str | None = None
    avatar_icon_color: str | None = None
    game: str = "boggle"
    score: int | None = None  # boggle
    word_count: int | None = None  # boggle
    result_value: int | None = None  # numbers
    distance: int | None = None  # numbers
    duration_seconds: int | None = None  # numbers


class Leaderboard(BaseModel):
    puzzle_id: str
    entries: list[LeaderboardEntry]


class ScoreDetail(BaseModel):
    puzzle_id: str
    user_id: str
    display_name: str
    avatar_id: str | None = None
    avatar_color_id: str | None = None
    avatar_icon_color: str | None = None
    game: str = "boggle"
    rank_today: int
    # True if the requester hasn't completed this puzzle themselves yet -- the board/
    # numbers/target/words/steps fields below are withheld (null) to avoid spoiling it,
    # while score/result_value/distance stay visible (already shown on the leaderboard).
    locked: bool = False
    # boggle
    score: int | None = None
    valid_words: list[str] | None = None
    board: list[str] | None = None
    # numbers
    numbers: list[int] | None = None
    target: int | None = None
    result_value: int | None = None
    distance: int | None = None
    duration_seconds: int | None = None
    steps: list[NumbersStep] | None = None
