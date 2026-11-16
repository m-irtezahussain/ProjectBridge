from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.validation import MAX_NAME_LENGTH, MIN_NAME_LENGTH, normalize_name
from app.models.project import ProjectStatus


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        strict=True, min_length=MIN_NAME_LENGTH, max_length=MAX_NAME_LENGTH
    )
    status: ProjectStatus = ProjectStatus.PLANNING

    @field_validator("name")
    @classmethod
    def normalize_project_name(cls, value: str) -> str:
        return normalize_name(value, field_name="Project name")


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(
        default=None,
        strict=True,
        min_length=MIN_NAME_LENGTH,
        max_length=MAX_NAME_LENGTH,
    )
    status: ProjectStatus | None = None

    @field_validator("name")
    @classmethod
    def normalize_project_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_name(value, field_name="Project name")

    @model_validator(mode="after")
    def require_update(self) -> "ProjectUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one project field must be provided")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("Project name cannot be null")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("Project status cannot be null")
        return self


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    name: str
    business_id: int
    status: ProjectStatus
