"""ORM model registry used by the application and Alembic."""

from app.models.auth_rate_limit import AuthRateLimit
from app.models.base import Base
from app.models.business import Business
from app.models.oauth import (
    OAuthAuthorizationCode,
    OAuthClient,
    OAuthGrant,
    OAuthRefreshToken,
)
from app.models.project import Project, ProjectStatus
from app.models.refresh_token import RefreshToken
from app.models.task import Task, TaskPriority, TaskSource, TaskStatus
from app.models.user import User

__all__ = [
    "AuthRateLimit",
    "Base",
    "Business",
    "OAuthAuthorizationCode",
    "OAuthClient",
    "OAuthGrant",
    "OAuthRefreshToken",
    "Project",
    "ProjectStatus",
    "RefreshToken",
    "Task",
    "TaskPriority",
    "TaskSource",
    "TaskStatus",
    "User",
]

