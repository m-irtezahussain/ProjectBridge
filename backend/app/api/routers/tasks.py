from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request, Response, status

from app.api.routers.auth import ACCESS_COOKIE
from app.core.managers.auth import AuthenticationError
from app.core.managers.projects import BusinessRequiredError, ProjectNotFoundError
from app.core.managers.tasks import AssigneeNotFoundError, TaskNotFoundError
from app.deps import SessionDep, TaskManagerDep
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate

router = APIRouter()
ProjectId = Annotated[int, Path(gt=0)]
TaskId = Annotated[int, Path(gt=0)]


def _raise_http_error(error: ValueError) -> None:
    if isinstance(error, AuthenticationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)
        ) from error
    if isinstance(error, BusinessRequiredError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(error)
        ) from error
    if isinstance(error, (ProjectNotFoundError, TaskNotFoundError)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    if isinstance(error, AssigneeNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    raise error


@router.get("", response_model=list[TaskRead])
async def list_tasks(
    project_id: ProjectId,
    request: Request,
    session: SessionDep,
    manager: TaskManagerDep,
) -> list[TaskRead]:
    try:
        tasks = await manager.list_tasks(
            session, request.cookies.get(ACCESS_COOKIE), project_id
        )
    except (AuthenticationError, BusinessRequiredError, ProjectNotFoundError) as error:
        _raise_http_error(error)
    return [TaskRead.model_validate(task) for task in tasks]


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    project_id: ProjectId,
    data: TaskCreate,
    request: Request,
    session: SessionDep,
    manager: TaskManagerDep,
) -> TaskRead:
    try:
        task = await manager.create_task(
            session, request.cookies.get(ACCESS_COOKIE), project_id, data
        )
    except (
        AuthenticationError,
        BusinessRequiredError,
        ProjectNotFoundError,
        AssigneeNotFoundError,
    ) as error:
        _raise_http_error(error)
    return TaskRead.model_validate(task)


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    project_id: ProjectId,
    task_id: TaskId,
    request: Request,
    session: SessionDep,
    manager: TaskManagerDep,
) -> TaskRead:
    try:
        task = await manager.get_task(
            session, request.cookies.get(ACCESS_COOKIE), project_id, task_id
        )
    except (
        AuthenticationError,
        BusinessRequiredError,
        TaskNotFoundError,
    ) as error:
        _raise_http_error(error)
    return TaskRead.model_validate(task)


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(
    project_id: ProjectId,
    task_id: TaskId,
    data: TaskUpdate,
    request: Request,
    session: SessionDep,
    manager: TaskManagerDep,
) -> TaskRead:
    try:
        task = await manager.update_task(
            session,
            request.cookies.get(ACCESS_COOKIE),
            project_id,
            task_id,
            data,
        )
    except (
        AuthenticationError,
        BusinessRequiredError,
        TaskNotFoundError,
        AssigneeNotFoundError,
    ) as error:
        _raise_http_error(error)
    return TaskRead.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_task(
    project_id: ProjectId,
    task_id: TaskId,
    request: Request,
    session: SessionDep,
    manager: TaskManagerDep,
) -> Response:
    try:
        await manager.dismiss_task(
            session, request.cookies.get(ACCESS_COOKIE), project_id, task_id
        )
    except (
        AuthenticationError,
        BusinessRequiredError,
        TaskNotFoundError,
    ) as error:
        _raise_http_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
