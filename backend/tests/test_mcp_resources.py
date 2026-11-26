import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from mcp import Client
from mcp.server import MCPServer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.managers.resources import ContextResourceManager, ResourcePage
from app.core.services.mcp_auth import MCPPrincipal
from app.core.services.resource_cursor import ResourceCursorCodec, ResourceCursorError
from app.mcp.resources import register_context_resources
from app.models import (
    Business,
    Document,
    DocumentStatus,
    Project,
    ProjectStatus,
    Task,
    TaskPriority,
    TaskStatus,
)


class FakeSessions:
    @asynccontextmanager
    async def session(self) -> AsyncIterator[object]:
        yield object()


class FakeResources:
    def __init__(self) -> None:
        self.project = Project(
            id=3,
            business_id=11,
            name="Client Portal",
            description="Customer workspace",
            status=ProjectStatus.ACTIVE,
            version=1,
        )
        self.task = Task(
            id=8,
            project_id=3,
            title="Prepare release",
            description="Check the release candidate",
            status=TaskStatus.TODO,
            priority=TaskPriority.HIGH,
            source_document_id=5,
            version=1,
        )
        self.document = Document(
            id=5,
            business_id=11,
            project_id=3,
            uploaded_by_user_id=7,
            original_filename="launch.png",
            declared_mime_type="image/png",
            detected_mime_type="image/png",
            declared_size=100,
            size_bytes=100,
            content_sha256="a" * 64,
            quarantine_key="businesses/11/quarantine/5",
            status=DocumentStatus.AVAILABLE,
            upload_expires_at=datetime.now(UTC),
            version=1,
        )

    async def get_project(self, *_args: object) -> Project:
        return self.project

    async def list_projects(self, *_args: object, **_kwargs: object) -> ResourcePage[Project]:
        return ResourcePage(items=[self.project], next_cursor="project-next")

    async def get_task(self, *_args: object) -> Task:
        return self.task

    async def list_tasks(self, *_args: object, **_kwargs: object) -> ResourcePage[Task]:
        return ResourcePage(items=[self.task], next_cursor=None)

    async def get_document(self, *_args: object) -> Document:
        return self.document

    async def list_documents(
        self, *_args: object, **_kwargs: object
    ) -> ResourcePage[Document]:
        return ResourcePage(items=[self.document], next_cursor=None)


class FakeBusinesses:
    async def get_for_owner(self, _session: object, owner_id: int) -> Business | None:
        return Business(id=11, name="Acme", owned_by=7) if owner_id == 7 else None


class PagingProjects:
    def __init__(self) -> None:
        self.ids = [5, 4, 3, 2, 1]

    async def list_active_before_id(
        self,
        _session: object,
        _business_id: int,
        *,
        before_id: int | None,
        limit: int,
    ) -> list[Project]:
        ids = [item_id for item_id in self.ids if before_id is None or item_id < before_id]
        return [
            Project(
                id=item_id,
                business_id=11,
                name=f"Project {item_id}",
                status=ProjectStatus.ACTIVE,
                version=1,
            )
            for item_id in ids[:limit]
        ]


def resource_json(result: Any) -> dict[str, object]:
    return json.loads(result.contents[0].text)


async def test_resource_templates_return_compact_linked_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = MCPServer("resources-test")
    register_context_resources(
        server,
        FakeSessions(),  # type: ignore[arg-type]
        FakeResources(),  # type: ignore[arg-type]
    )
    principal = MCPPrincipal(
        user_id=7,
        business_id=11,
        scopes=frozenset({"projects:read", "tasks:read", "documents:read"}),
        grant_id="grant-id",
    )
    monkeypatch.setattr(
        "app.mcp.resources.require_mcp_principal", lambda *_: principal
    )

    async with Client(server) as client:
        capabilities = await client.read_resource("projectbridge://capabilities")
        project = await client.read_resource("projectbridge://projects/3")
        projects = await client.read_resource("projectbridge://projects?limit=1")
        task = await client.read_resource("projectbridge://projects/3/tasks/8")
        document = await client.read_resource("projectbridge://documents/5")

    capability_data = resource_json(capabilities)
    project_data = resource_json(project)
    project_page = resource_json(projects)
    task_data = resource_json(task)
    document_data = resource_json(document)

    assert capability_data["resource_schema_version"] == "1.0"
    assert capability_data["pagination"]["method"] == "signed keyset cursor"  # type: ignore[index]
    assert project_data["uri"] == "projectbridge://projects/3"
    assert "business_id" not in project_data
    assert project_page["has_more"] is True
    assert project_page["next_uri"] == (
        "projectbridge://projects?limit=1&cursor=project-next"
    )
    assert task_data["links"][1] == {  # type: ignore[index]
        "rel": "source-document",
        "uri": "projectbridge://documents/5",
    }
    assert document_data["content_sha256"] == "a" * 64
    assert "storage_key" not in document_data


def test_resource_cursor_is_tenant_and_collection_bound() -> None:
    codec = ResourceCursorCodec("a-test-secret-that-is-long-enough")
    cursor = codec.encode(
        kind="tasks", business_id=11, parent_id=3, last_id=8
    )

    assert codec.decode(
        cursor, kind="tasks", business_id=11, parent_id=3
    ).last_id == 8  # type: ignore[union-attr]
    with pytest.raises(ResourceCursorError):
        codec.decode(cursor, kind="tasks", business_id=22, parent_id=3)
    with pytest.raises(ResourceCursorError):
        codec.decode(cursor, kind="documents", business_id=11, parent_id=3)
    with pytest.raises(ResourceCursorError):
        codec.decode(f"{cursor}x", kind="tasks", business_id=11, parent_id=3)


async def test_keyset_page_walk_does_not_duplicate_rows_during_changes() -> None:
    projects = PagingProjects()
    manager = ContextResourceManager(
        ResourceCursorCodec("a-test-secret-that-is-long-enough"),
        businesses=FakeBusinesses(),  # type: ignore[arg-type]
        projects=projects,  # type: ignore[arg-type]
    )
    principal = MCPPrincipal(
        user_id=7,
        business_id=11,
        scopes=frozenset({"projects:read"}),
        grant_id="grant-id",
    )
    session = cast(AsyncSession, object())

    first = await manager.list_projects(session, principal, cursor=None, limit=2)
    projects.ids.insert(0, 6)
    projects.ids.remove(3)
    second = await manager.list_projects(
        session, principal, cursor=first.next_cursor, limit=2
    )

    walked_ids = [item.id for item in first.items + second.items]
    assert walked_ids == [5, 4, 2, 1]
    assert len(walked_ids) == len(set(walked_ids))
    assert second.next_cursor is None
