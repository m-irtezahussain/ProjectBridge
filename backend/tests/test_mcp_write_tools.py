from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from mcp import Client
from mcp.server import MCPServer

from app.core.services.mcp_auth import MCPPrincipal
from app.core.services.mcp_mutations import MCPMutationResult
from app.mcp.tools import register_write_tools
from app.models import (
    Project,
    ProjectStatus,
    Task,
    TaskPriority,
    TaskSource,
    TaskStatus,
)
from app.schemas import ProjectCreate, ProjectUpdate, TaskCreate, TaskUpdate


class FakeSessions:
    @asynccontextmanager
    async def session(self) -> AsyncIterator[object]:
        yield object()


class FakeProjects:
    def __init__(self) -> None:
        self.archived = False

    async def create_project_for_principal(
        self,
        _session: object,
        principal: MCPPrincipal,
        data: ProjectCreate,
        _idempotency_key: str,
    ) -> MCPMutationResult[Project]:
        return MCPMutationResult(
            entity=Project(
                id=4,
                name=data.name,
                description=data.description,
                business_id=principal.business_id,
                status=data.status,
            ),
            replayed=False,
        )

    async def update_project_for_principal(
        self,
        _session: object,
        principal: MCPPrincipal,
        project_id: int,
        data: ProjectUpdate,
    ) -> Project:
        return Project(
            id=project_id,
            name=data.name or "Client Portal",
            description=data.description,
            business_id=principal.business_id,
            status=data.status or ProjectStatus.PLANNING,
        )

    async def archive_project_for_principal(
        self, _session: object, _principal: MCPPrincipal, _project_id: int
    ) -> bool:
        replayed = self.archived
        self.archived = True
        return replayed


class FakeTasks:
    def __init__(self) -> None:
        self.archived = False

    async def create_task_for_principal(
        self,
        _session: object,
        _principal: MCPPrincipal,
        project_id: int,
        data: TaskCreate,
        _idempotency_key: str,
    ) -> MCPMutationResult[Task]:
        return MCPMutationResult(
            entity=Task(
                id=8,
                title=data.title,
                description=data.description,
                status=data.status,
                priority=data.priority,
                project_id=project_id,
                created_by=TaskSource.MCP,
            ),
            replayed=False,
        )

    async def update_task_for_principal(
        self,
        _session: object,
        _principal: MCPPrincipal,
        project_id: int,
        task_id: int,
        data: TaskUpdate,
    ) -> Task:
        return Task(
            id=task_id,
            title=data.title or "Prepare release",
            description=data.description,
            status=data.status or TaskStatus.TODO,
            priority=data.priority or TaskPriority.MEDIUM,
            project_id=project_id,
            assignee_id=data.assignee_id,
            created_by=TaskSource.MCP,
        )

    async def archive_task_for_principal(
        self,
        _session: object,
        _principal: MCPPrincipal,
        _project_id: int,
        _task_id: int,
    ) -> bool:
        replayed = self.archived
        self.archived = True
        return replayed

    async def assign_task_for_principal(
        self,
        _session: object,
        _principal: MCPPrincipal,
        project_id: int,
        task_id: int,
        assignee_id: int,
    ) -> Task:
        return Task(
            id=task_id,
            title="Prepare release",
            status=TaskStatus.TODO,
            priority=TaskPriority.MEDIUM,
            project_id=project_id,
            assignee_id=assignee_id,
            created_by=TaskSource.MCP,
        )


@pytest.mark.asyncio
async def test_write_tools_return_typed_results_and_archive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = MCPServer("write-tools-test")
    tasks = FakeTasks()
    projects = FakeProjects()
    register_write_tools(
        server,
        FakeSessions(),  # type: ignore[arg-type]
        projects,  # type: ignore[arg-type]
        tasks,  # type: ignore[arg-type]
    )
    principal = MCPPrincipal(
        user_id=7,
        business_id=11,
        scopes=frozenset({"projects:write", "tasks:write"}),
        grant_id="grant-id",
    )
    monkeypatch.setattr("app.mcp.tools.require_mcp_principal", lambda *_: principal)

    async with Client(server) as client:
        project = await client.call_tool(
            "create_project",
            {
                "input": {
                    "name": "Client Portal",
                    "status": "Active",
                    "idempotency_key": "project-key",
                }
            },
        )
        updated_project = await client.call_tool(
            "update_project",
            {"input": {"project_id": 4, "status": "Completed"}},
        )
        archived_project = await client.call_tool(
            "archive_project", {"input": {"project_id": 4}}
        )
        task = await client.call_tool(
            "create_task",
            {
                "input": {
                    "project_id": 4,
                    "title": "Prepare release",
                    "priority": "high",
                    "idempotency_key": "task-key",
                }
            },
        )
        updated_task = await client.call_tool(
            "update_task",
            {
                "input": {
                    "project_id": 4,
                    "task_id": 8,
                    "status": "done",
                }
            },
        )
        assigned_task = await client.call_tool(
            "assign_task",
            {"input": {"project_id": 4, "task_id": 8, "assignee_id": 7}},
        )
        archived = await client.call_tool(
            "archive_task",
            {"input": {"project_id": 4, "task_id": 8}},
        )
        missing_key = await client.call_tool(
            "create_project",
            {"input": {"name": "Missing retry key"}},
        )
        empty_update = await client.call_tool(
            "update_project",
            {"input": {"project_id": 4}},
        )

    assert project.is_error is False
    assert project.structured_content["project"]["id"] == 4
    assert project.structured_content["replayed"] is False
    assert updated_project.structured_content["status"] == "Completed"
    assert task.structured_content["task"]["priority"] == "high"
    assert updated_task.structured_content["status"] == "done"
    assert assigned_task.structured_content["assignee_id"] == 7
    assert archived_project.structured_content == {
        "project_id": 4,
        "archived": True,
        "replayed": False,
    }
    assert archived.structured_content == {
        "task_id": 8,
        "archived": True,
        "replayed": False,
    }
    assert tasks.archived is True
    assert missing_key.is_error is True
    assert empty_update.is_error is True
