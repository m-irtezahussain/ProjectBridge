from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.managers import (
    AuthManager,
    ContextResourceManager,
    DocumentManager,
    IngestionManager,
    OAuthManager,
    ProjectManager,
    SearchIndexingManager,
    SemanticSearchManager,
    TaskManager,
)
from app.core.services.document_storage import (
    DocumentStorage,
    DocumentStorageError,
    S3DocumentStorage,
    UnavailableDocumentStorage,
)
from app.core.services.embeddings import OllamaEmbeddingService
from app.core.services.mcp_oauth import MCPTokenService
from app.core.services.ocr import PaddleOCRProvider
from app.core.services.rate_limits import AuthRateLimiter
from app.core.services.refresh_tokens import RefreshTokenService
from app.core.services.resource_cursor import ResourceCursorCodec
from app.core.services.tokens import TokenService
from app.core.services.vector_store import ChromaVectorStore
from app.db import get_session
from app.repositories.search import SearchRepository

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
    settings = get_settings()
    return ProjectManager(
        get_auth_manager(), search_max_attempts=settings.rag_max_attempts
    )


ProjectManagerDep = Annotated[ProjectManager, Depends(get_project_manager)]


@lru_cache
def get_task_manager() -> TaskManager:
    settings = get_settings()
    return TaskManager(
        get_auth_manager(), search_max_attempts=settings.rag_max_attempts
    )


TaskManagerDep = Annotated[TaskManager, Depends(get_task_manager)]


@lru_cache
def get_document_storage() -> DocumentStorage:
    settings = get_settings()
    try:
        return S3DocumentStorage(settings)
    except DocumentStorageError:
        return UnavailableDocumentStorage()


@lru_cache
def get_document_manager() -> DocumentManager:
    return DocumentManager(get_settings(), get_document_storage())


DocumentManagerDep = Annotated[DocumentManager, Depends(get_document_manager)]


@lru_cache
def get_ingestion_manager() -> IngestionManager:
    settings = get_settings()
    return IngestionManager(
        settings,
        get_document_storage(),
        PaddleOCRProvider(settings.ocr_model, settings.ocr_language),
    )


@lru_cache
def get_embedding_service() -> OllamaEmbeddingService:
    return OllamaEmbeddingService(get_settings())


@lru_cache
def get_vector_store() -> ChromaVectorStore:
    return ChromaVectorStore(get_settings())


@lru_cache
def get_semantic_search_manager() -> SemanticSearchManager:
    return SemanticSearchManager(
        get_embedding_service(), get_vector_store(), get_settings()
    )


@lru_cache
def get_search_indexing_manager() -> SearchIndexingManager:
    return SearchIndexingManager(
        get_settings(),
        get_embedding_service(),
        get_vector_store(),
        SearchRepository(),
    )


@lru_cache
def get_context_resource_manager() -> ContextResourceManager:
    return ContextResourceManager(ResourceCursorCodec(get_settings().mcp_jwt_secret))


@lru_cache
def get_auth_rate_limiter() -> AuthRateLimiter:
    return AuthRateLimiter(get_settings().jwt_secret)


AuthRateLimiterDep = Annotated[AuthRateLimiter, Depends(get_auth_rate_limiter)]

