"""Request and response bodies."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _check_password(value: str) -> str:
    # bcrypt only uses the first 72 bytes of a password.
    if len(value.encode()) > 72:
        raise ValueError("password must be at most 72 bytes")
    return value


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8)
    phone_number: str | None = None
    date_of_birth: date | None = None

    _validate_password = field_validator("password")(_check_password)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8)

    _validate_password = field_validator("new_password")(_check_password)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)

    _validate_password = field_validator("new_password")(_check_password)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str
    phone_number: str | None
    date_of_birth: date | None
    is_active: bool | None
    is_email_verified: bool | None
    created_at: datetime | None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserOut


class MessageResponse(BaseModel):
    message: str


class ForgotPasswordResponse(BaseModel):
    message: str
    # Only filled in when DEV_MODE=true, because this app doesn't send email.
    reset_token: str | None = None
