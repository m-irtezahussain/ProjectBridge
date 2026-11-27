from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status

from app.core.managers.documents import (
    DocumentNotFoundError,
    DocumentStateConflictError,
)
from app.core.managers.ingestion import (
    IngestionConflictError,
    IngestionNotFoundError,
)
from app.core.managers.projects import BusinessRequiredError, ProjectNotFoundError
from app.core.services.mcp_mutations import (
    IdempotencyConflictError,
    IdempotencyInProgressError,
    MutationVersionConflictError,
)
from app.deps import IngestionManagerDep, SessionDep, WebPrincipalDep
from app.schemas.ingestion import (
    CandidateListResult,
    ConfirmCandidatesRequest,
    IngestionRunSummary,
    RetryIngestionRequest,
    StartIngestionInput,
    TaskCandidateSummary,
)

router = APIRouter()
document_router = APIRouter()
IngestionId = Annotated[int, Path(gt=0)]
DocumentId = Annotated[int, Path(gt=0)]


def _raise_http_error(error: Exception) -> None:
    if isinstance(
        error,
        (DocumentNotFoundError, IngestionNotFoundError, ProjectNotFoundError),
    ):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(error, BusinessRequiredError):
        code = status.HTTP_403_FORBIDDEN
    elif isinstance(
        error,
        (
            DocumentStateConflictError,
            IngestionConflictError,
            IdempotencyConflictError,
            IdempotencyInProgressError,
            MutationVersionConflictError,
        ),
    ):
        code = status.HTTP_409_CONFLICT
    else:
        raise error
    raise HTTPException(status_code=code, detail=str(error)) from error


@router.post("", response_model=IngestionRunSummary, status_code=status.HTTP_201_CREATED)
async def start_ingestion(
    data: StartIngestionInput,
    session: SessionDep,
    principal: WebPrincipalDep,
    manager: IngestionManagerDep,
) -> IngestionRunSummary:
    try:
        result = await manager.start(
            session,
            principal,
            data.document_id,
            data.project_id,
            data.idempotency_key,
        )
    except Exception as error:
        _raise_http_error(error)
    return IngestionRunSummary.model_validate(result.entity)


@router.get("/{ingestion_id}", response_model=IngestionRunSummary)
async def get_ingestion(
    ingestion_id: IngestionId,
    session: SessionDep,
    principal: WebPrincipalDep,
    manager: IngestionManagerDep,
) -> IngestionRunSummary:
    try:
        run = await manager.get_run(session, principal, ingestion_id)
    except Exception as error:
        _raise_http_error(error)
    return IngestionRunSummary.model_validate(run)


@router.get("/{ingestion_id}/candidates", response_model=CandidateListResult)
async def list_candidates(
    ingestion_id: IngestionId,
    session: SessionDep,
    principal: WebPrincipalDep,
    manager: IngestionManagerDep,
) -> CandidateListResult:
    try:
        run, candidates = await manager.list_candidates(
            session, principal, ingestion_id
        )
    except Exception as error:
        _raise_http_error(error)
    return CandidateListResult(
        ingestion=IngestionRunSummary.model_validate(run),
        candidates=[TaskCandidateSummary.model_validate(item) for item in candidates],
    )


@router.post(
    "/{ingestion_id}/candidates/confirm", response_model=IngestionRunSummary
)
async def confirm_candidates(
    ingestion_id: IngestionId,
    data: ConfirmCandidatesRequest,
    session: SessionDep,
    principal: WebPrincipalDep,
    manager: IngestionManagerDep,
) -> IngestionRunSummary:
    try:
        result = await manager.confirm_candidates(
            session,
            principal,
            ingestion_id,
            data.approved_candidate_ids,
            data.rejected_candidate_ids,
            data.expected_version,
            data.idempotency_key,
        )
    except Exception as error:
        _raise_http_error(error)
    return IngestionRunSummary.model_validate(result.entity)


@router.post("/{ingestion_id}/retry", response_model=IngestionRunSummary)
async def retry_ingestion(
    ingestion_id: IngestionId,
    data: RetryIngestionRequest,
    session: SessionDep,
    principal: WebPrincipalDep,
    manager: IngestionManagerDep,
) -> IngestionRunSummary:
    try:
        result = await manager.retry(
            session,
            principal,
            ingestion_id,
            data.expected_version,
            data.idempotency_key,
        )
    except Exception as error:
        _raise_http_error(error)
    return IngestionRunSummary.model_validate(result.entity)


@document_router.get(
    "/documents/{document_id}/ingestion", response_model=IngestionRunSummary
)
async def get_latest_document_ingestion(
    document_id: DocumentId,
    session: SessionDep,
    principal: WebPrincipalDep,
    manager: IngestionManagerDep,
) -> IngestionRunSummary:
    try:
        run = await manager.get_latest_for_document(session, principal, document_id)
    except Exception as error:
        _raise_http_error(error)
    return IngestionRunSummary.model_validate(run)
