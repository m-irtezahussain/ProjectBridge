from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.managers.documents import DocumentNotFoundError
from app.core.managers.projects import BusinessRequiredError, ProjectNotFoundError
from app.core.managers.tasks import TaskNotFoundError
from app.core.services.mcp_auth import MCPPrincipal
from app.core.services.resource_cursor import ResourceCursorCodec
from app.models import Business, Document, Project, Task
from app.repositories.businesses import BusinessRepository
from app.repositories.documents import DocumentRepository
from app.repositories.projects import ProjectRepository
from app.repositories.tasks import TaskRepository


@dataclass(frozen=True)
class ResourcePage[ResourceItem]:
    items: list[ResourceItem]
    next_cursor: str | None


class ContextResourceManager:
    """Tenant-safe reads for compact MCP context resources."""

    def __init__(
        self,
        cursors: ResourceCursorCodec,
        businesses: BusinessRepository | None = None,
        projects: ProjectRepository | None = None,
        tasks: TaskRepository | None = None,
        documents: DocumentRepository | None = None,
    ) -> None:
        self._cursors = cursors
        self._businesses = businesses or BusinessRepository()
        self._projects = projects or ProjectRepository()
        self._tasks = tasks or TaskRepository()
        self._documents = documents or DocumentRepository()

    async def _require_business(
        self, session: AsyncSession, principal: MCPPrincipal
    ) -> Business:
        business = await self._businesses.get_for_owner(session, principal.user_id)
        if business is None or business.id != principal.business_id:
            raise BusinessRequiredError("Business registration required")
        return business

    @staticmethod
    def _validate_limit(limit: int) -> None:
        if limit < 1 or limit > 100:
            raise ValueError("Resource page limit must be between 1 and 100")

    async def get_project(
        self, session: AsyncSession, principal: MCPPrincipal, project_id: int
    ) -> Project:
        await self._require_business(session, principal)
        project = await self._projects.get_active(
            session, principal.business_id, project_id
        )
        if project is None:
            raise ProjectNotFoundError("Project not found")
        return project

    async def list_projects(
        self,
        session: AsyncSession,
        principal: MCPPrincipal,
        *,
        cursor: str | None,
        limit: int,
    ) -> ResourcePage[Project]:
        await self._require_business(session, principal)
        self._validate_limit(limit)
        decoded = self._cursors.decode(
            cursor,
            kind="projects",
            business_id=principal.business_id,
            parent_id=None,
        )
        rows = await self._projects.list_active_before_id(
            session,
            principal.business_id,
            before_id=decoded.last_id if decoded else None,
            limit=limit + 1,
        )
        return self._page(
            rows,
            limit=limit,
            kind="projects",
            business_id=principal.business_id,
            parent_id=None,
            get_id=lambda item: item.id,
        )

    async def get_task(
        self,
        session: AsyncSession,
        principal: MCPPrincipal,
        project_id: int,
        task_id: int,
    ) -> Task:
        await self.get_project(session, principal, project_id)
        task = await self._tasks.get_active(
            session, principal.business_id, project_id, task_id
        )
        if task is None:
            raise TaskNotFoundError("Task not found")
        return task

    async def list_tasks(
        self,
        session: AsyncSession,
        principal: MCPPrincipal,
        project_id: int,
        *,
        cursor: str | None,
        limit: int,
    ) -> ResourcePage[Task]:
        await self.get_project(session, principal, project_id)
        self._validate_limit(limit)
        decoded = self._cursors.decode(
            cursor,
            kind="tasks",
            business_id=principal.business_id,
            parent_id=project_id,
        )
        rows = await self._tasks.list_active_before_id(
            session,
            principal.business_id,
            project_id,
            before_id=decoded.last_id if decoded else None,
            limit=limit + 1,
        )
        return self._page(
            rows,
            limit=limit,
            kind="tasks",
            business_id=principal.business_id,
            parent_id=project_id,
            get_id=lambda item: item.id,
        )

    async def get_document(
        self, session: AsyncSession, principal: MCPPrincipal, document_id: int
    ) -> Document:
        await self._require_business(session, principal)
        document = await self._documents.get(
            session, principal.business_id, document_id
        )
        if document is None:
            raise DocumentNotFoundError("Document not found")
        return document

    async def list_documents(
        self,
        session: AsyncSession,
        principal: MCPPrincipal,
        *,
        project_id: int | None,
        cursor: str | None,
        limit: int,
    ) -> ResourcePage[Document]:
        await self._require_business(session, principal)
        if project_id is not None:
            await self.get_project(session, principal, project_id)
        self._validate_limit(limit)
        decoded = self._cursors.decode(
            cursor,
            kind="documents",
            business_id=principal.business_id,
            parent_id=project_id,
        )
        rows = await self._documents.list_before_id(
            session,
            principal.business_id,
            project_id=project_id,
            before_id=decoded.last_id if decoded else None,
            limit=limit + 1,
        )
        return self._page(
            rows,
            limit=limit,
            kind="documents",
            business_id=principal.business_id,
            parent_id=project_id,
            get_id=lambda item: item.id,
        )

    def _page[ResourceItem](
        self,
        rows: list[ResourceItem],
        *,
        limit: int,
        kind: str,
        business_id: int,
        parent_id: int | None,
        get_id: Callable[[ResourceItem], int],
    ) -> ResourcePage[ResourceItem]:
        items = rows[:limit]
        next_cursor = None
        if len(rows) > limit and items:
            last_id = get_id(items[-1])
            if not isinstance(last_id, int):
                raise RuntimeError("Resource record has no stable integer ID")
            next_cursor = self._cursors.encode(
                kind=kind,
                business_id=business_id,
                parent_id=parent_id,
                last_id=last_id,
            )
        return ResourcePage(items=items, next_cursor=next_cursor)
