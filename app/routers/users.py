from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response

from app.auth.dependency import get_current_user_id
from app.data.achievements import ACHIEVEMENTS
from app.models.users import (
    DailyBestScore,
    PublicUserProfile,
    TodayGameScore,
    UpdateProfileRequest,
    UserProfile,
)
from app.services.achievement_service import get_unlocked
from app.services.friend_service import get_friendship_status
from app.services.score_service import get_daily_best, get_today_score_for_user
from app.services.auth_service import DisplayNameTakenError
from app.services.user_service import (
    InvalidAvatarColorIdError,
    InvalidAvatarIdError,
    ProfanityError,
    delete_account,
    get_user,
    is_developer,
    list_identity_providers,
    update_profile,
)

router = APIRouter()


def _to_profile(user: dict) -> UserProfile:
    providers = list_identity_providers(user["user_id"])
    return UserProfile(
        user_id=user["user_id"],
        display_name=user["display_name"],
        email=user.get("email"),
        avatar_id=user.get("avatar_id"),
        avatar_color_id=user.get("avatar_color_id"),
        avatar_icon_color=user.get("avatar_icon_color"),
        streaks=user.get("streaks", {}),
        email_verified=user.get("email_verified", False),
        has_password="password" in providers,
        has_google="google" in providers,
        visible_on_global_leaderboard=user.get("visible_on_global_leaderboard", True),
        is_developer=is_developer(user["user_id"]),
    )


@router.get("/users/me", response_model=UserProfile)
def get_my_profile(user_id: str = Depends(get_current_user_id)):
    user = get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return _to_profile(user)


@router.patch("/users/me", response_model=UserProfile)
def update_my_profile(body: UpdateProfileRequest, user_id: str = Depends(get_current_user_id)):
    try:
        user = update_profile(
            user_id,
            display_name=body.display_name,
            avatar_id=body.avatar_id,
            avatar_color_id=body.avatar_color_id,
            avatar_icon_color=body.avatar_icon_color,
            visible_on_global_leaderboard=body.visible_on_global_leaderboard,
        )
    except ProfanityError as exc:
        raise HTTPException(status_code=400, detail="display name contains inappropriate language") from exc
    except DisplayNameTakenError as exc:
        raise HTTPException(status_code=409, detail="display name already taken") from exc
    except InvalidAvatarIdError as exc:
        raise HTTPException(status_code=400, detail="invalid avatar id") from exc
    except InvalidAvatarColorIdError as exc:
        raise HTTPException(status_code=400, detail="invalid avatar color id") from exc
    return _to_profile(user)


@router.delete("/users/me", status_code=204)
def delete_my_account(user_id: str = Depends(get_current_user_id)):
    delete_account(user_id)
    return Response(status_code=204)


def _today_score(user_id: str, game: str) -> TodayGameScore | None:
    item = get_today_score_for_user(user_id, game)
    if item is None:
        return None
    today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    puzzle_id = f"{game}_{today_iso}"
    if game == "numbers":
        return TodayGameScore(
            game=game,
            result_value=item.get("result_value"),
            distance=item.get("distance"),
            duration_seconds=item.get("duration_seconds"),
            puzzle_id=puzzle_id,
        )
    return TodayGameScore(
        game=game,
        score=item.get("score"),
        word_count=len(item.get("valid_words") or []),
        puzzle_id=puzzle_id,
    )


def _daily_best_score(user_id: str, game: str) -> DailyBestScore | None:
    item = get_daily_best(user_id, game)
    if item is None:
        return None
    if game == "numbers":
        return DailyBestScore(
            game=game,
            result_value=item.get("result_value"),
            distance=item.get("distance"),
            puzzle_id=item["puzzle_id"],
        )
    return DailyBestScore(
        game=game,
        score=item.get("score"),
        word_count=len(item.get("valid_words") or []),
        puzzle_id=item["puzzle_id"],
    )


@router.get("/users/{user_id}/profile", response_model=PublicUserProfile)
def get_user_profile(user_id: str, requesting_user_id: str = Depends(get_current_user_id)):
    user = get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    unlocked = get_unlocked(user_id)
    return PublicUserProfile(
        user_id=user_id,
        display_name=user["display_name"],
        avatar_id=user.get("avatar_id"),
        avatar_color_id=user.get("avatar_color_id"),
        avatar_icon_color=user.get("avatar_icon_color"),
        friendship_status=get_friendship_status(requesting_user_id, user_id),
        today_boggle=_today_score(user_id, "boggle"),
        today_numbers=_today_score(user_id, "numbers"),
        boggle_daily_best=_daily_best_score(user_id, "boggle"),
        numbers_daily_best=_daily_best_score(user_id, "numbers"),
        trophy_count=len(unlocked),
        total_trophies=len(ACHIEVEMENTS),
    )
