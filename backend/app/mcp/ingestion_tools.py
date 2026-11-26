from typing import Annotated

from mcp.server import MCPServer
from pydantic import Field

from app.core.managers.ingestion import IngestionManager
from app.mcp.auth import MCPDatabaseSessions, require_mcp_principal
from app.mcp.tools import IDEMPOTENT_WRITE, READ_ONLY, WRITE, structured_mcp_errors
from app.schemas.ingestion import (
    CandidateListResult,
    ConfirmCandidatesInput,
    IngestionRunSummary,
    RetryIngestionInput,
    StartIngestionInput,
    TaskCandidateSummary,
)


def register_ingestion_tools(
    server: MCPServer,
    sessions: MCPDatabaseSessions,
    ingestion: IngestionManager,
) -> None:
    @server.tool(
        description=(
            "Queue OCR and safe task-candidate extraction for an available document. "
            "OCR runs in a separate durable worker and cannot execute document text."
        ),
        annotations=IDEMPOTENT_WRITE,
        structured_output=True,
    )
    async def start_document_ingestion(
        input: StartIngestionInput,
    ) -> IngestionRunSummary:
        async with structured_mcp_errors():
            principal = require_mcp_principal("documents:write", "tasks:write")
            async with sessions.session() as session:
                run = await ingestion.start(
                    session,
                    principal,
                    input.document_id,
                    input.project_id,
                    input.idempotency_key,
                )
        return IngestionRunSummary.model_validate(run.entity)

    @server.tool(
        description="Get durable OCR, extraction, task-creation, and indexing progress.",
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def get_document_ingestion(
        ingestion_run_id: Annotated[int, Field(gt=0)],
    ) -> IngestionRunSummary:
        async with structured_mcp_errors():
            principal = require_mcp_principal("documents:read")
            async with sessions.session() as session:
                run = await ingestion.get_run(session, principal, ingestion_run_id)
        return IngestionRunSummary.model_validate(run)

    @server.tool(
        description=(
            "List untrusted task proposals extracted deterministically from OCR text. "
            "No proposal has permission to trigger a tool or mutate a task."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def list_task_candidates(
        ingestion_run_id: Annotated[int, Field(gt=0)],
    ) -> CandidateListResult:
        async with structured_mcp_errors():
            principal = require_mcp_principal("documents:read", "tasks:read")
            async with sessions.session() as session:
                run, candidates = await ingestion.list_candidates(
                    session, principal, ingestion_run_id
                )
        return CandidateListResult(
            ingestion=IngestionRunSummary.model_validate(run),
            candidates=[
                TaskCandidateSummary.model_validate(candidate)
                for candidate in candidates
            ],
        )

    @server.tool(
        description=(
            "Explicitly approve or reject every pending task proposal. Only approved "
            "IDs are queued for tenant-validated task creation; document text itself "
            "is never interpreted as confirmation."
        ),
        annotations=WRITE,
        structured_output=True,
    )
    async def confirm_task_candidates(
        input: ConfirmCandidatesInput,
    ) -> IngestionRunSummary:
        async with structured_mcp_errors():
            principal = require_mcp_principal("documents:write", "tasks:write")
            async with sessions.session() as session:
                result = await ingestion.confirm_candidates(
                    session,
                    principal,
                    input.ingestion_run_id,
                    input.approved_candidate_ids,
                    input.rejected_candidate_ids,
                    input.expected_version,
                    input.idempotency_key,
                )
        return IngestionRunSummary.model_validate(result.entity)

    @server.tool(
        description=(
            "Requeue a failed or partially failed ingestion from its last durable "
            "checkpoint. Completed OCR and task effects are not duplicated."
        ),
        annotations=IDEMPOTENT_WRITE,
        structured_output=True,
    )
    async def retry_document_ingestion(
        input: RetryIngestionInput,
    ) -> IngestionRunSummary:
        async with structured_mcp_errors():
            principal = require_mcp_principal("documents:write", "tasks:write")
            async with sessions.session() as session:
                result = await ingestion.retry(
                    session,
                    principal,
                    input.ingestion_run_id,
                    input.expected_version,
                    input.idempotency_key,
                )
        return IngestionRunSummary.model_validate(result.entity)
