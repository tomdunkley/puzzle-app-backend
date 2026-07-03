import requests

from app.config import settings


def send_email(to_address: str, subject: str, body: str) -> None:
    """Sends via the Resend API rather than AWS SES or Gmail SMTP -- see TODO.md for why."""
    response = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        json={
            "from": settings.resend_sender_email,
            "to": [to_address],
            "subject": subject,
            "text": body,
        },
        timeout=10,
    )
    response.raise_for_status()
