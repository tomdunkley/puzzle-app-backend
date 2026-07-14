from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependency import get_current_user_id
from app.services.achievement_service import (
    AchievementNotClaimableError,
    claim_achievement,
    get_achievement_summary,
)

router = APIRouter()


@router.get("/users/me/achievements")
def get_my_achievements(user_id: str = Depends(get_current_user_id)):
    return get_achievement_summary(user_id)


class ClaimAchievementRequest(BaseModel):
    achievement_id: str


@router.post("/users/me/achievements/claim")
def claim_my_achievement(
    body: ClaimAchievementRequest,
    user_id: str = Depends(get_current_user_id),
):
    try:
        newly = claim_achievement(user_id, body.achievement_id)
        return {"newly_unlocked": newly}
    except AchievementNotClaimableError:
        raise HTTPException(status_code=400, detail="achievement not claimable")
