from dataclasses import dataclass

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Document,
    DocumentText,
    IngestionRun,
    Project,
    Task,
    TaskCandidate,
    TaskPriority,
    TaskStatus,
)


@dataclass(frozen=True)
class TaskSourceReferenceRecord:
    task: Task
    document: Document | None
    candidate: TaskCandidate | None
    document_text: DocumentText | None
    ingestion_run: IngestionRun | None


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

    async def get_for_project(
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
                Project.business_id == business_id,
                Project.deleted_at.is_(None),
            )
        )

    async def list_active_before_id(
        self,
        session: AsyncSession,
        business_id: int,
        project_id: int,
        *,
        before_id: int | None,
        limit: int,
    ) -> list[Task]:
        filters = [
            Task.project_id == project_id,
            Task.is_deleted.is_(False),
            Project.business_id == business_id,
            Project.deleted_at.is_(None),
        ]
        if before_id is not None:
            filters.append(Task.id < before_id)
        result = await session.scalars(
            select(Task)
            .join(Project, Task.project_id == Project.id)
            .where(*filters)
            .order_by(Task.id.desc())
            .limit(limit)
        )
        return list(result.all())

    async def list_active_page(
        self,
        session: AsyncSession,
        business_id: int,
        project_id: int,
        *,
        status: TaskStatus | None,
        priority: TaskPriority | None,
        assignee_id: int | None,
        query: str | None,
        limit: int,
        offset: int,
        sort_by: str,
        descending: bool,
    ) -> tuple[list[Task], int]:
        filters = [
            Task.project_id == project_id,
            Task.is_deleted.is_(False),
            Project.business_id == business_id,
            Project.deleted_at.is_(None),
        ]
        if status is not None:
            filters.append(Task.status == status)
        if priority is not None:
            filters.append(Task.priority == priority)
        if assignee_id is not None:
            filters.append(Task.assignee_id == assignee_id)
        if query is not None:
            filters.append(Task.title.ilike(f"%{query}%"))

        sort_columns = {
            "id": Task.id,
            "title": Task.title,
            "status": Task.status,
            "priority": Task.priority,
        }
        sort_column = sort_columns[sort_by]
        ordering = sort_column.desc() if descending else sort_column.asc()
        total = await session.scalar(
            select(func.count())
            .select_from(Task)
            .join(Project, Task.project_id == Project.id)
            .where(*filters)
        )
        result = await session.scalars(
            select(Task)
            .join(Project, Task.project_id == Project.id)
            .where(*filters)
            .order_by(ordering, Task.id.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.all()), int(total or 0)

    def add(self, session: AsyncSession, task: Task) -> None:
        session.add(task)

    async def get_source_reference(
        self,
        session: AsyncSession,
        business_id: int,
        project_id: int,
        task_id: int,
    ) -> TaskSourceReferenceRecord | None:
        row = (
            await session.execute(
                select(Task, Document, TaskCandidate, DocumentText, IngestionRun)
                .join(Project, Task.project_id == Project.id)
                .outerjoin(
                    Document,
                    and_(
                        Task.source_document_id == Document.id,
                        Document.business_id == business_id,
                    ),
                )
                .outerjoin(
                    TaskCandidate,
                    and_(
                        Task.source_candidate_id == TaskCandidate.id,
                        TaskCandidate.business_id == business_id,
                    ),
                )
                .outerjoin(
                    DocumentText,
                    and_(
                        TaskCandidate.source_text_id == DocumentText.id,
                        DocumentText.business_id == business_id,
                    ),
                )
                .outerjoin(
                    IngestionRun,
                    and_(
                        TaskCandidate.ingestion_run_id == IngestionRun.id,
                        IngestionRun.business_id == business_id,
                    ),
                )
                .where(
                    Task.id == task_id,
                    Task.project_id == project_id,
                    Task.is_deleted.is_(False),
                    Project.business_id == business_id,
                    Project.deleted_at.is_(None),
                )
            )
        ).one_or_none()
        if row is None:
            return None
        return TaskSourceReferenceRecord(
            task=row[0],
            document=row[1],
            candidate=row[2],
            document_text=row[3],
            ingestion_run=row[4],
        )
