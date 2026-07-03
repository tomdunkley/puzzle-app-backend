from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependency import get_current_user_id
from app.auth.google import GoogleTokenError
from app.auth.jwt import InvalidTokenError, create_access_token, create_refresh_token, decode_token
from app.config import settings
from app.models.auth import (
    ChangePasswordRequest,
    DevLoginRequest,
    ForgotPasswordRequest,
    GoogleSignInRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SetPasswordRequest,
    TokenPair,
    VerifyEmailRequest,
)
from app.services.user_service import ProfanityError
from app.services.auth_service import (
    DisplayNameTakenError,
    EmailAlreadyRegisteredError,
    GoogleAccountAlreadyLinkedError,
    GoogleAccountEmailMismatchError,
    InvalidCredentialsError,
    NoEmailOnFileError,
    NoPasswordSetError,
    PasswordAlreadySetError,
    change_password,
    dev_login,
    link_google_account,
    login_with_password,
    register_with_password,
    set_password,
    sign_in_with_google,
)
from app.services.password_reset_service import (
    PasswordResetCodeExpiredError,
    PasswordResetCodeIncorrectError,
)
from app.services.password_reset_service import ResendCooldownError as PasswordResetCooldownError
from app.services.password_reset_service import TooManyAttemptsError as PasswordResetTooManyAttemptsError
from app.services.password_reset_service import confirm_password_reset, request_password_reset
from app.services.password_reset_service import resend_password_reset as resend_password_reset_code
from app.services.user_service import (
    EmailTakenError,
    create_guest_user,
    get_email_verified,
    get_user,
    mark_email_verified,
)
from app.services.verification_service import (
    ResendCooldownError,
    TooManyAttemptsError,
    VerificationCodeExpiredError,
    VerificationCodeIncorrectError,
    resend_verification_code,
    verify_code,
)

router = APIRouter()


@router.post("/auth/google", response_model=TokenPair)
def google_sign_in(body: GoogleSignInRequest):
    try:
        _user, access_token, refresh_token = sign_in_with_google(body.id_token, body.guest_access_token)
    except GoogleTokenError as exc:
        raise HTTPException(status_code=401, detail=f"invalid Google token: {exc}") from exc
    except EmailTakenError as exc:
        raise HTTPException(
            status_code=409,
            detail="an account with this email already exists -- sign in and link Google from Settings instead",
        ) from exc
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/auth/register", response_model=TokenPair, status_code=201)
def register(body: RegisterRequest):
    try:
        _user, access_token, refresh_token = register_with_password(
            body.email, body.password, body.display_name, body.guest_access_token
        )
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(status_code=409, detail="email already registered") from exc
    except EmailTakenError as exc:
        raise HTTPException(status_code=409, detail="email already registered") from exc
    except ProfanityError as exc:
        raise HTTPException(status_code=400, detail="display name contains inappropriate language") from exc
    except DisplayNameTakenError as exc:
        raise HTTPException(status_code=409, detail="display name already taken") from exc
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/auth/login", response_model=TokenPair)
def login(body: LoginRequest):
    try:
        _user, access_token, refresh_token = login_with_password(
            body.email, body.password, body.guest_access_token
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail="invalid email or password") from exc
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/auth/guest", response_model=TokenPair, status_code=201)
def guest_sign_in():
    user = create_guest_user()
    return TokenPair(
        access_token=create_access_token(user["user_id"]),
        refresh_token=create_refresh_token(user["user_id"]),
    )


@router.post("/auth/refresh", response_model=TokenPair)
def refresh(body: RefreshRequest):
    try:
        user_id = decode_token(body.refresh_token, expected_type="refresh")
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"invalid refresh token: {exc}") from exc
    return TokenPair(access_token=create_access_token(user_id), refresh_token=body.refresh_token)


if settings.allow_dev_login:

    @router.post("/auth/dev-login", response_model=TokenPair)
    def dev_login_endpoint(body: DevLoginRequest):
        """Dev-only: mints a real session for a brand-new user, no identity check.

        Only registered when ALLOW_DEV_LOGIN=true. Lets the rest of the
        authenticated API be exercised before the Google OAuth client exists.
        """
        _user, access_token, refresh_token = dev_login(body.display_name)
        return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/auth/verify-email")
