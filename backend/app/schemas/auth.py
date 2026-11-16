from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.validation import (
    MAX_EMAIL_LENGTH,
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    normalize_email,
)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(strict=True, min_length=3, max_length=MAX_EMAIL_LENGTH)
    password: str = Field(
        strict=True, min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH
    )

    @field_validator("email")
    @classmethod
    def normalize_login_email(cls, value: str) -> str:
        return normalize_email(value)


class NavigationResponse(BaseModel):
    message: str
    next: str


class SessionResponse(BaseModel):
    authenticated: bool
    has_business: bool
    full_name: str | None = None
    email: str | None = None
    next: str
