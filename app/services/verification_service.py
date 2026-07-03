import random
import time

from app.db import verification_codes_table
from app.services.email_service import send_email

CODE_TTL_SECONDS = 15 * 60
MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60


class VerificationCodeExpiredError(Exception):
    pass


class VerificationCodeIncorrectError(Exception):
    pass


class TooManyAttemptsError(Exception):
    pass


class ResendCooldownError(Exception):
    pass


def _generate_code() -> str:
    return f"{random.randint(0, 999999):06d}"


def send_verification_code(user_id: str, email: str) -> None:
    now = int(time.time())
    code = _generate_code()
    verification_codes_table.put_item(
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
        subject="Your td Puzzles verification code",
        body=f"Your verification code is {code}. It expires in 15 minutes.",
    )


def resend_verification_code(user_id: str, email: str) -> None:
    now = int(time.time())
    existing = verification_codes_table.get_item(Key={"user_id": user_id}).get("Item")
    if existing is not None and now - int(existing["last_sent_epoch"]) < RESEND_COOLDOWN_SECONDS:
        raise ResendCooldownError()
    send_verification_code(user_id, email)


def verify_code(user_id: str, submitted_code: str) -> None:
    record = verification_codes_table.get_item(Key={"user_id": user_id}).get("Item")
    if record is None or int(record["expires_at_epoch"]) < int(time.time()):
        raise VerificationCodeExpiredError()

    if int(record["attempts"]) >= MAX_ATTEMPTS:
        raise TooManyAttemptsError()

    if record["code"] != submitted_code:
        verification_codes_table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="SET attempts = attempts + :one",
            ExpressionAttributeValues={":one": 1},
        )
        raise VerificationCodeIncorrectError()

    verification_codes_table.delete_item(Key={"user_id": user_id})
