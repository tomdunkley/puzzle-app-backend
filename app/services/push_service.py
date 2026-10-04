import json
import logging
import os

import boto3
import google.auth.transport.requests
import google.oauth2.service_account
import requests as http_requests

from app.db import users_table

logger = logging.getLogger(__name__)

_creds = None
_service_account_info = None


def _load_service_account_info() -> dict | None:
    global _service_account_info
    if _service_account_info is not None:
        return _service_account_info
    try:
        ssm = boto3.client("ssm", region_name="us-east-1")
        resp = ssm.get_parameter(
            Name="/td-puzzles/firebase-service-account",
            WithDecryption=True,
        )
        _service_account_info = json.loads(resp["Parameter"]["Value"])
        return _service_account_info
    except Exception:
        logger.exception("failed to load Firebase service account from SSM")
        return None


def _get_access_token() -> str:
    global _creds
    if _creds is None or not _creds.valid:
        info = _load_service_account_info()
        if not info:
            raise ValueError("Firebase service account unavailable")
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
