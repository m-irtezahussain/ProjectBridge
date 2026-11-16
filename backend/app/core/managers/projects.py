from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.managers.auth import AuthenticationError, AuthManager
from app.models import Business, Project
from app.repositories.businesses import BusinessRepository
from app.repositories.projects import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate


class BusinessRequiredError(ValueError):
    pass


class ProjectNotFoundError(ValueError):
    pass


class ProjectManager:
    """Shared tenant-safe project rules for REST and future MCP tools."""

    def __init__(
        self,
        auth: AuthManager,
        businesses: BusinessRepository | None = None,
        projects: ProjectRepository | None = None,
    ) -> None:
        self._auth = auth
        self._businesses = businesses or BusinessRepository()
        self._projects = projects or ProjectRepository()

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

    async def list_projects(
        self, session: AsyncSession, access_token: str | None
    ) -> list[Project]:
        business = await self._get_business(session, access_token)
        return await self._projects.list_active(session, business.id)

    async def get_project(
        self, session: AsyncSession, access_token: str | None, project_id: int
    ) -> Project:
        business = await self._get_business(session, access_token)
        project = await self._projects.get_active(session, business.id, project_id)
        if project is None:
            raise ProjectNotFoundError("Project not found")
        return project

    async def create_project(
        self,
        session: AsyncSession,
        access_token: str | None,
        data: ProjectCreate,
    ) -> Project:
        business = await self._get_business(session, access_token)
        project = Project(
            name=data.name,
            description=data.description,
            business_id=business.id,
            status=data.status,
        )
        self._projects.add(session, project)
        await session.commit()
        return project

    async def update_project(
        self,
        session: AsyncSession,
        access_token: str | None,
        project_id: int,
        data: ProjectUpdate,
    ) -> Project:
        project = await self.get_project(session, access_token, project_id)
        if data.name is not None:
            project.name = data.name
        if data.status is not None:
            project.status = data.status
        if "description" in data.model_fields_set:
            project.description = data.description
        await session.commit()
        return project

    async def dismiss_project(
        self, session: AsyncSession, access_token: str | None, project_id: int
    ) -> None:
        project = await self.get_project(session, access_token, project_id)
        project.deleted_at = datetime.now(UTC)
        await session.commit()
