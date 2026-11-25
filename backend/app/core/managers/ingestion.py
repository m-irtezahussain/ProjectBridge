import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.managers.documents import DocumentNotFoundError, DocumentStateConflictError
from app.core.managers.projects import BusinessRequiredError, ProjectNotFoundError
from app.core.services.document_storage import DocumentStorage
from app.core.services.mcp_auth import MCPPrincipal
from app.core.services.ocr import OCRProvider
from app.core.services.task_extraction import SafeTaskCandidateExtractor, chunk_untrusted_text
from app.models import (
    ActionOrigin,
    Business,
    CandidateStatus,
    DocumentStatus,
    DocumentText,
    IngestionEvent,
    IngestionRun,
    IngestionStatus,
    StageStatus,
    Task,
    TaskCandidate,
    TaskPriority,
    TaskSource,
    TaskStatus,
)
from app.repositories.businesses import BusinessRepository
from app.repositories.documents import DocumentRepository
from app.repositories.ingestion import IngestionRepository
from app.repositories.mcp_operations import MCPAuditRepository
from app.repositories.projects import ProjectRepository
from app.repositories.tasks import TaskRepository


class IngestionNotFoundError(ValueError):
    pass


class IngestionConflictError(ValueError):
    pass


class IngestionManager:
    """Durable, human-gated document-to-task ingestion orchestration."""

    def __init__(
        self,
        settings: Settings,
        storage: DocumentStorage,
        ocr: OCRProvider,
        businesses: BusinessRepository | None = None,
        projects: ProjectRepository | None = None,
        documents: DocumentRepository | None = None,
        ingestion: IngestionRepository | None = None,
        tasks: TaskRepository | None = None,
        audit: MCPAuditRepository | None = None,
        extractor: SafeTaskCandidateExtractor | None = None,
    ) -> None:
        self._settings = settings
        self._storage = storage
        self._ocr = ocr
        self._businesses = businesses or BusinessRepository()
        self._projects = projects or ProjectRepository()
        self._documents = documents or DocumentRepository()
        self._ingestion = ingestion or IngestionRepository()
        self._tasks = tasks or TaskRepository()
        self._audit = audit or MCPAuditRepository()
        self._extractor = extractor or SafeTaskCandidateExtractor()

    async def _require_business(
        self, session: AsyncSession, principal: MCPPrincipal
    ) -> Business:
        business = await self._businesses.get_for_owner(session, principal.user_id)
        if business is None or business.id != principal.business_id:
            raise BusinessRequiredError("Business registration required")
        return business

    async def start(
        self,
        session: AsyncSession,
        principal: MCPPrincipal,
        document_id: int,
        project_id: int,
    ) -> IngestionRun:
        await self._require_business(session, principal)
        document = await self._documents.get(session, principal.business_id, document_id)
        if document is None:
            raise DocumentNotFoundError("Document not found")
        if document.status not in {DocumentStatus.AVAILABLE, DocumentStatus.DUPLICATE}:
            raise DocumentStateConflictError("Document is not ready for ingestion")
        project = await self._projects.get_active(
            session, principal.business_id, project_id
        )
        if project is None:
            raise ProjectNotFoundError("Project not found")
        active = await self._ingestion.get_active_for_document(
            session, principal.business_id, document_id
        )
        if active is not None:
            if active.project_id != project_id:
                raise IngestionConflictError(
                    "Document already has an active ingestion for another project"
                )
            return active
        run = IngestionRun(
            document_id=document_id,
            business_id=principal.business_id,
            project_id=project_id,
            requested_by_user_id=principal.user_id,
            initiated_via=ActionOrigin.MCP,
            grant_id=principal.grant_id,
            status=IngestionStatus.QUEUED,
            ocr_status=StageStatus.PENDING,
            extraction_status=StageStatus.PENDING,
            task_status=StageStatus.PENDING,
            indexing_status=StageStatus.PENDING,
            attempts=0,
            max_attempts=self._settings.ocr_max_attempts,
            next_attempt_at=datetime.now(UTC),
        )
        self._ingestion.add_run(session, run)
        await session.flush()
        self._add_event(
            session,
            run,
            action="ingestion_queued",
            outcome="queued",
            origin=ActionOrigin.MCP,
            actor_user_id=principal.user_id,
        )
        self._audit.add(
            session,
            principal=principal,
            tool_name="start_document_ingestion",
            target_type="ingestion_run",
            target_id=run.id,
            outcome="queued",
        )
        await session.commit()
        return run

    async def get_run(
        self, session: AsyncSession, principal: MCPPrincipal, run_id: int
    ) -> IngestionRun:
        await self._require_business(session, principal)
        run = await self._ingestion.get_run(session, principal.business_id, run_id)
        if run is None:
            raise IngestionNotFoundError("Ingestion run not found")
        return run

    async def list_candidates(
        self, session: AsyncSession, principal: MCPPrincipal, run_id: int
    ) -> tuple[IngestionRun, list[TaskCandidate]]:
        run = await self.get_run(session, principal, run_id)
        candidates = await self._ingestion.list_candidates(
            session, principal.business_id, run_id
        )
        return run, candidates

    async def confirm_candidates(
        self,
        session: AsyncSession,
        principal: MCPPrincipal,
        run_id: int,
        approved_ids: list[int],
        rejected_ids: list[int],
    ) -> IngestionRun:
        run, candidates = await self.list_candidates(session, principal, run_id)
        if run.status is not IngestionStatus.AWAITING_CONFIRMATION:
            raise IngestionConflictError("Ingestion is not awaiting confirmation")
        pending = {item.id: item for item in candidates if item.status is CandidateStatus.PENDING}
        decisions = set(approved_ids) | set(rejected_ids)
        if decisions != set(pending):
            raise IngestionConflictError(
                "Every pending candidate must be explicitly approved or rejected"
            )
        for candidate_id in approved_ids:
            pending[candidate_id].status = CandidateStatus.APPROVED
        for candidate_id in rejected_ids:
            pending[candidate_id].status = CandidateStatus.REJECTED
        run.status = IngestionStatus.QUEUED
        run.task_status = StageStatus.PENDING
        run.next_attempt_at = datetime.now(UTC)
        run.locked_at = None
        run.worker_id = None
        self._add_event(
            session,
            run,
            action="candidates_confirmed",
            outcome="queued",
            origin=ActionOrigin.MCP,
            actor_user_id=principal.user_id,
            details={
                "approved_count": len(approved_ids),
                "rejected_count": len(rejected_ids),
            },
        )
        self._audit.add(
            session,
            principal=principal,
            tool_name="confirm_task_candidates",
            target_type="ingestion_run",
            target_id=run.id,
            outcome="confirmed",
        )
        await session.commit()
        return run

    async def retry(
        self, session: AsyncSession, principal: MCPPrincipal, run_id: int
    ) -> IngestionRun:
        run = await self.get_run(session, principal, run_id)
        if run.status not in {
            IngestionStatus.FAILED,
            IngestionStatus.PARTIAL_FAILURE,
            IngestionStatus.RETRY_SCHEDULED,
        }:
            raise IngestionConflictError("Ingestion is not retryable")
        run.status = IngestionStatus.QUEUED
        run.attempts = 0
        run.next_attempt_at = datetime.now(UTC)
        run.locked_at = None
        run.worker_id = None
        candidates = await self._ingestion.list_candidates(
            session, principal.business_id, run.id
        )
        for candidate in candidates:
            if candidate.status is CandidateStatus.FAILED:
                candidate.status = CandidateStatus.APPROVED
                candidate.failure_message = None
        if run.task_status is StageStatus.FAILED:
            run.task_status = StageStatus.PENDING
            run.indexing_status = StageStatus.PENDING
        self._add_event(
            session,
            run,
            action="ingestion_retried",
            outcome="queued",
            origin=ActionOrigin.MCP,
            actor_user_id=principal.user_id,
        )
        await session.commit()
        return run

    async def process_claimed(self, session: AsyncSession, run: IngestionRun) -> None:
        try:
            if run.ocr_status is not StageStatus.COMPLETED:
                await self._run_ocr(session, run)
            if run.extraction_status is not StageStatus.COMPLETED:
                await self._run_extraction(session, run)
                run.status = IngestionStatus.AWAITING_CONFIRMATION
                run.locked_at = None
                run.worker_id = None
                await session.commit()
                return
            if run.task_status is not StageStatus.COMPLETED:
                await self._create_confirmed_tasks(session, run)
            if run.indexing_status is not StageStatus.COMPLETED:
                await self._index_content(session, run)
            has_candidate_failure = any(
                candidate.status is CandidateStatus.FAILED
                for candidate in await self._ingestion.list_candidates(
                    session, run.business_id, run.id
                )
            )
            run.status = (
                IngestionStatus.PARTIAL_FAILURE
                if has_candidate_failure
                else IngestionStatus.COMPLETED
            )
            run.completed_at = datetime.now(UTC)
            run.locked_at = None
            self._add_event(
                session,
                run,
                action="ingestion_finished",
                outcome=run.status.value,
                origin=ActionOrigin.WORKER,
            )
            run.worker_id = None
            await session.commit()
        except Exception as error:
            await self._record_worker_failure(session, run, error)

    async def _run_ocr(self, session: AsyncSession, run: IngestionRun) -> None:
        run.ocr_status = StageStatus.RUNNING
        await session.commit()
        document = await self._documents.get(session, run.business_id, run.document_id)
        if document is None or document.storage_key is None:
            raise DocumentNotFoundError("Document raw object is unavailable")
        with tempfile.TemporaryDirectory(prefix="projectbridge-ocr-") as temp_dir:
            suffix = Path(document.original_filename).suffix.lower()
            path = Path(temp_dir) / f"source{suffix}"
            await self._storage.download_to_path(
                document.storage_key, path, self._settings.document_max_bytes
            )
            result = await self._ocr.extract(path)
        existing = await self._ingestion.get_text(
            session, run.business_id, run.document_id, run.id
        )
        if existing is None:
            existing = DocumentText(
                document_id=run.document_id,
                business_id=run.business_id,
                ingestion_run_id=run.id,
                text=result.text,
                engine=result.engine,
                engine_version=result.engine_version,
                model=result.model,
                language=result.language,
                page_count=result.page_count,
                average_confidence=result.average_confidence,
                status=StageStatus.COMPLETED,
                created_via=ActionOrigin.WORKER,
            )
            self._ingestion.add_text(session, existing)
        else:
            existing.text = result.text
            existing.engine = result.engine
            existing.engine_version = result.engine_version
            existing.model = result.model
            existing.language = result.language
            existing.page_count = result.page_count
            existing.average_confidence = result.average_confidence
            existing.status = StageStatus.COMPLETED
        run.ocr_status = StageStatus.COMPLETED
        run.last_error_stage = None
        self._add_event(
            session,
            run,
            action="ocr_completed",
            stage="ocr",
            outcome="completed",
            origin=ActionOrigin.WORKER,
            details={
                "engine": result.engine,
                "engine_version": result.engine_version,
                "model": result.model,
            },
        )
        await session.commit()

    async def _run_extraction(self, session: AsyncSession, run: IngestionRun) -> None:
        run.extraction_status = StageStatus.RUNNING
        await session.commit()
        text = await self._ingestion.get_text(
            session, run.business_id, run.document_id, run.id
        )
        if text is None:
            raise RuntimeError("OCR text is missing")
        existing = await self._ingestion.list_candidates(session, run.business_id, run.id)
        if not existing:
            for extracted in self._extractor.extract(text.text):
                self._ingestion.add_candidate(
                    session,
                    TaskCandidate(
                        ingestion_run_id=run.id,
                        document_id=run.document_id,
                        source_text_id=text.id,
                        business_id=run.business_id,
                        project_id=run.project_id,
                        title=extracted.title,
                        source_excerpt=extracted.source_excerpt,
                        source_line_start=extracted.source_line_start,
                        source_line_end=extracted.source_line_end,
                        confidence=extracted.confidence,
                        extractor=self._extractor.name,
                        extractor_version=self._extractor.version,
                        extracted_via=ActionOrigin.WORKER,
                        status=CandidateStatus.PENDING,
                    ),
                )
        run.extraction_status = StageStatus.COMPLETED
        self._add_event(
            session,
            run,
            action="extraction_completed",
            stage="extraction",
            outcome="completed",
            origin=ActionOrigin.WORKER,
        )
        await session.commit()

    async def _create_confirmed_tasks(
        self, session: AsyncSession, run: IngestionRun
    ) -> None:
        run.task_status = StageStatus.RUNNING
        await session.commit()
        candidates = await self._ingestion.list_candidates(
            session, run.business_id, run.id
        )
        had_failure = False
        for candidate in candidates:
            if candidate.status is not CandidateStatus.APPROVED:
                continue
            try:
                # A failed insert must not poison the outer transaction or prevent
                # independent candidates from being created and checkpointed.
                async with session.begin_nested():
                    existing = await self._ingestion.get_task_for_candidate(
                        session, candidate.id
                    )
                    if isinstance(existing, Task):
                        candidate.created_task_id = existing.id
                        candidate.status = CandidateStatus.CREATED
                    else:
                        task = Task(
                            title=candidate.title,
                            description=candidate.description,
                            project_id=run.project_id,
                            status=TaskStatus.TODO,
                            priority=TaskPriority.MEDIUM,
                            created_by=TaskSource.WORKER,
                            source_document_id=run.document_id,
                            source_candidate_id=candidate.id,
                        )
                        self._tasks.add(session, task)
                        await session.flush()
                        candidate.created_task_id = task.id
                        candidate.status = CandidateStatus.CREATED
            except Exception as error:
                had_failure = True
                candidate.status = CandidateStatus.FAILED
                candidate.failure_message = "Task creation failed"
                run.last_error_message = str(error)[:500]
        run.task_status = StageStatus.FAILED if had_failure else StageStatus.COMPLETED
        self._add_event(
            session,
            run,
            action="task_creation_finished",
            stage="task_creation",
            outcome=run.task_status.value,
            origin=ActionOrigin.WORKER,
        )
        await session.commit()

    async def _index_content(self, session: AsyncSession, run: IngestionRun) -> None:
        run.indexing_status = StageStatus.RUNNING
        await session.commit()
        text = await self._ingestion.get_text(
            session, run.business_id, run.document_id, run.id
        )
        if text is None:
            raise RuntimeError("OCR text is missing")
        candidates = await self._ingestion.list_candidates(
            session, run.business_id, run.id
        )
        confirmed_titles = "\n".join(
            f"Confirmed task: {candidate.title}"
            for candidate in candidates
            if candidate.status is CandidateStatus.CREATED
        )
        content = f"{text.text}\n\n{confirmed_titles}" if confirmed_titles else text.text
        await self._ingestion.replace_chunks(
            session,
            business_id=run.business_id,
            project_id=run.project_id,
            document_id=run.document_id,
            chunks=chunk_untrusted_text(content),
        )
        run.indexing_status = StageStatus.COMPLETED
        self._add_event(
            session,
            run,
            action="indexing_completed",
            stage="indexing",
            outcome="completed",
            origin=ActionOrigin.WORKER,
        )
        await session.commit()

    async def _record_worker_failure(
        self, session: AsyncSession, run: IngestionRun, error: Exception
    ) -> None:
        stage_name, stage = self._current_stage(run)
        setattr(run, stage, StageStatus.FAILED)
        run.last_error_stage = stage_name
        run.last_error_code = type(error).__name__
        run.last_error_message = str(error)[:500] or "Ingestion stage failed"
        run.locked_at = None
        if run.attempts < run.max_attempts:
            run.status = IngestionStatus.RETRY_SCHEDULED
            run.next_attempt_at = datetime.now(UTC) + timedelta(
                seconds=min(300, 2 ** run.attempts)
            )
        else:
            completed_any = any(
                value is StageStatus.COMPLETED
                for value in (
                    run.ocr_status,
                    run.extraction_status,
                    run.task_status,
                    run.indexing_status,
                )
            )
            run.status = (
                IngestionStatus.PARTIAL_FAILURE
                if completed_any
                else IngestionStatus.FAILED
            )
        self._add_event(
            session,
            run,
            action="stage_failed",
            stage=stage_name,
            outcome=run.status.value,
            origin=ActionOrigin.WORKER,
            details={"error_code": run.last_error_code},
        )
        run.worker_id = None
        await session.commit()

    def _add_event(
        self,
        session: AsyncSession,
        run: IngestionRun,
        *,
        action: str,
        outcome: str,
        origin: ActionOrigin,
        actor_user_id: int | None = None,
        stage: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        self._ingestion.add_event(
            session,
            IngestionEvent(
                ingestion_run_id=run.id,
                business_id=run.business_id,
                actor_user_id=actor_user_id,
                origin=origin,
                action=action,
                stage=stage,
                outcome=outcome,
                worker_id=run.worker_id if origin is ActionOrigin.WORKER else None,
                details=details,
            ),
        )

    @staticmethod
    def _current_stage(run: IngestionRun) -> tuple[str, str]:
        for name, attribute in (
            ("ocr", "ocr_status"),
            ("extraction", "extraction_status"),
            ("task_creation", "task_status"),
            ("indexing", "indexing_status"),
        ):
            if getattr(run, attribute) is StageStatus.RUNNING:
                return name, attribute
        return "unknown", "ocr_status"
