from pydantic import BaseModel, field_validator

from app.models.auth import validate_display_name_no_at


class StreakInfo(BaseModel):
    current: int
    longest: int
    last_played_date: str | None = None


class UserProfile(BaseModel):
    user_id: str
    display_name: str
    email: str | None = None
    avatar_id: str | None = None
    avatar_color_id: str | None = None
    avatar_icon_color: str | None = None
    streaks: dict[str, StreakInfo] = {}
    email_verified: bool = False
    has_password: bool = False
    has_google: bool = False
    visible_on_global_leaderboard: bool = True
    is_developer: bool = False


class UpdateProfileRequest(BaseModel):
    display_name: str | None = None
    avatar_id: str | None = None
    avatar_color_id: str | None = None
    avatar_icon_color: str | None = None
    visible_on_global_leaderboard: bool | None = None

    _validate_display_name = field_validator("display_name")(
        lambda v: v if v is None else validate_display_name_no_at(v)
    )


class TodayGameScore(BaseModel):
    game: str
    score: int | None = None
    word_count: int | None = None
    result_value: int | None = None
    distance: int | None = None


class DailyBestScore(BaseModel):
    game: str
    score: int | None = None
    word_count: int | None = None
    result_value: int | None = None
    distance: int | None = None
    puzzle_id: str


class PublicUserProfile(BaseModel):
    user_id: str
    display_name: str
    avatar_id: str | None = None
    avatar_color_id: str | None = None
    avatar_icon_color: str | None = None
    friendship_status: str  # "none" | "friends" | "request_sent" | "request_received"
    today_boggle: TodayGameScore | None = None
    today_numbers: TodayGameScore | None = None
    boggle_daily_best: DailyBestScore | None = None
    numbers_daily_best: DailyBestScore | None = None
    trophy_count: int = 0
    total_trophies: int = 0
