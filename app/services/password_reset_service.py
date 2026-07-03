import random
import time

from app.auth.password import hash_password
from app.db import password_reset_codes_table
from app.services.email_service import send_email
from app.services.user_service import find_identity, update_password_hash

CODE_TTL_SECONDS = 15 * 60
MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60


class PasswordResetCodeExpiredError(Exception):
    pass


class PasswordResetCodeIncorrectError(Exception):
    pass


class TooManyAttemptsError(Exception):
    pass


class ResendCooldownError(Exception):
    pass


def _generate_code() -> str:
    return f"{random.randint(0, 999999):06d}"


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _send_code(user_id: str, email: str) -> None:
    now = int(time.time())
    code = _generate_code()
    password_reset_codes_table.put_item(
        Item={
            "user_id": user_id,
            "code": code,
            "expires_at_epoch": now + CODE_TTL_SECONDS,
            "attempts": 0,
            "last_sent_epoch": now,
        }
    )
    send_email(
        to_address=email,
        subject="Reset your td Puzzles password",
        body=f"Your password reset code is {code}. It expires in 15 minutes.",
    )


def request_password_reset(email: str) -> None:
    """No-ops silently if the email isn't a registered password account -- the caller
    always reports success either way, so this never reveals which emails exist.
    """
    normalized = _normalize_email(email)
    identity = find_identity("password", normalized)
    if identity is not None:
        _send_code(identity["user_id"], normalized)


def resend_password_reset(email: str) -> None:
    normalized = _normalize_email(email)
    identity = find_identity("password", normalized)
    if identity is None:
        return
    user_id = identity["user_id"]
    now = int(time.time())
    existing = password_reset_codes_table.get_item(Key={"user_id": user_id}).get("Item")
    if existing is not None and now - int(existing["last_sent_epoch"]) < RESEND_COOLDOWN_SECONDS:
        raise ResendCooldownError()
    _send_code(user_id, normalized)


def confirm_password_reset(email: str, code: str, new_password: str) -> None:
    normalized = _normalize_email(email)
    identity = find_identity("password", normalized)
    if identity is None:
        # Same error as a wrong code -- never confirms whether the email exists.
        raise PasswordResetCodeIncorrectError()

    user_id = identity["user_id"]
    record = password_reset_codes_table.get_item(Key={"user_id": user_id}).get("Item")
    if record is None or int(record["expires_at_epoch"]) < int(time.time()):
        raise PasswordResetCodeExpiredError()
    if int(record["attempts"]) >= MAX_ATTEMPTS:
        raise TooManyAttemptsError()
    if record["code"] != code:
        password_reset_codes_table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="SET attempts = attempts + :one",
            ExpressionAttributeValues={":one": 1},
        )
        raise PasswordResetCodeIncorrectError()

    password_reset_codes_table.delete_item(Key={"user_id": user_id})
    update_password_hash(normalized, hash_password(new_password))
