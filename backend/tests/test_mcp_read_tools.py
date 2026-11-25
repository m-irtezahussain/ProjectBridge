import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from mcp import Client
from mcp.server import MCPServer

from app.core.managers.tasks import TaskNotFoundError
from app.core.services.mcp_auth import MCPPrincipal
from app.mcp.tools import register_read_tools
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


class FakeSessions:
    @asynccontextmanager
    async def session(self) -> AsyncIterator[object]:
        yield object()


class FakeAccounts:
    async def get_current_account(
        self, _session: object, _principal: MCPPrincipal
    ) -> tuple[User, Business]:
        return (
            User(
                id=7,
                full_name="Maya Chen",
                email="maya@example.com",
                password_hash="$argon2id$valid-test-password-hash",
            ),
            Business(id=11, name="Acme Studio", owned_by=7),
        )


class FakeProjects:
    def __init__(self) -> None:
        self.project = Project(
            id=3,
            name="Client Portal",
            description="Customer workspace",
            business_id=11,
            status=ProjectStatus.ACTIVE,
        )

    async def list_projects_page_for_principal(
        self,
        _session: object,
        _principal: MCPPrincipal,
        *,
        status: ProjectStatus | None,
        **_kwargs: object,
    ) -> tuple[list[Project], int]:
        if status is None or status is self.project.status:
            return [self.project], 1
        return [], 0

    async def get_project_for_principal(
        self,
        _session: object,
        _principal: MCPPrincipal,
        _project_id: int,
    ) -> Project:
        return self.project


class FakeTasks:
    def __init__(self) -> None:
        self.task = Task(
            id=8,
            title="Prepare release",
            project_id=3,
            status=TaskStatus.TODO,
            priority=TaskPriority.HIGH,
            assignee_id=7,
        )
        self.assignee = User(
            id=7,
            full_name="Maya Chen",
            email="maya@example.com",
            password_hash="$argon2id$valid-test-password-hash",
        )

    async def list_tasks_page_for_principal(
        self, *_args: object, **_kwargs: object
    ) -> tuple[list[Task], int]:
        return [self.task], 1

    async def get_task_for_principal(self, *_args: object) -> Task:
        return self.task

    async def get_source_reference_for_principal(
        self, *_args: object
    ) -> SimpleNamespace:
        return SimpleNamespace(
            task=SimpleNamespace(id=8, project_id=3, created_by=TaskSource.WORKER),
            document=SimpleNamespace(
                id=5,
                project_id=3,
                original_filename="launch.png",
                content_sha256="a" * 64,
            ),
            candidate=SimpleNamespace(
                id=12,
                source_excerpt="TODO: Prepare release",
                page_number=1,
                source_line_start=4,
                source_line_end=4,
                extractor="safe_marker_extractor",
                extractor_version="1.0",
                extracted_via="worker",
            ),
            document_text=SimpleNamespace(
                status=SimpleNamespace(value="completed"),
                engine="paddleocr",
                engine_version="3.7.0",
                model="PP-OCRv6_small",
                language="en",
            ),
            ingestion_run=SimpleNamespace(
                id=9,
                requested_by_user_id=7,
                initiated_via="mcp",
                ocr_status=SimpleNamespace(value="completed"),
            ),
        )

    async def list_assignees_for_principal(self, *_args: object) -> list[User]:
        return [self.assignee]


