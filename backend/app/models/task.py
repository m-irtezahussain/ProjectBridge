from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.validation import normalize_name, normalize_task_description
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.project import Project


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROCESS = "in process"
    IN_REVIEW = "in review"
    DONE = "done"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskSource(StrEnum):
    API = "api"
    MCP = "mcp"


class Task(Base):
    """A project task that is soft-deleted and records its creation interface."""

    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("project_id > 0", name="ck_tasks_project_id_positive"),
        CheckConstraint(
            "char_length(btrim(title)) BETWEEN 2 AND 200",
            name="ck_tasks_title_length",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        SqlEnum(
            TaskStatus,
            name="task_status",
            values_callable=lambda statuses: [status.value for status in statuses],
            validate_strings=True,
        ),
        nullable=False,
        default=TaskStatus.TODO,
        server_default=TaskStatus.TODO.value,
    )
    priority: Mapped[TaskPriority] = mapped_column(
        SqlEnum(
            TaskPriority,
            name="task_priority",
            values_callable=lambda priorities: [priority.value for priority in priorities],
            validate_strings=True,
        ),
        nullable=False,
        default=TaskPriority.MEDIUM,
        server_default=TaskPriority.MEDIUM.value,
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )
    created_by: Mapped[TaskSource] = mapped_column(
        SqlEnum(
            TaskSource,
            name="task_source",
            values_callable=lambda sources: [source.value for source in sources],
            validate_strings=True,
        ),
        nullable=False,
        default=TaskSource.API,
        server_default=TaskSource.API.value,
    )

    project: Mapped[Project] = relationship(back_populates="tasks", lazy="raise")

    @validates("title")
    def validate_title(self, _key: str, value: str) -> str:
        return normalize_name(value, field_name="Task title")

    @validates("description")
    def validate_description(self, _key: str, value: str | None) -> str | None:
        return normalize_task_description(value)

    @validates("project_id")
    def validate_project_id(self, _key: str, value: int) -> int:
        if value < 1:
            raise ValueError("project_id must be a positive project ID")
        return value

    @validates("status")
    def validate_status(self, _key: str, value: TaskStatus | str) -> TaskStatus:
        try:
            return TaskStatus(value)
        except ValueError as exc:
            raise ValueError("Invalid task status") from exc

    @validates("priority")
    def validate_priority(self, _key: str, value: TaskPriority | str) -> TaskPriority:
        try:
            return TaskPriority(value)
        except ValueError as exc:
            raise ValueError("Invalid task priority") from exc

    @validates("created_by")
    def validate_created_by(self, _key: str, value: TaskSource | str) -> TaskSource:
        try:
            return TaskSource(value)
        except ValueError as exc:
            raise ValueError("Invalid task source") from exc
