from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.validation import MAX_NAME_LENGTH, MIN_NAME_LENGTH, normalize_name


class BusinessCreate(BaseModel):
    """Business registration input; ownership comes from the authenticated user."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        strict=True, min_length=MIN_NAME_LENGTH, max_length=MAX_NAME_LENGTH
    )

    @field_validator("name")
    @classmethod
    def normalize_business_name(cls, value: str) -> str:
        return normalize_name(value, field_name="Business name")


class BusinessRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    name: str
    owned_by: int
    registered_on: datetime

