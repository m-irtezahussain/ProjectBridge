from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.project import ProjectStatus
from app.models.task import TaskPriority, TaskStatus
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


class ProjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    name: str
    status: ProjectStatus
    description: str | None


class ProjectListResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projects: list[ProjectSummary]


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


class UpdateTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: int = Field(gt=0)
    task_id: int = Field(gt=0)
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None

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
    project_id: int


class TaskMutationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: TaskSummary
    replayed: bool


class ArchiveTaskResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: int
    archived: bool
