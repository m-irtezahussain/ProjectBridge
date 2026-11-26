from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.managers.projects import BusinessRequiredError, ProjectNotFoundError
from app.core.services.embeddings import EmbeddingService
from app.core.services.knowledge_text import normalize_knowledge_text
from app.core.services.mcp_auth import MCPPrincipal
from app.core.services.vector_store import ChromaVectorStore, VectorHit, VectorRecord
from app.models import (
    Business,
    SearchIndexJob,
    SearchJobOperation,
    SearchJobStatus,
)
from app.repositories.businesses import BusinessRepository
from app.repositories.documents import DocumentRepository
from app.repositories.projects import ProjectRepository
from app.repositories.search import SearchRepository


class SearchConflictError(ValueError):
    pass


@dataclass(frozen=True)
class KnowledgeSearchHit:
    excerpt: str
    distance: float
    source_type: str
    project_id: int
    document_id: int | None
    task_id: int | None
    chunk_id: int | None
    source_text_id: int | None
    ingestion_run_id: int | None
    untrusted_content: bool = True


class SemanticSearchManager:
    """Permission-gated semantic search over explicitly untrusted result text."""

    def __init__(
        self,
        embeddings: EmbeddingService,
        vectors: ChromaVectorStore,
        settings: Settings,
        businesses: BusinessRepository | None = None,
        projects: ProjectRepository | None = None,
        documents: DocumentRepository | None = None,
        search: SearchRepository | None = None,
    ) -> None:
        self._embeddings = embeddings
        self._vectors = vectors
        self._settings = settings
        self._businesses = businesses or BusinessRepository()
        self._projects = projects or ProjectRepository()
        self._documents = documents or DocumentRepository()
        self._search = search or SearchRepository()

    async def _require_business(
        self, session: AsyncSession, principal: MCPPrincipal
    ) -> Business:
        business = await self._businesses.get_for_owner(session, principal.user_id)
        if business is None or business.id != principal.business_id:
            raise BusinessRequiredError("Business registration required")
        return business

    async def search(
        self,
        session: AsyncSession,
        principal: MCPPrincipal,
        query: str,
        *,
        project_id: int | None,
        document_id: int | None,
        limit: int,
    ) -> list[KnowledgeSearchHit]:
        await self._require_business(session, principal)
        if project_id is not None:
            project = await self._projects.get_active(
                session, principal.business_id, project_id
            )
            if project is None:
                raise ProjectNotFoundError("Project not found")
        if document_id is not None:
            document = await self._documents.get(
                session, principal.business_id, document_id
            )
            if document is None or (
                project_id is not None and document.project_id != project_id
            ):
                raise SearchConflictError("Document is not available in the project")
        normalized_query = normalize_knowledge_text(query)
        if not normalized_query:
            raise SearchConflictError("Search query must not be blank")
        embeddings = await self._embeddings.embed([normalized_query])
        vector_hits = await self._vectors.query(
            principal.business_id,
            embeddings[0],
            limit=limit,
            project_id=project_id,
            document_id=document_id,
        )
        hits: list[KnowledgeSearchHit] = []
        for vector_hit in vector_hits:
            hit = self._to_search_hit(
                vector_hit,
                business_id=principal.business_id,
                project_id=project_id,
                document_id=document_id,
            )
            if hit is not None:
                hits.append(hit)
        return hits

    async def enqueue_project_reindex(
        self,
        session: AsyncSession,
        principal: MCPPrincipal,
        project_id: int,
    ) -> SearchIndexJob:
        await self._require_business(session, principal)
        project = await self._projects.get_active(
            session, principal.business_id, project_id
        )
        if project is None:
            raise ProjectNotFoundError("Project not found")
        job = await self._search.enqueue(
            session,
            business_id=principal.business_id,
            project_id=project_id,
            operation=SearchJobOperation.REINDEX_PROJECT,
            max_attempts=self._settings.rag_max_attempts,
        )
        await session.commit()
        return job

    @staticmethod
    def _metadata_int(metadata: dict[str, object], key: str) -> int | None:
        value = metadata.get(key)
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    def _to_search_hit(
        self,
        hit: VectorHit,
        *,
        business_id: int,
        project_id: int | None,
        document_id: int | None,
    ) -> KnowledgeSearchHit | None:
        if self._metadata_int(hit.metadata, "business_id") != business_id:
            return None
        result_project_id = self._metadata_int(hit.metadata, "project_id")
        result_document_id = self._metadata_int(hit.metadata, "document_id")
        if project_id is not None and result_project_id != project_id:
            return None
        if document_id is not None and result_document_id != document_id:
            return None
        source_type = hit.metadata.get("source_type")
        if result_project_id is None or source_type not in {"document", "task"}:
            return None
        return KnowledgeSearchHit(
            excerpt=hit.excerpt,
            distance=hit.distance,
            source_type=source_type,
            project_id=result_project_id,
            document_id=result_document_id,
            task_id=self._metadata_int(hit.metadata, "task_id"),
            chunk_id=self._metadata_int(hit.metadata, "chunk_id"),
            source_text_id=self._metadata_int(hit.metadata, "source_text_id"),
            ingestion_run_id=self._metadata_int(hit.metadata, "ingestion_run_id"),
        )


