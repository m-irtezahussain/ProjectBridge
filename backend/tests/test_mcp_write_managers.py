from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.core.managers.projects import ProjectManager, ProjectNotFoundError
from app.core.managers.tasks import AssigneeNotFoundError, TaskManager
from app.core.services.mcp_auth import MCPPrincipal
from app.core.services.mcp_mutations import (
    IdempotencyConflictError,
    hash_idempotency_key,
)
from app.models import (
    Business,
    MCPIdempotencyRecord,
    Project,
    ProjectStatus,
    Task,
    TaskPriority,
    TaskSource,
    TaskStatus,
    User,
)
from app.repositories.mcp_operations import IdempotencyClaim
from app.schemas import ProjectCreate, ProjectUpdate, TaskCreate, TaskUpdate


class FakeAuth:
    pass


class FakeBusinesses:
    def __init__(self) -> None:
        self.business = Business(id=11, name="Acme", owned_by=7)

    async def get_for_owner(
        self, _session: object, owner_id: int
    ) -> Business | None:
        return self.business if owner_id == 7 else None


class FakeProjects:
    def __init__(self) -> None:
        self.items: dict[int, Project] = {}

    async def get_active(
        self, _session: object, business_id: int, project_id: int
    ) -> Project | None:
        project = self.items.get(project_id)
        if (
            project is None
            or project.business_id != business_id
            or project.deleted_at is not None
        ):
            return None
        return project

    async def get_for_business(
        self, _session: object, business_id: int, project_id: int
    ) -> Project | None:
        project = self.items.get(project_id)
        if project is None or project.business_id != business_id:
            return None
        return project

    def add(self, _session: object, project: Project) -> None:
        project.id = len(self.items) + 1
        self.items[project.id] = project


class FakeTasks:
    def __init__(self) -> None:
        self.items: dict[int, Task] = {}

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

    async def get_for_project(
        self,
        _session: object,
        business_id: int,
        project_id: int,
        task_id: int,
    ) -> Task | None:
        task = self.items.get(task_id)
        if business_id != 11 or task is None or task.project_id != project_id:
            return None
        return task

    def add(self, _session: object, task: Task) -> None:
        task.id = len(self.items) + 1
        self.items[task.id] = task


class FakeIdempotency:
    def __init__(self) -> None:
        self.records: dict[tuple[int, str, str, str], MCPIdempotencyRecord] = {}

    async def claim(
        self,
        _session: object,
        *,
        principal: MCPPrincipal,
        tool_name: str,
        idempotency_key: str,
        fingerprint: str,
    ) -> IdempotencyClaim:
        scope = (
            principal.business_id,
            principal.grant_id,
            tool_name,
            hash_idempotency_key(idempotency_key),
        )
        existing = self.records.get(scope)
        if existing is not None:
            return IdempotencyClaim(existing, is_new=False)
        record = MCPIdempotencyRecord(
            id=len(self.records) + 1,
            business_id=principal.business_id,
            user_id=principal.user_id,
            grant_id=principal.grant_id,
            tool_name=tool_name,
            key_hash=scope[-1],
            request_fingerprint=fingerprint,
            state="started",
        )
        self.records[scope] = record
        return IdempotencyClaim(record, is_new=True)

    def complete(
        self,
        record: MCPIdempotencyRecord,
        *,
        result_type: str,
        result_id: int,
        response_body: dict[str, object],
    ) -> None:
        record.state = "completed"
        record.result_type = result_type
        record.result_id = result_id
        record.response_body = response_body
        record.completed_at = datetime.now(UTC)


class FakeAudit:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def add(
        self,
        _session: object,
        *,
        principal: MCPPrincipal,
        tool_name: str,
        target_type: str,
        target_id: int | None,
        outcome: str,
    ) -> None:
        self.events.append(
            {
                "user_id": principal.user_id,
                "business_id": principal.business_id,
                "grant_id": principal.grant_id,
                "tool_name": tool_name,
                "target_type": target_type,
                "target_id": target_id,
                "outcome": outcome,
            }
        )


class FakeUsers:
    def __init__(self) -> None:
        self.owner = User(
            id=7,
            full_name="Maya Chen",
            email="maya@example.com",
            password_hash="$argon2id$valid-test-password-hash",
        )

    async def get_business_assignee(
        self, _session: object, business_id: int, user_id: int
    ) -> User | None:
        if business_id == 11 and user_id == self.owner.id:
            return self.owner
        return None

    async def list_business_assignees(
        self, _session: object, business_id: int
    ) -> list[User]:
        return [self.owner] if business_id == 11 else []


def principal() -> MCPPrincipal:
    return MCPPrincipal(
        user_id=7,
        business_id=11,
        scopes=frozenset({"projects:write", "tasks:write"}),
        grant_id="grant-id",
    )


async def test_project_create_replays_and_rejects_key_mismatch() -> None:
    projects = FakeProjects()
    idempotency = FakeIdempotency()
    audit = FakeAudit()
    manager = ProjectManager(
        FakeAuth(),  # type: ignore[arg-type]
        FakeBusinesses(),  # type: ignore[arg-type]
        projects,  # type: ignore[arg-type]
        idempotency,  # type: ignore[arg-type]
        audit,  # type: ignore[arg-type]
    )
    session = AsyncMock()
    data = ProjectCreate(name="Client Portal", status=ProjectStatus.ACTIVE)

    created = await manager.create_project_for_principal(
        session, principal(), data, "project-key"
    )
    replayed = await manager.create_project_for_principal(
        session, principal(), data, "project-key"
    )

    assert created.replayed is False
    assert replayed.replayed is True
    assert replayed.entity.id == created.entity.id
    assert len(projects.items) == 1
    assert [event["outcome"] for event in audit.events] == [
        "success",
        "idempotent_replay",
    ]
    assert audit.events[0] == {
        "user_id": 7,
        "business_id": 11,
        "grant_id": "grant-id",
        "tool_name": "create_project",
        "target_type": "project",
        "target_id": 1,
        "outcome": "success",
    }

    with pytest.raises(IdempotencyConflictError):
        await manager.create_project_for_principal(
            session,
            principal(),
            ProjectCreate(name="Different project"),
            "project-key",
        )
    assert audit.events[-1]["outcome"] == "idempotency_conflict"


