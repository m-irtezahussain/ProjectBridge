from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.validation import normalize_name
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User


class Business(Base):
    """A business owned by a registered ProjectBridge user."""

    __tablename__ = "business"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    owned_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        unique=True,
    )
    registered_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    owner: Mapped[User] = relationship(back_populates="owned_businesses", lazy="joined")
    projects: Mapped[list[Project]] = relationship(
        back_populates="business",
        lazy="raise",
    )

    @validates("name")
    def validate_name(self, _key: str, value: str) -> str:
        return normalize_name(value, field_name="Business name")

    @validates("owned_by")
    def validate_owned_by(self, _key: str, value: int) -> int:
        if value < 1:
            raise ValueError("owned_by must be a positive user ID")
        return value