class SearchIndexingManager:
    """Idempotent worker-side synchronization from Postgres into Chroma."""

    def __init__(
        self,
        settings: Settings,
        embeddings: EmbeddingService,
        vectors: ChromaVectorStore,
        search: SearchRepository | None = None,
    ) -> None:
        self._settings = settings
        self._embeddings = embeddings
        self._vectors = vectors
        self._search = search or SearchRepository()

    async def process_claimed(
        self, session: AsyncSession, job: SearchIndexJob
    ) -> None:
        try:
            await self._dispatch(session, job)
            job.status = SearchJobStatus.COMPLETED
            job.completed_at = datetime.now(UTC)
            job.error_code = None
            job.error_message = None
            job.locked_at = None
            job.worker_id = None
            await session.commit()
        except Exception as error:
            job.error_code = type(error).__name__
            job.error_message = str(error)[:500] or "Search indexing failed"
            job.locked_at = None
            job.worker_id = None
            if job.attempts < job.max_attempts:
                job.status = SearchJobStatus.RETRY_SCHEDULED
                job.next_attempt_at = datetime.now(UTC) + timedelta(
                    seconds=min(300, 2**job.attempts)
                )
            else:
                job.status = SearchJobStatus.FAILED
            await session.commit()

    async def _dispatch(self, session: AsyncSession, job: SearchIndexJob) -> None:
        if job.operation is SearchJobOperation.UPSERT_DOCUMENT:
            if job.document_id is None:
                raise RuntimeError("Document indexing job is missing document_id")
            await self._upsert_document(session, job.business_id, job.document_id)
        elif job.operation is SearchJobOperation.DELETE_DOCUMENT:
            if job.document_id is None:
                raise RuntimeError("Document deletion job is missing document_id")
            await self._delete_document(job.business_id, job.document_id)
        elif job.operation is SearchJobOperation.UPSERT_TASK:
            if job.task_id is None:
                raise RuntimeError("Task indexing job is missing task_id")
            await self._upsert_task(session, job.business_id, job.task_id)
        elif job.operation is SearchJobOperation.DELETE_TASK:
            if job.task_id is None:
                raise RuntimeError("Task deletion job is missing task_id")
            await self._delete_task(job.business_id, job.task_id)
        elif job.operation is SearchJobOperation.DELETE_PROJECT:
            if job.project_id is None:
                raise RuntimeError("Project deletion job is missing project_id")
            await self._delete_project(job.business_id, job.project_id)
        elif job.operation is SearchJobOperation.REINDEX_PROJECT:
            if job.project_id is None:
                raise RuntimeError("Project reindex job is missing project_id")
            await self._reindex_project(session, job.business_id, job.project_id)

    async def _upsert_document(
        self, session: AsyncSession, business_id: int, document_id: int
    ) -> None:
        chunks = await self._search.get_document_chunks(
            session, business_id, document_id
        )
        await self._delete_document(business_id, document_id)
        if not chunks:
            return
        embeddings = await self._embeddings.embed([chunk.content for chunk in chunks])
        records = [
            VectorRecord(
                id=f"document:{document_id}:chunk:{chunk.chunk_index}",
                document=chunk.content,
                embedding=embedding,
                metadata={
                    "business_id": business_id,
                    "project_id": chunk.project_id,
                    "document_id": document_id,
                    "chunk_id": chunk.id,
                    "chunk_index": chunk.chunk_index,
                    "source_text_id": chunk.source_text_id,
                    "ingestion_run_id": chunk.ingestion_run_id,
                    "source_type": "document",
                    "embedding_model": self._embeddings.model,
                    "untrusted_content": True,
                },
            )
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]
        await self._vectors.upsert(business_id, records)

    async def _upsert_task(
        self, session: AsyncSession, business_id: int, task_id: int
    ) -> None:
        task = await self._search.get_active_task(session, business_id, task_id)
        await self._delete_task(business_id, task_id)
        if task is None:
            return
        content = normalize_knowledge_text(
            f"Task: {task.title}\n\n{task.description or ''}"
        )
        embedding = (await self._embeddings.embed([content]))[0]
        metadata: dict[str, str | int | float | bool] = {
            "business_id": business_id,
            "project_id": task.project_id,
            "task_id": task.id,
            "source_type": "task",
            "embedding_model": self._embeddings.model,
            "untrusted_content": True,
        }
        if task.source_document_id is not None:
            metadata["document_id"] = task.source_document_id
        await self._vectors.upsert(
            business_id,
            [
                VectorRecord(
                    id=f"task:{task.id}",
                    document=content,
                    embedding=embedding,
                    metadata=metadata,
                )
            ],
        )

    async def _delete_document(self, business_id: int, document_id: int) -> None:
        await self._vectors.delete(
            business_id, where={"document_id": {"$eq": document_id}}
        )

    async def _delete_task(self, business_id: int, task_id: int) -> None:
        await self._vectors.delete(business_id, ids=[f"task:{task_id}"])

    async def _delete_project(self, business_id: int, project_id: int) -> None:
        await self._vectors.delete(
            business_id, where={"project_id": {"$eq": project_id}}
        )

    async def _reindex_project(
        self, session: AsyncSession, business_id: int, project_id: int
    ) -> None:
        await self._delete_project(business_id, project_id)
        document_ids = await self._search.list_project_document_ids(
            session, business_id, project_id
        )
        task_ids = await self._search.list_project_task_ids(
            session, business_id, project_id
        )
        for document_id in document_ids:
            await self._upsert_document(session, business_id, document_id)
        for task_id in task_ids:
            await self._upsert_task(session, business_id, task_id)
