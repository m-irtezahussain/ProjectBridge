from sqlalchemy.ext.asyncio import AsyncSession

from app.core.managers.auth import AuthenticationError, AuthManager
from app.core.managers.projects import BusinessRequiredError, ProjectNotFoundError
from app.models import Business, Task, TaskSource
from app.repositories.businesses import BusinessRepository
from app.repositories.projects import ProjectRepository
from app.repositories.tasks import TaskRepository
from app.schemas.task import TaskCreate, TaskUpdate


class TaskNotFoundError(ValueError):
    pass


class TaskManager:
    """Shared tenant-safe task rules for REST and MCP interfaces."""

    def __init__(
        self,
        auth: AuthManager,
        businesses: BusinessRepository | None = None,
        projects: ProjectRepository | None = None,
        tasks: TaskRepository | None = None,
    ) -> None:
        self._auth = auth
        self._businesses = businesses or BusinessRepository()
        self._projects = projects or ProjectRepository()
        self._tasks = tasks or TaskRepository()

    async def _get_business(
        self, session: AsyncSession, access_token: str | None
    ) -> Business:
        user = await self._auth.get_user(session, access_token, "access")
        if user is None:
            raise AuthenticationError("Authentication required")
        business = await self._businesses.get_for_owner(session, user.id)
        if business is None:
            raise BusinessRequiredError("Business registration required")
        return business

    async def _require_project(
        self, session: AsyncSession, business_id: int, project_id: int
    ) -> None:
        project = await self._projects.get_active(session, business_id, project_id)
        if project is None:
            raise ProjectNotFoundError("Project not found")

    async def list_tasks(
        self,
        session: AsyncSession,
        access_token: str | None,
        project_id: int,
    ) -> list[Task]:
        business = await self._get_business(session, access_token)
        await self._require_project(session, business.id, project_id)
        return await self._tasks.list_active(session, business.id, project_id)

    async def get_task(
        self,
        session: AsyncSession,
        access_token: str | None,
        project_id: int,
        task_id: int,
    ) -> Task:
        business = await self._get_business(session, access_token)
        task = await self._tasks.get_active(
            session, business.id, project_id, task_id
        )
        if task is None:
            raise TaskNotFoundError("Task not found")
        return task

    async def create_task(
        self,
        session: AsyncSession,
        access_token: str | None,
        project_id: int,
        data: TaskCreate,
        source: TaskSource = TaskSource.API,
    ) -> Task:
        business = await self._get_business(session, access_token)
        await self._require_project(session, business.id, project_id)
        task = Task(
            title=data.title,
            description=data.description,
            status=data.status,
            priority=data.priority,
            project_id=project_id,
            created_by=source,
        )
        self._tasks.add(session, task)
        await session.commit()
        return task

    async def update_task(
        self,
        session: AsyncSession,
        access_token: str | None,
        project_id: int,
        task_id: int,
        data: TaskUpdate,
    ) -> Task:
        task = await self.get_task(session, access_token, project_id, task_id)
        if data.title is not None:
            task.title = data.title
        if "description" in data.model_fields_set:
            task.description = data.description
        if data.status is not None:
            task.status = data.status
        if data.priority is not None:
            task.priority = data.priority
        await session.commit()
        return task

    async def dismiss_task(
        self,
        session: AsyncSession,
        access_token: str | None,
        project_id: int,
        task_id: int,
    ) -> None:
        task = await self.get_task(session, access_token, project_id, task_id)
        task.is_deleted = True
        await session.commit()
