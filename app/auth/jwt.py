from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings

ALGORITHM = "HS256"


class InvalidTokenError(Exception):
    pass


def _encode(user_id: str, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def create_access_token(user_id: str) -> str:
    return _encode(user_id, "access", timedelta(minutes=settings.jwt_access_token_minutes))


def create_refresh_token(user_id: str) -> str:
    return _encode(user_id, "refresh", timedelta(days=settings.jwt_refresh_token_days))


def decode_token(token: str, expected_type: str) -> str:
    """Returns the user_id (sub claim) if the token is valid and of the expected type."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    if payload.get("type") != expected_type:
        raise InvalidTokenError(f"expected a {expected_type} token")

    return payload["sub"]
