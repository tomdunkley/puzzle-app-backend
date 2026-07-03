import os


class Settings:
    aws_region: str = os.environ.get("AWS_REGION", "us-east-1")

    users_table: str = os.environ.get("USERS_TABLE", "td-puzzles-users")
    identities_table: str = os.environ.get("IDENTITIES_TABLE", "td-puzzles-identities")
    puzzles_table: str = os.environ.get("PUZZLES_TABLE", "td-puzzles-puzzles")
    scores_table: str = os.environ.get("SCORES_TABLE", "td-puzzles-scores")
    friendships_table: str = os.environ.get("FRIENDSHIPS_TABLE", "td-puzzles-friendships")
    friend_requests_table: str = os.environ.get("FRIEND_REQUESTS_TABLE", "td-puzzles-friend-requests")
    verification_codes_table: str = os.environ.get("VERIFICATION_CODES_TABLE", "td-puzzles-verification-codes")
    password_reset_codes_table: str = os.environ.get("PASSWORD_RESET_CODES_TABLE", "td-puzzles-password-reset-codes")
    achievements_table: str = os.environ.get("ACHIEVEMENTS_TABLE", "td-puzzles-achievements")

    jwt_secret: str = os.environ.get("JWT_SECRET", "dev-secret-change-me")
    jwt_access_token_minutes: int = int(os.environ.get("JWT_ACCESS_TOKEN_MINUTES", "60"))
    jwt_refresh_token_days: int = int(os.environ.get("JWT_REFRESH_TOKEN_DAYS", "30"))

    google_oauth_client_id: str = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")

    # Verification emails are sent via the Resend API. Tried AWS SES first (blocked on
    # sandbox/production-access approval) and Gmail SMTP second (Google blocks SMTP AUTH
    # from AWS Lambda's IP ranges even with a valid app password) -- see TODO.md.
    resend_api_key: str = os.environ.get("RESEND_API_KEY", "")
    resend_sender_email: str = os.environ.get("RESEND_SENDER_EMAIL", "")

    # Enables POST /v1/auth/dev-login. Must be unset/false in any real deployment.
    allow_dev_login: bool = os.environ.get("ALLOW_DEV_LOGIN", "false").lower() == "true"

    # Accounts (by email) that get developer-only affordances, e.g. resetting their
    # own daily puzzle progress to replay it. A plain allowlist, not a DB flag, so
    # granting/revoking it is just an env var change with no data migration.
    developer_emails: frozenset[str] = frozenset(
        email.strip().lower()
        for email in os.environ.get("DEVELOPER_EMAILS", "dunkertheepic13@gmail.com").split(",")
        if email.strip()
    )


settings = Settings()
