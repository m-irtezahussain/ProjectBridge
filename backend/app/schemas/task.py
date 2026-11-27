from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.validation import (
    MAX_NAME_LENGTH,
    MAX_TASK_DESCRIPTION_LENGTH,
    MIN_NAME_LENGTH,
    normalize_name,
    normalize_task_description,
)
from app.models.task import TaskPriority, TaskSource, TaskStatus


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(
        strict=True, min_length=MIN_NAME_LENGTH, max_length=MAX_NAME_LENGTH
    )
    description: str | None = Field(
        default=None, strict=True, max_length=MAX_TASK_DESCRIPTION_LENGTH
    )
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee_id: int | None = Field(default=None, gt=0)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return normalize_name(value, field_name="Task title")

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return normalize_task_description(value)


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(
        default=None,
        strict=True,
        min_length=MIN_NAME_LENGTH,
        max_length=MAX_NAME_LENGTH,
    )
    description: str | None = Field(
        default=None, strict=True, max_length=MAX_TASK_DESCRIPTION_LENGTH
    )
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee_id: int | None = Field(default=None, gt=0)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_name(value, field_name="Task title")

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return normalize_task_description(value)

    @model_validator(mode="after")
    def require_update(self) -> "TaskUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one task field must be provided")
        for field_name in ("title", "status", "priority"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"Task {field_name} cannot be null")
        return self


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    assignee_id: int | None
    source_document_id: int | None
    source_candidate_id: int | None
    project_id: int
    is_deleted: bool
    created_by: TaskSource
    version: int


class TaskPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tasks: list[TaskRead]
    total: int
    limit: int
    offset: int
    has_more: bool
