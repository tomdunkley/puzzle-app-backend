from fastapi import APIRouter, Depends

from app.auth.dependency import get_current_user_id
from app.services.achievement_service import get_achievement_summary

router = APIRouter()


@router.get("/users/me/achievements")
def get_my_achievements(user_id: str = Depends(get_current_user_id)):
    return get_achievement_summary(user_id)
