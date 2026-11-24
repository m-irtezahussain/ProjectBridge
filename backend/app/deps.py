from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.managers import (
    AuthManager,
    DocumentManager,
    OAuthManager,
    ProjectManager,
    TaskManager,
)
from app.core.services.document_storage import (
    DocumentStorage,
    DocumentStorageError,
    S3DocumentStorage,
    UnavailableDocumentStorage,
)
from app.core.services.mcp_oauth import MCPTokenService
from app.core.services.rate_limits import AuthRateLimiter
from app.core.services.refresh_tokens import RefreshTokenService
from app.core.services.tokens import TokenService
from app.db import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@lru_cache
def get_auth_manager() -> AuthManager:
    settings: Settings = get_settings()
    return AuthManager(TokenService(settings), RefreshTokenService(settings))


AuthManagerDep = Annotated[AuthManager, Depends(get_auth_manager)]


@lru_cache
def get_oauth_manager() -> OAuthManager:
    settings = get_settings()
    return OAuthManager(settings, MCPTokenService(settings))


OAuthManagerDep = Annotated[OAuthManager, Depends(get_oauth_manager)]


@lru_cache
def get_project_manager() -> ProjectManager:
    return ProjectManager(get_auth_manager())


ProjectManagerDep = Annotated[ProjectManager, Depends(get_project_manager)]


@lru_cache
def get_task_manager() -> TaskManager:
    return TaskManager(get_auth_manager())


TaskManagerDep = Annotated[TaskManager, Depends(get_task_manager)]


@lru_cache
def get_document_manager() -> DocumentManager:
    settings = get_settings()
    storage: DocumentStorage
    try:
        storage = S3DocumentStorage(settings)
    except DocumentStorageError:
        storage = UnavailableDocumentStorage()
    return DocumentManager(settings, storage)


DocumentManagerDep = Annotated[DocumentManager, Depends(get_document_manager)]


@lru_cache
def get_auth_rate_limiter() -> AuthRateLimiter:
    return AuthRateLimiter(get_settings().jwt_secret)


AuthRateLimiterDep = Annotated[AuthRateLimiter, Depends(get_auth_rate_limiter)]

