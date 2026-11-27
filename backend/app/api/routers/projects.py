from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path, Query, Request, Response, status

from app.api.auth_cookies import ACCESS_COOKIE
from app.core.managers.auth import AuthenticationError
from app.core.managers.projects import BusinessRequiredError, ProjectNotFoundError
from app.deps import ProjectManagerDep, SessionDep, WebPrincipalDep
from app.models import ProjectStatus
from app.schemas.project import ProjectCreate, ProjectPage, ProjectRead, ProjectUpdate

router = APIRouter()
ProjectId = Annotated[int, Path(gt=0)]


def _raise_http_error(error: ValueError) -> None:
    if isinstance(error, AuthenticationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        ) from error
    if isinstance(error, BusinessRequiredError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error
    if isinstance(error, ProjectNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    raise error


@router.get("", response_model=ProjectPage)
async def list_projects(
    session: SessionDep,
    principal: WebPrincipalDep,
    manager: ProjectManagerDep,
    project_status: Annotated[ProjectStatus | None, Query(alias="status")] = None,
    query: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 24,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort_by: Literal["id", "name", "status"] = "id",
    sort_order: Literal["asc", "desc"] = "desc",
) -> ProjectPage:
    try:
        projects, total = await manager.list_projects_page_for_principal(
            session,
            principal,
            status=project_status,
            query=query.strip() if query and query.strip() else None,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            descending=sort_order == "desc",
        )
    except BusinessRequiredError as error:
        _raise_http_error(error)
    return ProjectPage(
        projects=[ProjectRead.model_validate(project) for project in projects],
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(projects) < total,
    )


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    request: Request,
    session: SessionDep,
    manager: ProjectManagerDep,
) -> ProjectRead:
    try:
        project = await manager.create_project(
            session, request.cookies.get(ACCESS_COOKIE), data
        )
    except (AuthenticationError, BusinessRequiredError) as error:
        _raise_http_error(error)
    return ProjectRead.model_validate(project)


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: ProjectId,
    request: Request,
    session: SessionDep,
    manager: ProjectManagerDep,
) -> ProjectRead:
    try:
        project = await manager.get_project(
            session, request.cookies.get(ACCESS_COOKIE), project_id
        )
    except (AuthenticationError, BusinessRequiredError, ProjectNotFoundError) as error:
        _raise_http_error(error)
    return ProjectRead.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: ProjectId,
    data: ProjectUpdate,
    request: Request,
    session: SessionDep,
    manager: ProjectManagerDep,
) -> ProjectRead:
    try:
        project = await manager.update_project(
            session,
            request.cookies.get(ACCESS_COOKIE),
            project_id,
            data,
        )
    except (AuthenticationError, BusinessRequiredError, ProjectNotFoundError) as error:
        _raise_http_error(error)
    return ProjectRead.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_project(
    project_id: ProjectId,
    request: Request,
    session: SessionDep,
    manager: ProjectManagerDep,
) -> Response:
    try:
        await manager.dismiss_project(
            session, request.cookies.get(ACCESS_COOKIE), project_id
        )
    except (AuthenticationError, BusinessRequiredError, ProjectNotFoundError) as error:
        _raise_http_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
