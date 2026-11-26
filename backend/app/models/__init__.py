"""ORM model registry used by the application and Alembic."""

from app.models.audit import AuditEvent
from app.models.auth_rate_limit import AuthRateLimit
from app.models.base import Base
from app.models.business import Business
from app.models.document import Document, DocumentAuditEvent, DocumentStatus
from app.models.ingestion import (
    CandidateStatus,
    DocumentSearchChunk,
    DocumentText,
    IngestionEvent,
    IngestionRun,
    IngestionStatus,
    StageStatus,
    TaskCandidate,
)
from app.models.mcp_operations import MCPAuditEvent, MCPIdempotencyRecord
from app.models.oauth import (
    OAuthAuthorizationCode,
    OAuthClient,
    OAuthGrant,
    OAuthRefreshToken,
)
from app.models.project import Project, ProjectStatus
from app.models.provenance import ActionOrigin
from app.models.refresh_token import RefreshToken
from app.models.search import SearchIndexJob, SearchJobOperation, SearchJobStatus
from app.models.task import Task, TaskPriority, TaskSource, TaskStatus
from app.models.user import User

__all__ = [
    "AuthRateLimit",
    "AuditEvent",
    "Base",
    "Business",
    "Document",
    "DocumentAuditEvent",
    "DocumentStatus",
    "CandidateStatus",
    "DocumentSearchChunk",
    "DocumentText",
    "IngestionRun",
    "IngestionEvent",
    "IngestionStatus",
    "StageStatus",
    "TaskCandidate",
    "MCPAuditEvent",
    "MCPIdempotencyRecord",
    "OAuthAuthorizationCode",
    "OAuthClient",
    "OAuthGrant",
    "OAuthRefreshToken",
    "Project",
    "ProjectStatus",
    "ActionOrigin",
    "RefreshToken",
    "SearchIndexJob",
    "SearchJobOperation",
    "SearchJobStatus",
    "Task",
    "TaskPriority",
    "TaskSource",
    "TaskStatus",
    "User",
]

