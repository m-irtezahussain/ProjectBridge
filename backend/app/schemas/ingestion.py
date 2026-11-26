from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.ingestion import CandidateStatus, IngestionStatus, StageStatus
from app.models.provenance import ActionOrigin


class StartIngestionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: int = Field(gt=0)
    project_id: int = Field(gt=0)
    idempotency_key: str = Field(strict=True, min_length=1, max_length=255)

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("idempotency_key must not be blank")
        return value


class IngestionRunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    document_id: int
    project_id: int
    requested_by_user_id: int
    initiated_via: ActionOrigin
    status: IngestionStatus
    ocr_status: StageStatus
    extraction_status: StageStatus
    task_status: StageStatus
    indexing_status: StageStatus
    attempts: int
    max_attempts: int
    last_error_stage: str | None
    last_error_code: str | None
    last_error_message: str | None
    next_attempt_at: datetime
    completed_at: datetime | None
    version: int


class TaskCandidateSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    title: str
    description: str | None
    source_excerpt: str
    source_text_id: int
    page_number: int | None
    source_line_start: int | None
    source_line_end: int | None
    extractor: str
    extractor_version: str
    extracted_via: ActionOrigin
    confidence: float | None
    status: CandidateStatus
    created_task_id: int | None
    failure_message: str | None


class CandidateListResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ingestion: IngestionRunSummary
    candidates: list[TaskCandidateSummary]


class ConfirmCandidatesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ingestion_run_id: int = Field(gt=0)
    approved_candidate_ids: list[int] = Field(default_factory=list, max_length=200)
    rejected_candidate_ids: list[int] = Field(default_factory=list, max_length=200)
    expected_version: int = Field(gt=0)
    idempotency_key: str = Field(strict=True, min_length=1, max_length=255)

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("idempotency_key must not be blank")
        return value

    @model_validator(mode="after")
    def validate_decisions(self) -> "ConfirmCandidatesInput":
        approved = set(self.approved_candidate_ids)
        rejected = set(self.rejected_candidate_ids)
        if len(approved) != len(self.approved_candidate_ids) or len(rejected) != len(
            self.rejected_candidate_ids
        ):
            raise ValueError("Candidate IDs must not be duplicated")
        if approved & rejected:
            raise ValueError("A candidate cannot be both approved and rejected")
        return self


class RetryIngestionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ingestion_run_id: int = Field(gt=0)
    expected_version: int = Field(gt=0)
    idempotency_key: str = Field(strict=True, min_length=1, max_length=255)

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("idempotency_key must not be blank")
        return value
