from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, Task


class TaskRepository:
    """Task persistence with tenant and project scoping enforced in every query."""

    async def list_active(
        self,
        session: AsyncSession,
        business_id: int,
        project_id: int,
    ) -> list[Task]:
        result = await session.scalars(
            select(Task)
            .join(Project, Task.project_id == Project.id)
            .where(
                Task.project_id == project_id,
                Task.is_deleted.is_(False),
                Project.business_id == business_id,
                Project.deleted_at.is_(None),
            )
            .order_by(Task.id.desc())
        )
        return list(result.all())

    async def get_active(
        self,
        session: AsyncSession,
        business_id: int,
        project_id: int,
        task_id: int,
    ) -> Task | None:
        return await session.scalar(
            select(Task)
            .join(Project, Task.project_id == Project.id)
            .where(
                Task.id == task_id,
                Task.project_id == project_id,
                Task.is_deleted.is_(False),
                Project.business_id == business_id,
                Project.deleted_at.is_(None),
            )
        )

    def add(self, session: AsyncSession, task: Task) -> None:
        session.add(task)
