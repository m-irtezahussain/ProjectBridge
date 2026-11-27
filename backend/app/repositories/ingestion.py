from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DocumentSearchChunk,
    DocumentText,
    IngestionEvent,
    IngestionRun,
    IngestionStatus,
    Task,
    TaskCandidate,
)


class IngestionRepository:
    def add_run(self, session: AsyncSession, run: IngestionRun) -> None:
        session.add(run)

    def add_event(self, session: AsyncSession, event: IngestionEvent) -> None:
        session.add(event)

    async def get_run(
        self, session: AsyncSession, business_id: int, run_id: int
    ) -> IngestionRun | None:
        return await session.scalar(
            select(IngestionRun).where(
                IngestionRun.id == run_id, IngestionRun.business_id == business_id
            )
        )

    async def get_run_for_update(
        self, session: AsyncSession, business_id: int, run_id: int
    ) -> IngestionRun | None:
        return await session.scalar(
            select(IngestionRun)
            .where(
                IngestionRun.id == run_id,
                IngestionRun.business_id == business_id,
            )
            .with_for_update()
        )

    async def get_active_for_document(
        self, session: AsyncSession, business_id: int, document_id: int
    ) -> IngestionRun | None:
        return await session.scalar(
            select(IngestionRun)
            .where(
                IngestionRun.business_id == business_id,
                IngestionRun.document_id == document_id,
                IngestionRun.status.not_in(
                    {IngestionStatus.COMPLETED, IngestionStatus.FAILED}
                ),
            )
            .order_by(IngestionRun.id.desc())
            .limit(1)
        )

    async def get_latest_for_document(
        self, session: AsyncSession, business_id: int, document_id: int
    ) -> IngestionRun | None:
        return await session.scalar(
            select(IngestionRun)
            .where(
                IngestionRun.business_id == business_id,
                IngestionRun.document_id == document_id,
            )
            .order_by(IngestionRun.id.desc())
            .limit(1)
        )

    async def claim(
        self, session: AsyncSession, worker_id: str, lease_seconds: int
    ) -> IngestionRun | None:
        now = datetime.now(UTC)
        stale = now - timedelta(seconds=lease_seconds)
        run = await session.scalar(
            select(IngestionRun)
            .where(
                or_(
                    IngestionRun.status.in_(
                        {IngestionStatus.QUEUED, IngestionStatus.RETRY_SCHEDULED}
                    )
                    & (IngestionRun.next_attempt_at <= now),
                    (IngestionRun.status == IngestionStatus.PROCESSING)
                    & (IngestionRun.locked_at < stale),
                )
            )
            .order_by(IngestionRun.next_attempt_at.asc(), IngestionRun.id.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if run is None:
            return None
        run.status = IngestionStatus.PROCESSING
        run.locked_at = now
        run.worker_id = worker_id
        run.attempts += 1
        return run

    async def get_text(
        self,
        session: AsyncSession,
        business_id: int,
        document_id: int,
        ingestion_run_id: int,
    ) -> DocumentText | None:
        return await session.scalar(
            select(DocumentText).where(
                DocumentText.business_id == business_id,
                DocumentText.document_id == document_id,
                DocumentText.ingestion_run_id == ingestion_run_id,
            )
        )

    def add_text(self, session: AsyncSession, text: DocumentText) -> None:
        session.add(text)

    async def list_candidates(
        self, session: AsyncSession, business_id: int, run_id: int
    ) -> list[TaskCandidate]:
        result = await session.scalars(
            select(TaskCandidate)
            .where(
                TaskCandidate.business_id == business_id,
                TaskCandidate.ingestion_run_id == run_id,
            )
            .order_by(TaskCandidate.id.asc())
        )
        return list(result.all())

    def add_candidate(self, session: AsyncSession, candidate: TaskCandidate) -> None:
        session.add(candidate)

    async def replace_chunks(
        self,
        session: AsyncSession,
        *,
        business_id: int,
        project_id: int,
        document_id: int,
        source_text_id: int,
        ingestion_run_id: int,
        chunks: list[str],
    ) -> None:
        await session.execute(
            delete(DocumentSearchChunk).where(
                DocumentSearchChunk.business_id == business_id,
                DocumentSearchChunk.document_id == document_id,
            )
        )
        session.add_all(
            DocumentSearchChunk(
                business_id=business_id,
                project_id=project_id,
                document_id=document_id,
                source_text_id=source_text_id,
                ingestion_run_id=ingestion_run_id,
                chunk_index=index,
                content=content,
            )
            for index, content in enumerate(chunks)
        )

    async def get_task_for_candidate(
        self, session: AsyncSession, candidate_id: int
    ) -> Task | None:
        return await session.scalar(
            select(Task).where(Task.source_candidate_id == candidate_id)
        )
