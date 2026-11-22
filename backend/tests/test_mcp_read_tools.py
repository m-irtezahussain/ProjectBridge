from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from mcp import Client
from mcp.server import MCPServer

from app.core.services.mcp_auth import MCPPrincipal
from app.mcp.tools import register_read_tools
from app.models import Business, Project, ProjectStatus, User


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

    async def list_projects_for_principal(
        self,
        _session: object,
        _principal: MCPPrincipal,
        status: ProjectStatus | None = None,
    ) -> list[Project]:
        if status is None or status is self.project.status:
            return [self.project]
        return []

    async def get_project_for_principal(
        self,
        _session: object,
        _principal: MCPPrincipal,
        _project_id: int,
    ) -> Project:
        return self.project


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
    )
    principal = MCPPrincipal(
        user_id=7,
        business_id=11,
        scopes=frozenset({"projects:read"}),
        grant_id="grant-id",
    )
    monkeypatch.setattr("app.mcp.tools.require_mcp_principal", lambda *_: principal)

    async with Client(server) as client:
        account = await client.call_tool("get_current_account", {})
        listed = await client.call_tool("list_projects", {"status": "Active"})
        project = await client.call_tool("get_project", {"project_id": 3})

    assert account.is_error is False
    assert account.structured_content == {
        "user_id": 7,
        "full_name": "Maya Chen",
        "email": "maya@example.com",
        "business_id": 11,
        "business_name": "Acme Studio",
        "scopes": ["projects:read"],
    }
    assert listed.structured_content == {
        "projects": [
            {
                "id": 3,
                "name": "Client Portal",
                "status": "Active",
                "description": "Customer workspace",
            }
        ]
    }
    assert project.structured_content == listed.structured_content["projects"][0]
