from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.config import get_settings
from app.core.managers.documents import (
    DocumentNotFoundError,
    DocumentStateConflictError,
)
from app.core.managers.projects import BusinessRequiredError, ProjectNotFoundError
from app.core.services.document_storage import DocumentStorageError
from app.core.services.document_validation import DocumentValidationError
from app.core.services.mcp_mutations import (
    IdempotencyConflictError,
    IdempotencyInProgressError,
    MutationVersionConflictError,
)
from app.deps import DocumentManagerDep, SessionDep, WebPrincipalDep
from app.models import DocumentStatus
from app.schemas.document import (
    ArchiveDocumentRequest,
    ArchiveDocumentResult,
    DocumentDownloadResult,
    DocumentListResult,
    DocumentSummary,
    FinalizeDocumentUploadResult,
    InitiateDocumentUploadInput,
    InitiateDocumentUploadResult,
    UploadTarget,
)

router = APIRouter()
DocumentId = Annotated[int, Path(gt=0)]


def _raise_http_error(error: Exception) -> None:
    if isinstance(error, (DocumentNotFoundError, ProjectNotFoundError)):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(error, BusinessRequiredError):
        code = status.HTTP_403_FORBIDDEN
    elif isinstance(
        error,
        (
            DocumentStateConflictError,
            IdempotencyConflictError,
            IdempotencyInProgressError,
            MutationVersionConflictError,
        ),
    ):
        code = status.HTTP_409_CONFLICT
    elif isinstance(error, DocumentValidationError):
        code = status.HTTP_422_UNPROCESSABLE_ENTITY
    elif isinstance(error, DocumentStorageError):
        code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        raise error
    raise HTTPException(status_code=code, detail=str(error)) from error


@router.post(
    "/uploads",
    response_model=InitiateDocumentUploadResult,
    status_code=status.HTTP_201_CREATED,
)
async def initiate_upload(
    data: InitiateDocumentUploadInput,
    session: SessionDep,
    principal: WebPrincipalDep,
    manager: DocumentManagerDep,
) -> InitiateDocumentUploadResult:
    try:
        document, upload = await manager.initiate_upload(session, principal, data)
    except Exception as error:
        _raise_http_error(error)
    return InitiateDocumentUploadResult(
        document=DocumentSummary.model_validate(document),
        upload=UploadTarget(
            url=upload.url,
            fields=upload.fields,
            expires_in=upload.expires_in,
        ),
    )


@router.get("", response_model=DocumentListResult)
async def list_documents(
    session: SessionDep,
    principal: WebPrincipalDep,
    manager: DocumentManagerDep,
    project_id: Annotated[int | None, Query(gt=0)] = None,
    document_status: Annotated[
        DocumentStatus | None, Query(alias="status")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DocumentListResult:
    try:
        documents, total = await manager.list_documents(
            session,
            principal,
            project_id=project_id,
            status=document_status,
            limit=limit,
            offset=offset,
        )
    except Exception as error:
        _raise_http_error(error)
    return DocumentListResult(
        documents=[DocumentSummary.model_validate(item) for item in documents],
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(documents) < total,
    )


@router.get("/{document_id}", response_model=DocumentSummary)
async def get_document(
    document_id: DocumentId,
    session: SessionDep,
    principal: WebPrincipalDep,
    manager: DocumentManagerDep,
) -> DocumentSummary:
    try:
        document = await manager.get_document(session, principal, document_id)
    except Exception as error:
        _raise_http_error(error)
    return DocumentSummary.model_validate(document)


@router.post(
    "/{document_id}/finalize", response_model=FinalizeDocumentUploadResult
)
async def finalize_upload(
    document_id: DocumentId,
    session: SessionDep,
    principal: WebPrincipalDep,
    manager: DocumentManagerDep,
) -> FinalizeDocumentUploadResult:
    try:
        document, replayed = await manager.finalize_upload(
            session, principal, document_id
        )
    except Exception as error:
        _raise_http_error(error)
    return FinalizeDocumentUploadResult(
        document=DocumentSummary.model_validate(document), replayed=replayed
    )


@router.get("/{document_id}/download-url", response_model=DocumentDownloadResult)
async def create_download_url(
    document_id: DocumentId,
    session: SessionDep,
    principal: WebPrincipalDep,
    manager: DocumentManagerDep,
) -> DocumentDownloadResult:
    try:
        url = await manager.create_download_url(session, principal, document_id)
    except Exception as error:
        _raise_http_error(error)
    return DocumentDownloadResult(
        document_id=document_id,
        url=url,
        expires_in=get_settings().s3_presign_expiry_seconds,
    )


@router.delete("/{document_id}", response_model=ArchiveDocumentResult)
async def archive_document(
    document_id: DocumentId,
    data: ArchiveDocumentRequest,
    session: SessionDep,
    principal: WebPrincipalDep,
    manager: DocumentManagerDep,
) -> ArchiveDocumentResult:
    try:
        replayed = await manager.archive_document(
            session,
            principal,
            document_id,
            data.expected_version,
            data.idempotency_key,
        )
    except Exception as error:
        _raise_http_error(error)
    return ArchiveDocumentResult(
        document_id=document_id, archived=True, replayed=replayed
    )
