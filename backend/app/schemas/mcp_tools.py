from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.project import ProjectStatus
from app.models.provenance import ActionOrigin
from app.models.task import TaskPriority, TaskSource, TaskStatus
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.schemas.task import TaskCreate, TaskUpdate


class CurrentAccountSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: int
    full_name: str
    email: str
    business_id: int
    business_name: str
    scopes: list[str]


class ProjectListInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ProjectStatus | None = None
    query: str | None = Field(default=None, min_length=1, max_length=200)
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    sort_by: Literal["id", "name", "status"] = "id"
    sort_order: Literal["asc", "desc"] = "desc"

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("query must not be blank")
        return normalized


class ProjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    name: str
    status: ProjectStatus
    description: str | None


class ProjectListResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projects: list[ProjectSummary]
    total: int
    limit: int
    offset: int
    has_more: bool


class CreateProjectInput(ProjectCreate):
    idempotency_key: str = Field(strict=True, min_length=1, max_length=255)

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("idempotency_key must not be blank")
        return value

    def project_data(self) -> ProjectCreate:
        return ProjectCreate.model_validate(
            self.model_dump(exclude={"idempotency_key"})
        )


class UpdateProjectInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: int = Field(gt=0)
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    status: ProjectStatus | None = None

    @model_validator(mode="after")
    def require_update(self) -> "UpdateProjectInput":
        if not (self.model_fields_set - {"project_id"}):
            raise ValueError("At least one project field must be provided")
        return self

    def project_data(self) -> ProjectUpdate:
        fields = self.model_fields_set - {"project_id"}
        return ProjectUpdate.model_validate(
            {field: getattr(self, field) for field in fields}
        )


class ProjectMutationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project: ProjectSummary
    replayed: bool


class ArchiveProjectInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: int = Field(gt=0)


class ArchiveProjectResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: int
    archived: bool
    replayed: bool


class CreateTaskInput(TaskCreate):
    project_id: int = Field(gt=0)
    idempotency_key: str = Field(strict=True, min_length=1, max_length=255)

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("idempotency_key must not be blank")
        return value

    def task_data(self) -> TaskCreate:
        return TaskCreate.model_validate(
            self.model_dump(exclude={"project_id", "idempotency_key"})
        )


class AssignTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: int = Field(gt=0)
    task_id: int = Field(gt=0)
    assignee_id: int = Field(gt=0)


class UpdateTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: int = Field(gt=0)
    task_id: int = Field(gt=0)
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def require_update(self) -> "UpdateTaskInput":
        if not (self.model_fields_set - {"project_id", "task_id"}):
            raise ValueError("At least one task field must be provided")
        return self

    def task_data(self) -> TaskUpdate:
        fields = self.model_fields_set - {"project_id", "task_id"}
        return TaskUpdate.model_validate(
            {field: getattr(self, field) for field in fields}
        )


class ArchiveTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: int = Field(gt=0)
    task_id: int = Field(gt=0)


class TaskSummary(BaseModel):
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


class TaskSourceReference(BaseModel):
    """Compact provenance only; never includes raw files or complete OCR text."""

    model_config = ConfigDict(extra="forbid")

    task_id: int
    project_id: int
    task_created_via: TaskSource
    has_document_source: bool
    document_id: int | None
    document_project_id: int | None
    original_filename: str | None
    content_sha256: str | None
    candidate_id: int | None
    ingestion_run_id: int | None
    source_excerpt: str | None
    page_number: int | None
    source_line_start: int | None
    source_line_end: int | None
    extractor: str | None
    extractor_version: str | None
    extracted_via: ActionOrigin | None
    ocr_status: str | None
    ocr_engine: str | None
    ocr_engine_version: str | None
    ocr_model: str | None
    ocr_language: str | None
    ingestion_initiated_by_user_id: int | None
    ingestion_initiated_via: ActionOrigin | None


class TaskListInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: int = Field(gt=0)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee_id: int | None = Field(default=None, gt=0)
    query: str | None = Field(default=None, min_length=1, max_length=200)
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    sort_by: Literal["id", "title", "status", "priority"] = "id"
    sort_order: Literal["asc", "desc"] = "desc"

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("query must not be blank")
        return normalized


class TaskListResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tasks: list[TaskSummary]
    total: int
    limit: int
    offset: int
    has_more: bool


class AssigneeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: int
    full_name: str
    email: str


class AssigneeListResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignees: list[AssigneeSummary]


class TaskMutationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: TaskSummary
    replayed: bool


class ArchiveTaskResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: int
    archived: bool
    replayed: bool


class MCPErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal[
        "validation_error",
        "authentication_error",
        "authorization_error",
        "not_found",
        "conflict",
        "service_unavailable",
    ]
    message: str
    retryable: bool = False
