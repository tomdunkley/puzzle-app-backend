from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependency import get_current_user_id
from app.services.dev_service import NotADeveloperError, reset_achievements, reset_todays_progress, unlock_all_achievements

router = APIRouter()


@router.post("/dev/reset-progress")
def reset_progress(user_id: str = Depends(get_current_user_id)):
    # No status_code=204 -- Retrofit/OkHttp always reports a null body for a bare 204,
    # which crashes the Android client's non-nullable Unit-returning suspend call.
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
