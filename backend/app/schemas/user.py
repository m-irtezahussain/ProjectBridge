from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.validation import (
    MAX_EMAIL_LENGTH,
    MAX_NAME_LENGTH,
    MAX_PASSWORD_LENGTH,
    MIN_NAME_LENGTH,
    MIN_PASSWORD_LENGTH,
    normalize_email,
    normalize_name,
    validate_password,
)


class UserCreate(BaseModel):
    """Strict registration input; plaintext password is hashed before persistence."""

    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(
        strict=True, min_length=MIN_NAME_LENGTH, max_length=MAX_NAME_LENGTH
    )
    email: str = Field(strict=True, min_length=3, max_length=MAX_EMAIL_LENGTH)
    password: str = Field(
        strict=True, min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH
    )
    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        return normalize_name(value, field_name="Full name")

    @field_validator("email")
    @classmethod
    def normalize_user_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def validate_user_password(cls, value: str) -> str:
        return validate_password(value)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    full_name: str
    email: str
    has_business: bool

