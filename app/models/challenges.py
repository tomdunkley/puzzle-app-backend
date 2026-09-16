from pydantic import BaseModel


class CreateChallengeRequest(BaseModel):
    friend_id: str
    game: str  # "boggle" | "numbers" | "routes"
    seed: str
    puzzle_data: dict  # board for boggle, {numbers, target} for numbers, {grid_size} for routes


class ChallengePlayRequest(BaseModel):
    duration_seconds: int
    words: list[str] = []  # boggle
    result_value: int | None = None  # numbers
    steps: list[dict] = []  # numbers


class LastChallengeResult(BaseModel):
    outcome: str  # "win" | "loss" | "draw"
    my_summary: str
    their_summary: str


class ChallengeSummaryGame(BaseModel):
    game: str
    challenge_id: str | None = None
    # "open" = I haven't played yet, "waiting" = I played, waiting for them, "completed" = both played
    status: str | None = None
    puzzle_data: dict | None = None  # populated when challenge_id is set, so client can generate the game
    record_wins: int = 0
    record_losses: int = 0
    record_draws: int = 0
    last_challenge_id: str | None = None
    last_result: LastChallengeResult | None = None
    expires_at_epoch: int | None = None


class FriendChallengeSummaryResponse(BaseModel):
    games: list[ChallengeSummaryGame]


class ChallengeCreateResponse(BaseModel):
    challenge_id: str


class ChallengePlayResult(BaseModel):
    challenge_id: str
    status: str  # "open" | "completed"
    both_played: bool


class PendingChallengesResponse(BaseModel):
    count: int
    by_friend: dict[str, int]  # friend_id -> count of challenges where I haven't played yet
