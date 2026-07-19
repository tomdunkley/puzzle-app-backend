from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependency import get_current_user_id
from app.services.dev_service import NotADeveloperError, reset_achievements, reset_todays_progress, unlock_all_achievements
from app.services.user_service import admin_update_user, is_developer, list_all_users

router = APIRouter()


class AdminUpdateRequest(BaseModel):
    email_verified: Optional[bool] = None
    is_developer: Optional[bool] = None
    visible_on_global_leaderboard: Optional[bool] = None


def _require_developer(user_id: str) -> None:
    if not is_developer(user_id):
        raise HTTPException(status_code=403, detail="developer access required")


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


@router.get("/dev/users")
def list_users(user_id: str = Depends(get_current_user_id)):
    _require_developer(user_id)
    users = list_all_users()
    safe_fields = [
        "user_id", "display_name", "email", "email_verified", "is_guest",
        "is_developer", "visible_on_global_leaderboard", "created_at",
        "avatar_id", "avatar_color_id",
    ]
    return [
        {k: u.get(k) for k in safe_fields}
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
