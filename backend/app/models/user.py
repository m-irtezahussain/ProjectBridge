from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.validation import MAX_ACCESS_TOKEN_LENGTH, normalize_email, normalize_name
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.business import Business


class User(Base):
    """A ProjectBridge user with securely hashed credentials."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    access_token: Mapped[str | None] = mapped_column(
        String(2048), nullable=True, unique=True
    )

    owned_businesses: Mapped[list[Business]] = relationship(
        back_populates="owner",
        lazy="selectin",
    )

    @validates("full_name")
    def validate_full_name(self, _key: str, value: str) -> str:
        return normalize_name(value, field_name="Full name")

    @validates("email")
    def validate_email(self, _key: str, value: str) -> str:
        return normalize_email(value)

    @validates("password_hash")
    def validate_password_hash(self, _key: str, value: str) -> str:
        if not value.startswith("$argon2id$"):
            raise ValueError("password_hash must contain an Argon2id hash")
        if not 20 <= len(value) <= 255:
            raise ValueError("password_hash must be between 20 and 255 characters")
        return value

    @validates("access_token")
    def validate_access_token(self, _key: str, value: str | None) -> str | None:
        if value is None:
            return None
        token = value.strip()
        if not token or len(token) > MAX_ACCESS_TOKEN_LENGTH:
            raise ValueError(
                f"access_token must be between 1 and {MAX_ACCESS_TOKEN_LENGTH} characters"
            )
        return token

    @property
    def has_business(self) -> bool:
        """Derive registration state from owned businesses instead of duplicated data."""

        return bool(self.owned_businesses)

