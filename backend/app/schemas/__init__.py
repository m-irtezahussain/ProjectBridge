"""Explicit request and response schemas."""

from app.schemas.auth import LoginRequest, NavigationResponse, SessionResponse
from app.schemas.business import BusinessCreate, BusinessRead
from app.schemas.document import (
    ArchiveDocumentResult,
    DocumentDownloadResult,
    DocumentListInput,
    DocumentListResult,
    DocumentSummary,
    FinalizeDocumentUploadInput,
    FinalizeDocumentUploadResult,
    InitiateDocumentUploadInput,
    InitiateDocumentUploadResult,
    UploadTarget,
)
from app.schemas.ingestion import (
    CandidateListResult,
    ConfirmCandidatesInput,
    IngestionRunSummary,
    RetryIngestionInput,
    StartIngestionInput,
    TaskCandidateSummary,
)
from app.schemas.oauth import (
    OAuthClientRegistrationRequest,
    OAuthClientRegistrationResponse,
    OAuthErrorResponse,
    OAuthRevocationResponse,
    OAuthTokenResponse,
)
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate
from app.schemas.user import UserCreate, UserRead

__all__ = [
    "ArchiveDocumentResult",
    "BusinessCreate",
    "BusinessRead",
    "CandidateListResult",
    "ConfirmCandidatesInput",
    "DocumentDownloadResult",
    "DocumentListInput",
    "DocumentListResult",
    "DocumentSummary",
    "FinalizeDocumentUploadInput",
    "FinalizeDocumentUploadResult",
    "InitiateDocumentUploadInput",
    "InitiateDocumentUploadResult",
    "IngestionRunSummary",
    "LoginRequest",
    "NavigationResponse",
    "OAuthClientRegistrationRequest",
    "OAuthClientRegistrationResponse",
    "OAuthErrorResponse",
    "OAuthRevocationResponse",
    "OAuthTokenResponse",
    "ProjectCreate",
    "ProjectRead",
    "ProjectUpdate",
    "SessionResponse",
    "RetryIngestionInput",
    "StartIngestionInput",
    "TaskCreate",
    "TaskRead",
    "TaskUpdate",
    "TaskCandidateSummary",
    "UploadTarget",
    "UserCreate",
    "UserRead",
]
