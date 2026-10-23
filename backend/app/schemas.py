"""Pydantic request/response schemas for auth endpoints."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, model_validator


class LoginRequest(BaseModel):
    """Login with either an email or an institution-scoped register number."""

    password: str = Field(min_length=1)
    email: EmailStr | None = None
    institution_code: str | None = None
    register_number: str | None = None
    totp_code: str | None = None

    @model_validator(mode="after")
    def _one_identifier(self) -> "LoginRequest":
        has_email = self.email is not None
        has_register = (
            self.institution_code is not None and self.register_number is not None
        )
        if has_email == has_register:
            raise ValueError(
                "Provide either email, or both institution_code and "
                "register_number — not both and not neither."
            )
        return self


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    mfa_required: bool = False


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=1)
    all_sessions: bool = False


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class CurrentUser(BaseModel):
    id: int
    email: str | None
    full_name: str
    is_super_admin: bool
    roles: list[str]
    institution_ids: list[int]


class MFASetupResponse(BaseModel):
    secret: str
    otpauth_uri: str


class MFAEnableRequest(BaseModel):
    totp_code: str = Field(min_length=6, max_length=8)
