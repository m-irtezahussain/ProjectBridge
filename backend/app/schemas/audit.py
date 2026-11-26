from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import ActionOrigin


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    business_id: int
    actor_user_id: int | None
    interface: ActionOrigin
    action: str
    target_type: str
    target_id: int | None
    outcome: str
    details: dict[str, object] | None
    occurred_at: datetime


class AuditEventPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AuditEventRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class AuditEventListInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interface: ActionOrigin | None = None
    action: str | None = Field(default=None, min_length=1, max_length=100)
    outcome: str | None = Field(default=None, min_length=1, max_length=50)
    target_type: str | None = Field(default=None, min_length=1, max_length=50)
    actor_user_id: int | None = Field(default=None, gt=0)
    occurred_from: datetime | None = None
    occurred_to: datetime | None = None
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
