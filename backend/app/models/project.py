from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.validation import normalize_name
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.business import Business


class ProjectStatus(StrEnum):
    ACTIVE = "Active"
    PLANNING = "Planning"
    AT_RISK = "At risk"
    COMPLETED = "Completed"


class Project(Base):
    """A tenant-owned project that can be dismissed without losing history."""

    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("business_id > 0", name="ck_projects_business_id_positive"),
        CheckConstraint(
            "char_length(btrim(name)) BETWEEN 2 AND 200",
            name="ck_projects_name_length",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("business.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[ProjectStatus] = mapped_column(
        SqlEnum(
            ProjectStatus,
            name="project_status",
            values_callable=lambda statuses: [status.value for status in statuses],
            validate_strings=True,
        ),
        nullable=False,
        default=ProjectStatus.PLANNING,
        server_default=ProjectStatus.PLANNING.value,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    business: Mapped[Business] = relationship(back_populates="projects", lazy="raise")

    @validates("name")
    def validate_name(self, _key: str, value: str) -> str:
        return normalize_name(value, field_name="Project name")

    @validates("business_id")
    def validate_business_id(self, _key: str, value: int) -> int:
        if value < 1:
            raise ValueError("business_id must be a positive business ID")
        return value

    @validates("status")
    def validate_status(
        self, _key: str, value: ProjectStatus | str
    ) -> ProjectStatus:
        try:
            return ProjectStatus(value)
        except ValueError as exc:
            raise ValueError("Invalid project status") from exc
