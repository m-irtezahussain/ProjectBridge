from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.managers.search import KnowledgeSearchHit, ProjectIndexState
from app.core.services.document_storage import PresignedPost
from app.core.services.mcp_auth import AuthenticatedPrincipal
from app.core.services.mcp_mutations import MCPMutationResult
from app.db import get_session
from app.deps import (
    get_document_manager,
    get_ingestion_manager,
    get_semantic_search_manager,
    get_web_principal,
)
from app.main import create_app
from app.models import (
    ActionOrigin,
    CandidateStatus,
    Document,
    DocumentStatus,
    IngestionRun,
    IngestionStatus,
    SearchIndexJob,
    SearchJobOperation,
    SearchJobStatus,
    StageStatus,
    TaskCandidate,
)

NOW = datetime(2026, 11, 27, tzinfo=UTC)
PRINCIPAL = AuthenticatedPrincipal(
    user_id=3,
    business_id=7,
    scopes=frozenset(),
    grant_id="rest:3",
    origin=ActionOrigin.REST,
)


async def fake_session() -> AsyncIterator[object]:
    yield object()


def make_document() -> Document:
    return Document(
        id=11,
        business_id=7,
        project_id=5,
        uploaded_by_user_id=3,
        created_via=ActionOrigin.REST,
        original_filename="scope.pdf",
        declared_mime_type="application/pdf",
        detected_mime_type="application/pdf",
        declared_size=128,
        size_bytes=128,
        content_sha256="a" * 64,
        quarantine_key="businesses/7/quarantine/example",
        storage_key="businesses/7/raw/example",
        status=DocumentStatus.AVAILABLE,
        failure_code=None,
        failure_message=None,
        duplicate_of_document_id=None,
        upload_expires_at=NOW,
        created_at=NOW,
        updated_at=NOW,
        archived_at=None,
        version=1,
    )


def make_ingestion() -> IngestionRun:
    return IngestionRun(
        id=13,
        document_id=11,
        business_id=7,
        project_id=5,
        requested_by_user_id=3,
        initiated_via=ActionOrigin.REST,
        grant_id="rest:3",
        status=IngestionStatus.AWAITING_CONFIRMATION,
        ocr_status=StageStatus.COMPLETED,
        extraction_status=StageStatus.COMPLETED,
        task_status=StageStatus.PENDING,
        indexing_status=StageStatus.PENDING,
        attempts=1,
        max_attempts=5,
        next_attempt_at=NOW,
        last_error_stage=None,
        last_error_code=None,
        last_error_message=None,
        completed_at=None,
        version=2,
    )


class FakeDocumentManager:
    def __init__(self) -> None:
        self.document = make_document()

    async def initiate_upload(self, *_args: object) -> tuple[Document, PresignedPost]:
        return self.document, PresignedPost("https://storage.test/upload", {"key": "x"}, 300)

    async def list_documents(self, *_args: object, **_kwargs: object) -> tuple[list[Document], int]:
        return [self.document], 1

    async def get_document(self, *_args: object) -> Document:
        return self.document

    async def finalize_upload(self, *_args: object) -> tuple[Document, bool]:
        return self.document, False

    async def create_download_url(self, *_args: object) -> str:
        return "https://storage.test/download"

    async def archive_document(self, *_args: object) -> bool:
        return False


class FakeIngestionManager:
    def __init__(self) -> None:
        self.run = make_ingestion()
        self.candidate = TaskCandidate(
            id=17,
            ingestion_run_id=13,
            document_id=11,
            source_text_id=19,
            business_id=7,
            project_id=5,
            title="Confirm launch date",
            dedupe_key="b" * 64,
            description=None,
            source_excerpt="Confirm launch date with the client.",
            page_number=1,
            source_line_start=4,
            source_line_end=4,
            confidence=0.9,
            extractor="safe-rules",
            extractor_version="1",
            extracted_via=ActionOrigin.WORKER,
            status=CandidateStatus.PENDING,
            created_task_id=None,
            failure_message=None,
        )

    async def start(self, *_args: object) -> MCPMutationResult[IngestionRun]:
        return MCPMutationResult(entity=self.run, replayed=False)

    async def get_run(self, *_args: object) -> IngestionRun:
        return self.run

    async def get_latest_for_document(self, *_args: object) -> IngestionRun:
        return self.run

    async def list_candidates(self, *_args: object) -> tuple[IngestionRun, list[TaskCandidate]]:
        return self.run, [self.candidate]

    async def confirm_candidates(self, *_args: object) -> MCPMutationResult[IngestionRun]:
        return MCPMutationResult(entity=self.run, replayed=False)

    async def retry(self, *_args: object) -> MCPMutationResult[IngestionRun]:
        return MCPMutationResult(entity=self.run, replayed=False)