async def test_project_update_is_tenant_scoped_and_audited() -> None:
    projects = FakeProjects()
    audit = FakeAudit()
    manager = ProjectManager(
        FakeAuth(),  # type: ignore[arg-type]
        FakeBusinesses(),  # type: ignore[arg-type]
        projects,  # type: ignore[arg-type]
        FakeIdempotency(),  # type: ignore[arg-type]
        audit,  # type: ignore[arg-type]
    )
    projects.items[1] = Project(
        id=1,
        name="Client Portal",
        business_id=11,
        status=ProjectStatus.PLANNING,
    )

    updated = await manager.update_project_for_principal(
        AsyncMock(),
        principal(),
        1,
        ProjectUpdate(status=ProjectStatus.ACTIVE),
    )

    assert updated.status is ProjectStatus.ACTIVE
    assert audit.events[-1]["tool_name"] == "update_project"
    assert audit.events[-1]["outcome"] == "success"

    projects.items[2] = Project(
        id=2,
        name="Other tenant",
        business_id=999,
        status=ProjectStatus.ACTIVE,
    )
    with pytest.raises(ProjectNotFoundError):
        await manager.update_project_for_principal(
            AsyncMock(),
            principal(),
            2,
            ProjectUpdate(status=ProjectStatus.COMPLETED),
        )
    assert projects.items[2].status is ProjectStatus.ACTIVE
    assert audit.events[-1]["outcome"] == "not_found"


async def test_project_archive_is_idempotent_and_tenant_scoped() -> None:
    projects = FakeProjects()
    audit = FakeAudit()
    manager = ProjectManager(
        FakeAuth(),  # type: ignore[arg-type]
        FakeBusinesses(),  # type: ignore[arg-type]
        projects,  # type: ignore[arg-type]
        FakeIdempotency(),  # type: ignore[arg-type]
        audit,  # type: ignore[arg-type]
    )
    projects.items[1] = Project(
        id=1,
        name="Client Portal",
        business_id=11,
        status=ProjectStatus.ACTIVE,
    )

    first = await manager.archive_project_for_principal(AsyncMock(), principal(), 1)
    retried = await manager.archive_project_for_principal(AsyncMock(), principal(), 1)

    assert first is False
    assert retried is True
    assert projects.items[1].deleted_at is not None
    assert [event["outcome"] for event in audit.events] == [
        "success",
        "idempotent_replay",
    ]
async def test_task_writes_are_idempotent_sourced_and_audited() -> None:
    project = Project(
        id=3,
        name="Client Portal",
        business_id=11,
        status=ProjectStatus.ACTIVE,
    )
    projects = FakeProjects()
    projects.items[3] = project
    tasks = FakeTasks()
    audit = FakeAudit()
    manager = TaskManager(
        FakeAuth(),  # type: ignore[arg-type]
        FakeBusinesses(),  # type: ignore[arg-type]
        projects,  # type: ignore[arg-type]
        tasks,  # type: ignore[arg-type]
        FakeIdempotency(),  # type: ignore[arg-type]
        audit,  # type: ignore[arg-type]
        FakeUsers(),  # type: ignore[arg-type]
    )
    session = AsyncMock()
    data = TaskCreate(
        title="Prepare release",
        priority=TaskPriority.HIGH,
        assignee_id=7,
    )

    created = await manager.create_task_for_principal(
        session, principal(), 3, data, "task-key"
    )
    replayed = await manager.create_task_for_principal(
        session, principal(), 3, data, "task-key"
    )
    updated = await manager.update_task_for_principal(
        session,
        principal(),
        3,
        created.entity.id,
        TaskUpdate(status=TaskStatus.DONE),
    )
    assigned = await manager.assign_task_for_principal(
        session,
        principal(),
        3,
        created.entity.id,
        7,
    )
    with pytest.raises(AssigneeNotFoundError):
        await manager.assign_task_for_principal(
            session,
            principal(),
            3,
            created.entity.id,
            99,
        )
    first_archive = await manager.archive_task_for_principal(
        session, principal(), 3, created.entity.id
    )
    retried_archive = await manager.archive_task_for_principal(
        session, principal(), 3, created.entity.id
    )

    assert created.entity.created_by is TaskSource.MCP
    assert created.entity.assignee_id == 7
    assert replayed.replayed is True
    assert len(tasks.items) == 1
    assert updated.status is TaskStatus.DONE
    assert assigned.assignee_id == 7
    assert created.entity.is_deleted is True
    assert first_archive is False
    assert retried_archive is True
    assert [event["tool_name"] for event in audit.events] == [
        "create_task",
        "create_task",
        "update_task",
        "assign_task",
        "archive_task",
        "archive_task",
    ]
    assert [event["outcome"] for event in audit.events] == [
        "success",
        "idempotent_replay",
        "success",
        "success",
        "success",
        "idempotent_replay",
    ]
