from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentStatus
from app.models.provenance import ActionOrigin

SupportedDocumentMime = Literal["application/pdf", "image/jpeg", "image/png"]


class InitiateDocumentUploadInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(strict=True, min_length=1, max_length=500)
    mime_type: SupportedDocumentMime
    size_bytes: int = Field(strict=True, gt=0)
    project_id: int | None = Field(default=None, gt=0)


class FinalizeDocumentUploadInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: int = Field(gt=0)


class DocumentListInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: int | None = Field(default=None, gt=0)
    status: DocumentStatus | None = None
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    project_id: int | None
    created_via: ActionOrigin
    original_filename: str
    status: DocumentStatus
    declared_mime_type: str
    detected_mime_type: str | None
    declared_size: int
    size_bytes: int | None
    content_sha256: str | None
    duplicate_of_document_id: int | None
    failure_code: str | None
    failure_message: str | None
    created_at: datetime
    updated_at: datetime


class DocumentListResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documents: list[DocumentSummary]
    total: int
    limit: int
    offset: int
    has_more: bool


class UploadTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: Literal["POST"] = "POST"
    url: str
    fields: dict[str, str]
    expires_in: int


class InitiateDocumentUploadResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document: DocumentSummary
    upload: UploadTarget


class FinalizeDocumentUploadResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document: DocumentSummary
    replayed: bool


class ArchiveDocumentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: int
    archived: bool
    replayed: bool


class DocumentDownloadResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: int
    url: str
    expires_in: int