class FakeSearchManager:
    def __init__(self) -> None:
        self.job = SearchIndexJob(
            id=23,
            business_id=7,
            project_id=5,
            operation=SearchJobOperation.REINDEX_PROJECT,
            status=SearchJobStatus.QUEUED,
            attempts=0,
            max_attempts=5,
            next_attempt_at=NOW,
            error_code=None,
            error_message=None,
            created_at=NOW,
            updated_at=NOW,
            completed_at=None,
        )

    async def search(self, *_args: object, **_kwargs: object) -> list[KnowledgeSearchHit]:
        return [
            KnowledgeSearchHit(
                excerpt="Untrusted source excerpt",
                distance=0.12,
                source_type="document",
                project_id=5,
                document_id=11,
                task_id=None,
                chunk_id=29,
                source_text_id=19,
                ingestion_run_id=13,
            )
        ]

    async def enqueue_project_reindex(self, *_args: object) -> SearchIndexJob:
        return self.job

    async def get_index_job(self, *_args: object) -> SearchIndexJob:
        return self.job

    async def get_project_index_state(self, *_args: object) -> ProjectIndexState:
        return ProjectIndexState(5, "queued", 1, None, None)


def configure_app(
    manager_dependency: Callable[..., Any], manager: object
) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_session] = fake_session
    app.dependency_overrides[get_web_principal] = lambda: PRINCIPAL
    app.dependency_overrides[manager_dependency] = lambda: manager
    return app


async def test_document_rest_contract() -> None:
    app = configure_app(get_document_manager, FakeDocumentManager())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        initiated = await client.post(
            "/api/v1/documents/uploads",
            json={
                "filename": "scope.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 128,
                "project_id": 5,
            },
        )
        listed = await client.get("/api/v1/documents?project_id=5&limit=10")
        finalized = await client.post("/api/v1/documents/11/finalize")
        downloaded = await client.get("/api/v1/documents/11/download-url")
        archived = await client.request(
            "DELETE",
            "/api/v1/documents/11",
            json={"expected_version": 1, "idempotency_key": "archive-11"},
        )

    assert initiated.status_code == 201
    assert initiated.json()["document"]["created_via"] == "rest"
    assert initiated.json()["upload"]["url"] == "https://storage.test/upload"
    assert listed.json()["has_more"] is False
    assert finalized.json()["replayed"] is False
    assert downloaded.json()["url"] == "https://storage.test/download"
    assert archived.json() == {"document_id": 11, "archived": True, "replayed": False}


async def test_ingestion_rest_contract() -> None:
    app = configure_app(get_ingestion_manager, FakeIngestionManager())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        started = await client.post(
            "/api/v1/ingestions",
            json={"document_id": 11, "project_id": 5, "idempotency_key": "start-11"},
        )
        latest = await client.get("/api/v1/documents/11/ingestion")
        candidates = await client.get("/api/v1/ingestions/13/candidates")
        confirmed = await client.post(
            "/api/v1/ingestions/13/candidates/confirm",
            json={
                "approved_candidate_ids": [17],
                "rejected_candidate_ids": [],
                "expected_version": 2,
                "idempotency_key": "confirm-13",
            },
        )

    assert started.status_code == 201
    assert latest.json()["id"] == 13
    assert candidates.json()["candidates"][0]["source_excerpt"].startswith("Confirm")
    assert confirmed.status_code == 200


async def test_search_rest_contract_marks_results_untrusted() -> None:
    app = configure_app(get_semantic_search_manager, FakeSearchManager())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        searched = await client.post(
            "/api/v1/search", json={"query": "launch", "project_id": 5}
        )
        reindexed = await client.post("/api/v1/search/projects/5/reindex")
        job = await client.get("/api/v1/search/jobs/23")
        state = await client.get("/api/v1/search/projects/5/index-state")

    assert searched.status_code == 200
    assert searched.json()["results"][0]["untrusted_content"] is True
    assert "untrusted" in searched.json()["untrusted_content_notice"].lower()
    assert reindexed.status_code == 202
    assert job.json()["status"] == "queued"
    assert state.json()["pending_jobs"] == 1


async def test_web_knowledge_routes_require_authentication() -> None:
    app = create_app()
    app.dependency_overrides[get_session] = fake_session
    app.dependency_overrides[get_document_manager] = lambda: FakeDocumentManager()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/documents")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"
