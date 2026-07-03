from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.config import settings


class GoogleTokenError(Exception):
    pass


def verify_google_id_token(token: str) -> dict:
    """Verifies a Google ID token and returns its claims (sub, email, name, picture)."""
    if not settings.google_oauth_client_id:
        raise GoogleTokenError("server has no GOOGLE_OAUTH_CLIENT_ID configured")

    try:
        claims = id_token.verify_oauth2_token(
            token, google_requests.Request(), audience=settings.google_oauth_client_id
        )
    except ValueError as exc:
        raise GoogleTokenError(str(exc)) from exc

    return claims
