from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status

from app.core.managers.projects import BusinessRequiredError, ProjectNotFoundError
from app.core.managers.search import SearchConflictError, SearchJobNotFoundError
from app.core.services.embeddings import EmbeddingServiceError
from app.core.services.vector_store import VectorStoreError
from app.deps import SemanticSearchManagerDep, SessionDep, WebPrincipalDep
from app.schemas.search import (
    ProjectIndexStateResult,
    ProjectKnowledgeResult,
    ReindexProjectKnowledgeResult,
    SearchIndexJobResult,
    SearchProjectKnowledgeInput,
    SearchProjectKnowledgeResult,
)

router = APIRouter()
ProjectId = Annotated[int, Path(gt=0)]
JobId = Annotated[int, Path(gt=0)]


def _raise_http_error(error: Exception) -> None:
    if isinstance(error, (ProjectNotFoundError, SearchJobNotFoundError)):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(error, BusinessRequiredError):
        code = status.HTTP_403_FORBIDDEN
    elif isinstance(error, SearchConflictError):
        code = status.HTTP_409_CONFLICT
    elif isinstance(error, (EmbeddingServiceError, VectorStoreError)):
        code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        raise error
    detail = (
        "Knowledge search is temporarily unavailable"
        if code == status.HTTP_503_SERVICE_UNAVAILABLE
        else str(error)
    )
    raise HTTPException(status_code=code, detail=detail) from error


@router.post("", response_model=SearchProjectKnowledgeResult)
async def search_knowledge(
    data: SearchProjectKnowledgeInput,
    session: SessionDep,
    principal: WebPrincipalDep,
    manager: SemanticSearchManagerDep,
) -> SearchProjectKnowledgeResult:
    try:
        hits = await manager.search(
            session,
            principal,
            data.query,
            project_id=data.project_id,
            document_id=data.document_id,
            limit=data.limit,
        )
    except Exception as error:
        _raise_http_error(error)
    return SearchProjectKnowledgeResult(
        results=[ProjectKnowledgeResult.model_validate(hit.__dict__) for hit in hits]
    )


@router.post(
    "/projects/{project_id}/reindex",
    response_model=ReindexProjectKnowledgeResult,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reindex_project(
    project_id: ProjectId,
    session: SessionDep,
    principal: WebPrincipalDep,
    manager: SemanticSearchManagerDep,
) -> ReindexProjectKnowledgeResult:
    try:
        job = await manager.enqueue_project_reindex(session, principal, project_id)
    except Exception as error:
        _raise_http_error(error)
    return ReindexProjectKnowledgeResult(job_id=job.id, project_id=project_id)


@router.get("/jobs/{job_id}", response_model=SearchIndexJobResult)
async def get_index_job(
    job_id: JobId,
    session: SessionDep,
    principal: WebPrincipalDep,
    manager: SemanticSearchManagerDep,
) -> SearchIndexJobResult:
    try:
        job = await manager.get_index_job(session, principal, job_id)
    except Exception as error:
        _raise_http_error(error)
    return SearchIndexJobResult.model_validate(job)


@router.get(
    "/projects/{project_id}/index-state", response_model=ProjectIndexStateResult
)
async def get_project_index_state(
    project_id: ProjectId,
    session: SessionDep,
    principal: WebPrincipalDep,
    manager: SemanticSearchManagerDep,
) -> ProjectIndexStateResult:
    try:
        state = await manager.get_project_index_state(
            session, principal, project_id
        )
    except Exception as error:
        _raise_http_error(error)
    return ProjectIndexStateResult.model_validate(state.__dict__)
