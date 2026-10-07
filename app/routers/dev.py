from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependency import get_current_user_id
from app.services.cryptic_service import NotADeveloperError as CrypticNotDeveloper
from app.services.cryptic_service import (
    delete_clue,
    list_clues,
    submit_clue,
    suggest_words,
    update_clue,
)
from app.services.dev_service import (
    NotADeveloperError,
    grant_streak_freezes_to_eligible,
    reset_achievements,
    reset_todays_progress,
    streak_freeze_progress,
    unlock_all_achievements,
)
from app.services.challenge_service import backfill_challenge_records
from app.services.user_service import admin_update_user, is_developer, list_all_users

router = APIRouter()


class AdminUpdateRequest(BaseModel):
    email_verified: Optional[bool] = None
    is_developer: Optional[bool] = None
    visible_on_global_leaderboard: Optional[bool] = None


class SubmitCrypticClueRequest(BaseModel):
    solution: str
    clue: str


class UpdateCrypticClueRequest(BaseModel):
    solution: str
    clue: str


def _require_developer(user_id: str) -> None:
    if not is_developer(user_id):
        raise HTTPException(status_code=403, detail="developer access required")


@router.post("/dev/cryptic-clues")
def submit_cryptic_clue(
    req: SubmitCrypticClueRequest,
    user_id: str = Depends(get_current_user_id),
):
    try:
        submit_clue(user_id, req.solution, req.clue)
    except CrypticNotDeveloper:
        raise HTTPException(status_code=403, detail="developer access required")
    return {"status": "ok"}


@router.get("/dev/cryptic-clues/suggest-words")
def suggest_cryptic_words(user_id: str = Depends(get_current_user_id)):
    try:
        words, grid_size = suggest_words(user_id)
    except CrypticNotDeveloper:
        raise HTTPException(status_code=403, detail="developer access required")
    return {"words": words, "grid_size": grid_size}


@router.get("/dev/cryptic-clues")
def list_cryptic_clues(user_id: str = Depends(get_current_user_id)):
    try:
        return list_clues(user_id)
    except CrypticNotDeveloper:
        raise HTTPException(status_code=403, detail="developer access required")


@router.patch("/dev/cryptic-clues/{clue_id}")
def update_cryptic_clue(
    clue_id: str,
    req: UpdateCrypticClueRequest,
    user_id: str = Depends(get_current_user_id),
):
    try:
        update_clue(user_id, clue_id, req.solution.strip().upper(), req.clue.strip())
    except CrypticNotDeveloper:
        raise HTTPException(status_code=403, detail="developer access required")
    return {"status": "ok"}


@router.delete("/dev/cryptic-clues/{clue_id}")
def delete_cryptic_clue(clue_id: str, user_id: str = Depends(get_current_user_id)):
    try:
        delete_clue(user_id, clue_id)
    except CrypticNotDeveloper:
        raise HTTPException(status_code=403, detail="developer access required")
    return {"status": "ok"}


@router.post("/dev/reset-progress")
def reset_progress(user_id: str = Depends(get_current_user_id)):
    try:
        reset_todays_progress(user_id)
    except NotADeveloperError as exc:
        raise HTTPException(status_code=403, detail="developer access required") from exc
    return {"status": "ok"}


@router.post("/dev/unlock-all-achievements")
def unlock_achievements(user_id: str = Depends(get_current_user_id)):
    try:
        unlock_all_achievements(user_id)
    except NotADeveloperError as exc:
        raise HTTPException(status_code=403, detail="developer access required") from exc
    return {"status": "ok"}


@router.post("/dev/reset-achievements")
def reset_achievements_endpoint(user_id: str = Depends(get_current_user_id)):
    try:
        reset_achievements(user_id)
    except NotADeveloperError as exc:
        raise HTTPException(status_code=403, detail="developer access required") from exc
    return {"status": "ok"}


@router.post("/dev/grant-streak-freezes")
def grant_freezes(user_id: str = Depends(get_current_user_id)):
    _require_developer(user_id)
    try:
        return grant_streak_freezes_to_eligible(user_id)
    except NotADeveloperError as exc:
        raise HTTPException(status_code=403, detail="developer access required") from exc


@router.get("/dev/users")
def list_users(user_id: str = Depends(get_current_user_id)):
    _require_developer(user_id)
    users = list_all_users()
    safe_fields = [
        "user_id", "display_name", "email", "email_verified", "is_guest",
        "is_developer", "visible_on_global_leaderboard", "created_at",
        "avatar_id", "avatar_color_id", "last_login_at", "last_login_platform",
    ]
    return [
        {**{k: u.get(k) for k in safe_fields}, "freeze_progress": streak_freeze_progress(u)}
        for u in users
    ]


@router.delete("/dev/users/{target_user_id}")
def delete_user(target_user_id: str, user_id: str = Depends(get_current_user_id)):
    _require_developer(user_id)
    if target_user_id == user_id:
        raise HTTPException(status_code=400, detail="cannot delete yourself")
    from app.services.user_service import delete_account
    delete_account(target_user_id)
    return {"status": "ok"}


@router.patch("/dev/users/{target_user_id}")
def update_user(
    target_user_id: str,
    req: AdminUpdateRequest,
    user_id: str = Depends(get_current_user_id),
):
    _require_developer(user_id)
    updated = admin_update_user(
        target_user_id,
        email_verified=req.email_verified,
        is_developer_flag=req.is_developer,
        visible_on_global_leaderboard=req.visible_on_global_leaderboard,
    )
    return updated or {}


@router.post("/dev/backfill-challenge-records")
def backfill_records(user_id: str = Depends(get_current_user_id)):
    _require_developer(user_id)
    return backfill_challenge_records()