def verify_email(body: VerifyEmailRequest, user_id: str = Depends(get_current_user_id)):
    # Retrofit/OkHttp always reports a null body for a bare 204, which crashes the
    # Android client's non-nullable Unit-returning suspend calls -- return a trivial
    # body instead, same as the other mutation endpoints below.
    if get_email_verified(user_id):
        # Already verified -- a double-submit (e.g. a duplicate tap) would otherwise
        # land here with no matching code row and see a confusing "expired" message.
        return {"status": "ok"}
    try:
        verify_code(user_id, body.code)
    except VerificationCodeExpiredError as exc:
        raise HTTPException(
            status_code=400, detail="verification code expired, please request a new one"
        ) from exc
    except VerificationCodeIncorrectError as exc:
        raise HTTPException(status_code=400, detail="incorrect verification code") from exc
    except TooManyAttemptsError as exc:
        raise HTTPException(
            status_code=429, detail="too many attempts, please request a new code"
        ) from exc
    mark_email_verified(user_id)
    return {"status": "ok"}


@router.post("/auth/resend-verification")
def resend_verification(user_id: str = Depends(get_current_user_id)):
    user = get_user(user_id)
    email = (user or {}).get("email")
    if not email:
        raise HTTPException(status_code=400, detail="no email on file for this account")
    try:
        resend_verification_code(user_id, email)
    except ResendCooldownError as exc:
        raise HTTPException(
            status_code=429, detail="please wait before requesting another code"
        ) from exc
    return {"status": "ok"}


@router.post("/auth/forgot-password")
def forgot_password(body: ForgotPasswordRequest):
    request_password_reset(body.email)
    return {"status": "ok"}


@router.post("/auth/resend-password-reset")
def resend_password_reset(body: ForgotPasswordRequest):
    try:
        resend_password_reset_code(body.email)
    except PasswordResetCooldownError as exc:
        raise HTTPException(
            status_code=429, detail="please wait before requesting another code"
        ) from exc
    return {"status": "ok"}


@router.post("/auth/reset-password")
def reset_password(body: ResetPasswordRequest):
    try:
        confirm_password_reset(body.email, body.code, body.new_password)
    except PasswordResetCodeExpiredError as exc:
        raise HTTPException(
            status_code=400, detail="reset code expired, please request a new one"
        ) from exc
    except PasswordResetCodeIncorrectError as exc:
        raise HTTPException(status_code=400, detail="incorrect reset code") from exc
    except PasswordResetTooManyAttemptsError as exc:
        raise HTTPException(
            status_code=429, detail="too many attempts, please request a new code"
        ) from exc
    return {"status": "ok"}


@router.post("/auth/set-password")
def set_password_endpoint(body: SetPasswordRequest, user_id: str = Depends(get_current_user_id)):
    try:
        set_password(user_id, body.new_password)
    except NoEmailOnFileError as exc:
        raise HTTPException(status_code=400, detail="no email on file for this account") from exc
    except PasswordAlreadySetError as exc:
        raise HTTPException(status_code=409, detail="a password is already set for this account") from exc
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=409, detail="email already registered to a different account"
        ) from exc
    return {"status": "ok"}


@router.post("/auth/change-password")
def change_password_endpoint(body: ChangePasswordRequest, user_id: str = Depends(get_current_user_id)):
    try:
        change_password(user_id, body.current_password, body.new_password)
    except NoEmailOnFileError as exc:
        raise HTTPException(status_code=400, detail="no email on file for this account") from exc
    except NoPasswordSetError as exc:
        raise HTTPException(status_code=400, detail="no password is set for this account") from exc
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail="current password is incorrect") from exc
    return {"status": "ok"}


@router.post("/auth/link-google")
def link_google_endpoint(body: GoogleSignInRequest, user_id: str = Depends(get_current_user_id)):
    try:
        link_google_account(user_id, body.id_token)
    except GoogleTokenError as exc:
        raise HTTPException(status_code=401, detail=f"invalid Google token: {exc}") from exc
    except GoogleAccountEmailMismatchError as exc:
        raise HTTPException(
            status_code=400, detail="that Google account's email doesn't match your account email"
        ) from exc
    except GoogleAccountAlreadyLinkedError as exc:
        raise HTTPException(
            status_code=409, detail="that Google account is already linked to a different user"
        ) from exc
    return {"status": "ok"}
