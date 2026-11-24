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
    "DocumentDownloadResult",
    "DocumentListInput",
    "DocumentListResult",
    "DocumentSummary",
    "FinalizeDocumentUploadInput",
    "FinalizeDocumentUploadResult",
    "InitiateDocumentUploadInput",
    "InitiateDocumentUploadResult",
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
    "TaskCreate",
    "TaskRead",
    "TaskUpdate",
    "UploadTarget",
    "UserCreate",
    "UserRead",
]
