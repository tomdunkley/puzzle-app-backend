import json
import logging
import os

import google.auth.transport.requests
import google.oauth2.service_account
import requests as http_requests

from app.db import users_table

logger = logging.getLogger(__name__)

_creds = None


def _get_access_token() -> str:
    global _creds
    if _creds is None or not _creds.valid:
        raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "")
        if not raw:
            raise ValueError("FIREBASE_SERVICE_ACCOUNT env var not set")
        info = json.loads(raw)
        _creds = google.oauth2.service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/firebase.messaging"],
        )
    _creds.refresh(google.auth.transport.requests.Request())
    return _creds.token


def save_fcm_token(user_id: str, token: str) -> None:
    users_table.update_item(
        Key={"user_id": user_id},
        UpdateExpression="SET fcm_token = :t",
        ExpressionAttributeValues={":t": token},
    )


def _clear_fcm_token(user_id: str) -> None:
    users_table.update_item(
        Key={"user_id": user_id},
        UpdateExpression="REMOVE fcm_token",
    )


def _get_fcm_token(user_id: str) -> str | None:
    item = users_table.get_item(
        Key={"user_id": user_id},
        ProjectionExpression="fcm_token",
    ).get("Item")
    return item.get("fcm_token") if item else None


def send_push(user_id: str, title: str, body: str) -> None:
    """Send a push notification to the given user. Silently no-ops if the token
    is absent or if the Firebase env vars are not configured."""
    project_id = os.environ.get("FIREBASE_PROJECT_ID", "")
    if not project_id:
        return

    token = _get_fcm_token(user_id)
    if not token:
        return

    try:
        access_token = _get_access_token()
        url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
        resp = http_requests.post(
            url,
            json={"message": {"token": token, "notification": {"title": title, "body": body}}},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=5,
        )
        if resp.status_code in (404, 400) and (
            "UNREGISTERED" in resp.text or "INVALID_ARGUMENT" in resp.text
        ):
            _clear_fcm_token(user_id)
    except Exception:
        logger.exception("push notification failed for user %s", user_id)
