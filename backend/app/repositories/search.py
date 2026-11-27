from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from app.models import (
    Document,
    DocumentSearchChunk,
    DocumentStatus,
    Project,
    SearchIndexJob,
    SearchJobOperation,
    SearchJobStatus,
    Task,
)

COALESCIBLE_JOB_STATUSES = {
    SearchJobStatus.QUEUED,
    SearchJobStatus.RETRY_SCHEDULED,
}


class SearchRepository:
    """Postgres-backed RAG queue and tenant-scoped source reads."""

    async def enqueue(
        self,
        session: AsyncSession,
        *,
        business_id: int,
        operation: SearchJobOperation,
        max_attempts: int,
        project_id: int | None = None,
        document_id: int | None = None,
        task_id: int | None = None,
    ) -> SearchIndexJob:
        filters: list[ColumnElement[bool]] = [
            SearchIndexJob.business_id == business_id,
            SearchIndexJob.operation == operation,
            # Never coalesce into a processing job: it may already have read an
            # older source version. A follow-up job guarantees eventual freshness.
            SearchIndexJob.status.in_(COALESCIBLE_JOB_STATUSES),
            self._matches_optional(SearchIndexJob.project_id, project_id),
            self._matches_optional(SearchIndexJob.document_id, document_id),
            self._matches_optional(SearchIndexJob.task_id, task_id),
        ]
        existing = await session.scalar(
            select(SearchIndexJob)
            .where(*filters)
            .order_by(SearchIndexJob.id.desc())
            .limit(1)
        )
        if existing is not None:
            return existing
        job = SearchIndexJob(
            business_id=business_id,
            project_id=project_id,
            document_id=document_id,
            task_id=task_id,
            operation=operation,
            status=SearchJobStatus.QUEUED,
            max_attempts=max_attempts,
            next_attempt_at=datetime.now(UTC),
        )
        session.add(job)
        return job

    @staticmethod
    def _matches_optional(
        column: InstrumentedAttribute[int | None], value: int | None
    ) -> ColumnElement[bool]:
        return column.is_(None) if value is None else column == value

    async def claim(
        self, session: AsyncSession, worker_id: str, lease_seconds: int
    ) -> SearchIndexJob | None:
        now = datetime.now(UTC)
        stale = now - timedelta(seconds=lease_seconds)
        job = await session.scalar(
            select(SearchIndexJob)
            .where(
                or_(
                    and_(
                        SearchIndexJob.status.in_(
                            {
                                SearchJobStatus.QUEUED,
                                SearchJobStatus.RETRY_SCHEDULED,
                            }
                        ),
                        SearchIndexJob.next_attempt_at <= now,
                    ),
                    and_(
                        SearchIndexJob.status == SearchJobStatus.PROCESSING,
                        SearchIndexJob.locked_at < stale,
                    ),
                )
            )
            .order_by(SearchIndexJob.next_attempt_at.asc(), SearchIndexJob.id.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            return None
        job.status = SearchJobStatus.PROCESSING
        job.locked_at = now
        job.worker_id = worker_id
        job.attempts += 1
        return job

    async def get_job(
        self, session: AsyncSession, business_id: int, job_id: int
    ) -> SearchIndexJob | None:
        return await session.scalar(
            select(SearchIndexJob).where(
                SearchIndexJob.id == job_id,
                SearchIndexJob.business_id == business_id,
            )
        )

    async def get_latest_project_job(
        self, session: AsyncSession, business_id: int, project_id: int
    ) -> SearchIndexJob | None:
        return await session.scalar(
            select(SearchIndexJob)
            .where(
                SearchIndexJob.business_id == business_id,
                SearchIndexJob.project_id == project_id,
            )
            .order_by(SearchIndexJob.id.desc())
            .limit(1)
        )

    async def count_pending_project_jobs(
        self, session: AsyncSession, business_id: int, project_id: int
    ) -> int:
        count = await session.scalar(
            select(func.count(SearchIndexJob.id)).where(
                SearchIndexJob.business_id == business_id,
                SearchIndexJob.project_id == project_id,
                SearchIndexJob.status.in_(
                    {
                        SearchJobStatus.QUEUED,
                        SearchJobStatus.PROCESSING,
                        SearchJobStatus.RETRY_SCHEDULED,
                    }
                ),
            )
        )
        return int(count or 0)

    async def get_latest_completed_project_job(
        self, session: AsyncSession, business_id: int, project_id: int
    ) -> SearchIndexJob | None:
        return await session.scalar(
            select(SearchIndexJob)
            .where(
                SearchIndexJob.business_id == business_id,
                SearchIndexJob.project_id == project_id,
                SearchIndexJob.status == SearchJobStatus.COMPLETED,
            )
            .order_by(SearchIndexJob.completed_at.desc(), SearchIndexJob.id.desc())
            .limit(1)
        )

    async def get_document_chunks(
        self, session: AsyncSession, business_id: int, document_id: int
    ) -> list[DocumentSearchChunk]:
        result = await session.scalars(
            select(DocumentSearchChunk)
            .join(Document, DocumentSearchChunk.document_id == Document.id)
            .join(Project, DocumentSearchChunk.project_id == Project.id)
            .where(
                DocumentSearchChunk.business_id == business_id,
                DocumentSearchChunk.document_id == document_id,
                Document.business_id == business_id,
                Document.archived_at.is_(None),
                Document.status.in_({DocumentStatus.AVAILABLE, DocumentStatus.DUPLICATE}),
                Project.business_id == business_id,
                Project.deleted_at.is_(None),
            )
            .order_by(DocumentSearchChunk.chunk_index.asc())
        )
        return list(result.all())

    async def get_active_task(
        self, session: AsyncSession, business_id: int, task_id: int
    ) -> Task | None:
        return await session.scalar(
            select(Task)
            .join(Project, Task.project_id == Project.id)
            .where(
                Task.id == task_id,
                Task.is_deleted.is_(False),
                Project.business_id == business_id,
                Project.deleted_at.is_(None),
            )
        )

    async def list_project_document_ids(
        self, session: AsyncSession, business_id: int, project_id: int
    ) -> list[int]:
        result = await session.scalars(
            select(Document.id)
            .join(Project, Document.project_id == Project.id)
            .where(
                Document.business_id == business_id,
                Document.project_id == project_id,
                Document.archived_at.is_(None),
                Document.status.in_({DocumentStatus.AVAILABLE, DocumentStatus.DUPLICATE}),
                Project.business_id == business_id,
                Project.deleted_at.is_(None),
            )
            .order_by(Document.id.asc())
        )
        return list(result.all())

    async def list_project_task_ids(
        self, session: AsyncSession, business_id: int, project_id: int
    ) -> list[int]:
        result = await session.scalars(
            select(Task.id)
            .join(Project, Task.project_id == Project.id)
            .where(
                Task.project_id == project_id,
                Task.is_deleted.is_(False),
                Project.business_id == business_id,
                Project.deleted_at.is_(None),
            )
            .order_by(Task.id.asc())
        )
        return list(result.all())
