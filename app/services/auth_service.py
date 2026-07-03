from app.auth.google import verify_google_id_token
from app.auth.jwt import create_access_token, create_refresh_token
from app.auth.password import hash_password, verify_password
from app.services.guest_service import claim_guest_score_for_today
from app.services.user_service import (
    DisplayNameTakenError,
    create_google_identity,
    create_password_identity,
    create_user_with_identity,
    find_identity,
    find_user_by_display_name_lower,
    get_or_create_user_for_identity,
    get_user,
    mark_email_verified,
    update_password_hash,
)
from app.services.verification_service import send_verification_code


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class NoEmailOnFileError(Exception):
    pass


class PasswordAlreadySetError(Exception):
    pass


class NoPasswordSetError(Exception):
    pass


class GoogleAccountEmailMismatchError(Exception):
    pass


class GoogleAccountAlreadyLinkedError(Exception):
    pass


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def sign_in_with_google(google_id_token: str, guest_access_token: str | None = None) -> tuple[dict, str, str]:
    claims = verify_google_id_token(google_id_token)
    user = get_or_create_user_for_identity(
        provider="google",
        provider_subject=claims["sub"],
        display_name=claims.get("name", "Player"),
        email=claims.get("email"),
        email_verified=True,
    )
    # Unconditional, not just at creation -- a Google identity created before email
    # verification existed (or before the one-off backfill ran) would otherwise stay
    # unverified forever, since get_or_create_user_for_identity only sets this on the
    # very first sign-in. Google has already verified this email; trust it every time.
    if not user.get("email_verified", False):
        mark_email_verified(user["user_id"])
        user["email_verified"] = True
    claim_guest_score_for_today(user["user_id"], guest_access_token)
    return user, create_access_token(user["user_id"]), create_refresh_token(user["user_id"])


def register_with_password(
    email: str, password: str, display_name: str, guest_access_token: str | None = None
) -> tuple[dict, str, str]:
    normalized_email = _normalize_email(email)
    if find_identity("password", normalized_email) is not None:
        raise EmailAlreadyRegisteredError(normalized_email)
    if find_user_by_display_name_lower(display_name.strip().lower()) is not None:
        raise DisplayNameTakenError(display_name)

    user = create_user_with_identity(
        provider="password",
        provider_subject=normalized_email,
        display_name=display_name,
        password_hash=hash_password(password),
        email=normalized_email,
        email_verified=False,
    )
    send_verification_code(user["user_id"], normalized_email)
    claim_guest_score_for_today(user["user_id"], guest_access_token)
    return user, create_access_token(user["user_id"]), create_refresh_token(user["user_id"])


def login_with_password(
    email: str, password: str, guest_access_token: str | None = None
) -> tuple[dict, str, str]:
    identity = find_identity("password", _normalize_email(email))
    if identity is None or not verify_password(password, identity["password_hash"]):
        raise InvalidCredentialsError()

    user = get_user(identity["user_id"])
    if user is None:
        raise InvalidCredentialsError()

    claim_guest_score_for_today(user["user_id"], guest_access_token)
    return user, create_access_token(user["user_id"]), create_refresh_token(user["user_id"])


def set_password(user_id: str, new_password: str) -> None:
    """Lets a Google-only account add a password identity, so it can later sign in
    without Google too. One-time setup -- changing an existing password goes through
    the forgot-password flow instead.
    """
    user = get_user(user_id)
    email = (user or {}).get("email")
    if not email:
        raise NoEmailOnFileError()

    normalized_email = _normalize_email(email)
    existing = find_identity("password", normalized_email)
    if existing is not None:
        if existing["user_id"] == user_id:
            raise PasswordAlreadySetError()
        raise EmailAlreadyRegisteredError(normalized_email)

    create_password_identity(user_id, normalized_email, hash_password(new_password))


def change_password(user_id: str, current_password: str, new_password: str) -> None:
    """Lets an account with an existing password replace it, given the correct
    current password -- the in-Settings counterpart to the email-code-based
    forgot-password flow, for someone who's already signed in and just wants to
    change their password directly.
    """
    user = get_user(user_id)
    email = (user or {}).get("email")
    if not email:
        raise NoEmailOnFileError()

    normalized_email = _normalize_email(email)
    identity = find_identity("password", normalized_email)
    if identity is None or identity["user_id"] != user_id:
        raise NoPasswordSetError()
    if not verify_password(current_password, identity["password_hash"]):
        raise InvalidCredentialsError()

    update_password_hash(normalized_email, hash_password(new_password))


def link_google_account(user_id: str, google_id_token: str) -> None:
    """Lets a password-registered account attach a Google identity with the same
    email, so it can later sign in with Google too.
    """
    claims = verify_google_id_token(google_id_token)
    google_email = claims.get("email")
    user = get_user(user_id)
    user_email = (user or {}).get("email")
    if not user_email or not google_email or _normalize_email(google_email) != _normalize_email(user_email):
        raise GoogleAccountEmailMismatchError()

    existing = find_identity("google", claims["sub"])
    if existing is not None:
        if existing["user_id"] == user_id:
            return  # already linked -- idempotent no-op
        raise GoogleAccountAlreadyLinkedError()

    create_google_identity(user_id, claims["sub"])
    mark_email_verified(user_id)


def dev_login(display_name: str) -> tuple[dict, str, str]:
    """Issues a real token pair for a brand-new user, bypassing identity verification.

    Only wired up when ALLOW_DEV_LOGIN=true, so it can never be reached in a real
    deployment. Exists purely so the rest of the authenticated API (scores,
    leaderboards) can be built and tested before the Google OAuth client exists.
    """
    user = create_user_with_identity(
        provider="dev",
        provider_subject=display_name,
        display_name=display_name,
        email_verified=True,
    )
    return user, create_access_token(user["user_id"]), create_refresh_token(user["user_id"])
