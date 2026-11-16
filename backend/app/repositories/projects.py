from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project


class ProjectRepository:
    """Database access that always scopes projects to one business."""

    async def list_active(
        self, session: AsyncSession, business_id: int
    ) -> list[Project]:
        result = await session.scalars(
            select(Project)
            .where(
                Project.business_id == business_id,
                Project.deleted_at.is_(None),
            )
            .order_by(Project.id.desc())
        )
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

    def add(self, session: AsyncSession, project: Project) -> None:
        session.add(project)
