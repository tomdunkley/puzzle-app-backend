from fastapi import Header, HTTPException

from app.auth.jwt import InvalidTokenError, decode_token
from app.services.user_service import get_email_verified


def get_current_user_id(authorization: str = Header(default="")) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")

    token = authorization.removeprefix("Bearer ")
    try:
        return decode_token(token, expected_type="access")
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"invalid token: {exc}") from exc


def get_verified_user_id(authorization: str = Header(default="")) -> str:
    user_id = get_current_user_id(authorization)
    if not get_email_verified(user_id):
        raise HTTPException(status_code=403, detail="please verify your email before playing")
    return user_id
