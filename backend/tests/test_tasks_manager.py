from unittest.mock import AsyncMock

import pytest

from app.core.managers.tasks import TaskManager, TaskNotFoundError
from app.models import (
    Business,
    Project,
    ProjectStatus,
    Task,
    TaskPriority,
    TaskSource,
    TaskStatus,
    User,
)
from app.schemas import TaskCreate, TaskUpdate


class FakeAuth:
    def __init__(self, user: User | None) -> None:
        self.user = user

    async def get_user(
        self, _session: object, _token: str | None, _purpose: str
    ) -> User | None:
        return self.user


class FakeBusinesses:
    def __init__(self, business: Business) -> None:
        self.business = business

    async def get_for_owner(
        self, _session: object, owner_id: int
    ) -> Business | None:
        return self.business if self.business.owned_by == owner_id else None


class FakeProjects:
    def __init__(self, project: Project) -> None:
        self.project = project

    async def get_active(
        self, _session: object, business_id: int, project_id: int
    ) -> Project | None:
        if (
            self.project.id != project_id
            or self.project.business_id != business_id
            or self.project.deleted_at is not None
        ):
            return None
        return self.project


class FakeTasks:
    def __init__(self) -> None:
        self.items: dict[int, Task] = {}

    async def list_active(
        self, _session: object, business_id: int, project_id: int
    ) -> list[Task]:
        if business_id != 11:
            return []
        return [
            task
            for task in self.items.values()
            if task.project_id == project_id and not task.is_deleted
        ]

    async def get_active(
        self,
        _session: object,
        business_id: int,
        project_id: int,
        task_id: int,
    ) -> Task | None:
        task = self.items.get(task_id)
        if (
            business_id != 11
            or task is None
            or task.project_id != project_id
            or task.is_deleted
        ):
            return None
        return task

    def add(self, _session: object, task: Task) -> None:
        task.id = len(self.items) + 1
        self.items[task.id] = task


def make_manager() -> tuple[TaskManager, FakeTasks, AsyncMock]:
    user = User(
        id=1,
        full_name="Maya Chen",
        email="maya@example.com",
        password_hash="$argon2id$valid-example-hash",
    )
    business = Business(id=11, name="Acme Studio", owned_by=1)
    project = Project(
        id=3,
        name="Client Portal",
        business_id=11,
        status=ProjectStatus.ACTIVE,
    )
    tasks = FakeTasks()
    manager = TaskManager(
        FakeAuth(user),  # type: ignore[arg-type]
        FakeBusinesses(business),  # type: ignore[arg-type]
        FakeProjects(project),  # type: ignore[arg-type]
        tasks,  # type: ignore[arg-type]
    )
    return manager, tasks, AsyncMock()


async def test_task_crud_soft_deletion_and_api_source() -> None:
    manager, tasks, session = make_manager()

    created = await manager.create_task(
        session,
        "access-token",
        3,
        TaskCreate(
            title="Prepare release",
            description="Confirm the final checklist",
            status=TaskStatus.IN_PROCESS,
            priority=TaskPriority.HIGH,
        ),
    )
    updated = await manager.update_task(
        session,
        "access-token",
        3,
        created.id,
        TaskUpdate(status=TaskStatus.IN_REVIEW, description=None),
    )

    assert created.project_id == 3
    assert created.created_by is TaskSource.REST
    assert updated.status is TaskStatus.IN_REVIEW
    assert updated.description is None
    assert await manager.list_tasks(session, "access-token", 3) == [created]

    await manager.dismiss_task(session, "access-token", 3, created.id)

    assert created.is_deleted is True
    assert await manager.list_tasks(session, "access-token", 3) == []
    with pytest.raises(TaskNotFoundError, match="Task not found"):
        await manager.get_task(session, "access-token", 3, created.id)
    assert tasks.items[created.id] is created


async def test_task_lookup_never_crosses_project_boundary() -> None:
    manager, tasks, session = make_manager()
    tasks.items[9] = Task(
        id=9,
        title="Another project task",
        project_id=999,
        status=TaskStatus.TODO,
        priority=TaskPriority.LOW,
    )

    with pytest.raises(TaskNotFoundError, match="Task not found"):
        await manager.get_task(session, "access-token", 3, 9)
