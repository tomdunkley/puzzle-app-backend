from pydantic import BaseModel, Field, field_validator


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class GoogleSignInRequest(BaseModel):
    id_token: str
    guest_access_token: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


def validate_display_name_no_at(display_name: str) -> str:
    if "@" in display_name:
        raise ValueError("display name cannot contain '@'")
    if " " in display_name:
        raise ValueError("display name cannot contain spaces")
    return display_name


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=50)
    guest_access_token: str | None = None

    _validate_display_name = field_validator("display_name")(validate_display_name_no_at)


class LoginRequest(BaseModel):
    email: str
    password: str
    guest_access_token: str | None = None


class DevLoginRequest(BaseModel):
    display_name: str


class VerifyEmailRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8, max_length=128)


class SetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