@pytest.mark.asyncio
async def test_read_tools_return_compact_typed_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = MCPServer("read-tools-test")
    register_read_tools(
        server,
        FakeSessions(),  # type: ignore[arg-type]
        FakeAccounts(),  # type: ignore[arg-type]
        FakeProjects(),  # type: ignore[arg-type]
        FakeTasks(),  # type: ignore[arg-type]
    )
    principal = MCPPrincipal(
        user_id=7,
        business_id=11,
        scopes=frozenset({"projects:read", "tasks:read", "documents:read"}),
        grant_id="grant-id",
    )
    monkeypatch.setattr("app.mcp.tools.require_mcp_principal", lambda *_: principal)

    async with Client(server) as client:
        account = await client.call_tool("get_current_account", {})
        listed = await client.call_tool("list_projects", {"status": "Active"})
        project = await client.call_tool("get_project", {"project_id": 3})
        tasks = await client.call_tool("list_tasks", {"input": {"project_id": 3}})
        task = await client.call_tool(
            "get_task", {"project_id": 3, "task_id": 8}
        )
        source = await client.call_tool(
            "get_task_source_reference", {"project_id": 3, "task_id": 8}
        )
        assignees = await client.call_tool("list_assignees", {})

    assert account.is_error is False
    assert account.structured_content == {
        "user_id": 7,
        "full_name": "Maya Chen",
        "email": "maya@example.com",
        "business_id": 11,
        "business_name": "Acme Studio",
        "scopes": ["documents:read", "projects:read", "tasks:read"],
    }
    assert listed.structured_content == {
        "projects": [
            {
                "id": 3,
                "name": "Client Portal",
                "status": "Active",
                "description": "Customer workspace",
            }
        ],
        "total": 1,
        "limit": 50,
        "offset": 0,
        "has_more": False,
    }
    assert project.structured_content == listed.structured_content["projects"][0]
    assert tasks.structured_content == {
        "tasks": [
            {
                "id": 8,
                "title": "Prepare release",
                "description": None,
                "status": "todo",
                "priority": "high",
                "assignee_id": 7,
                "source_document_id": None,
                "source_candidate_id": None,
                "project_id": 3,
            }
        ],
        "total": 1,
        "limit": 50,
        "offset": 0,
        "has_more": False,
    }
    assert task.structured_content == tasks.structured_content["tasks"][0]
    assert source.structured_content == {
        "task_id": 8,
        "project_id": 3,
        "task_created_via": "worker",
        "has_document_source": True,
        "document_id": 5,
        "document_project_id": 3,
        "original_filename": "launch.png",
        "content_sha256": "a" * 64,
        "candidate_id": 12,
        "ingestion_run_id": 9,
        "source_excerpt": "TODO: Prepare release",
        "page_number": 1,
        "source_line_start": 4,
        "source_line_end": 4,
        "extractor": "safe_marker_extractor",
        "extractor_version": "1.0",
        "extracted_via": "worker",
        "ocr_status": "completed",
        "ocr_engine": "paddleocr",
        "ocr_engine_version": "3.7.0",
        "ocr_model": "PP-OCRv6_small",
        "ocr_language": "en",
        "ingestion_initiated_by_user_id": 7,
        "ingestion_initiated_via": "mcp",
    }
    assert "text" not in source.structured_content
    assert assignees.structured_content == {
        "assignees": [
            {"user_id": 7, "full_name": "Maya Chen", "email": "maya@example.com"}
        ]
    }


@pytest.mark.asyncio
async def test_read_tool_returns_structured_not_found_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MissingTasks(FakeTasks):
        async def get_task_for_principal(self, *_args: object) -> Task:
            raise TaskNotFoundError("Task not found")

    server = MCPServer("read-errors-test")
    register_read_tools(
        server,
        FakeSessions(),  # type: ignore[arg-type]
        FakeAccounts(),  # type: ignore[arg-type]
        FakeProjects(),  # type: ignore[arg-type]
        MissingTasks(),  # type: ignore[arg-type]
    )
    principal = MCPPrincipal(
        user_id=7,
        business_id=11,
        scopes=frozenset({"tasks:read"}),
        grant_id="grant-id",
    )
    monkeypatch.setattr("app.mcp.tools.require_mcp_principal", lambda *_: principal)

    async with Client(server) as client:
        result = await client.call_tool(
            "get_task", {"project_id": 3, "task_id": 999}
        )

    assert result.is_error is True
    error_text = result.content[0].text  # type: ignore[union-attr]
    detail = json.loads(error_text.split(": ", maxsplit=1)[1])
    assert detail == {
        "code": "not_found",
        "message": "Task not found",
        "retryable": False,
    }
