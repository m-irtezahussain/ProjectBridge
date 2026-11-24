from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, ProjectStatus


class ProjectRepository:
    """Database access that always scopes projects to one business."""

    async def list_active(
        self,
        session: AsyncSession,
        business_id: int,
        status: ProjectStatus | None = None,
    ) -> list[Project]:
        statement = select(Project).where(
            Project.business_id == business_id,
            Project.deleted_at.is_(None),
        )
        if status is not None:
            statement = statement.where(Project.status == status)
        result = await session.scalars(statement.order_by(Project.id.desc()))
        return list(result.all())

    async def get_active(
        self, session: AsyncSession, business_id: int, project_id: int
    ) -> Project | None:
        return await session.scalar(
            select(Project).where(
                Project.id == project_id,
                Project.business_id == business_id,
                Project.deleted_at.is_(None),
            )
        )

    async def get_for_business(
        self, session: AsyncSession, business_id: int, project_id: int
    ) -> Project | None:
        return await session.scalar(
            select(Project).where(
                Project.id == project_id,
                Project.business_id == business_id,
            )
        )

    async def list_active_page(
        self,
        session: AsyncSession,
        business_id: int,
        *,
        status: ProjectStatus | None,
        query: str | None,
        limit: int,
        offset: int,
        sort_by: str,
        descending: bool,
    ) -> tuple[list[Project], int]:
        filters = [
            Project.business_id == business_id,
            Project.deleted_at.is_(None),
        ]
        if status is not None:
            filters.append(Project.status == status)
        if query is not None:
            filters.append(Project.name.ilike(f"%{query}%"))

        sort_columns = {
            "id": Project.id,
            "name": Project.name,
            "status": Project.status,
        }
        sort_column = sort_columns[sort_by]
        ordering = sort_column.desc() if descending else sort_column.asc()
        total = await session.scalar(
            select(func.count()).select_from(Project).where(*filters)
        )
        result = await session.scalars(
            select(Project)
            .where(*filters)
            .order_by(ordering, Project.id.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.all()), int(total or 0)

    def add(self, session: AsyncSession, project: Project) -> None:
        session.add(project)
