from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from mcp import Client
from mcp.server import MCPServer
from sqlalchemy import event

from app.core.managers.audit import AuditManager
from app.core.managers.projects import BusinessRequiredError
from app.core.services.audit import AuditService, scrub_audit_details
from app.core.services.mcp_auth import MCPPrincipal
from app.db import get_session
from app.deps import get_audit_manager
from app.main import create_app
from app.mcp.audit_tools import register_audit_tools
from app.models import ActionOrigin, AuditEvent, Business, User
from app.models.audit import _reject_audit_mutation


class FakeAuditRepository:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []
        self.queried_business_id: int | None = None

    def add(self, _session: object, event: AuditEvent) -> None:
        self.events.append(event)

    async def list_page(
        self, _session: object, business_id: int, **_filters: object
    ) -> tuple[list[AuditEvent], int]:
        self.queried_business_id = business_id
        return self.events, len(self.events)


class FakeAuth:
    async def get_user(
        self, _session: object, token: str | None, _purpose: str
    ) -> User | None:
        if token != "valid":
            return None
        return User(
            id=7,
            full_name="Maya Chen",
            email="maya@example.com",
            password_hash="$argon2id$valid-test-password-hash",
        )


class FakeBusinesses:
    async def get_for_owner(
        self, _session: object, owner_id: int
    ) -> Business | None:
        return Business(id=11, name="Acme", owned_by=7) if owner_id == 7 else None


def test_audit_service_redacts_secret_fields_centrally() -> None:
    repository = FakeAuditRepository()
    service = AuditService(repository)  # type: ignore[arg-type]

    service.record(
        MagicMock(),
        business_id=11,
        actor_user_id=7,
        interface=ActionOrigin.REST,
        action="project.update",
        target_type="project",
        target_id=3,
        outcome="success",
        details={
            "status": "active",
            "access_token": "do-not-store",
            "nested": {"client_secret": "also-secret"},
        },
    )

    assert repository.events[0].details == {
        "status": "active",
        "access_token": "[REDACTED]",
        "nested": {"client_secret": "[REDACTED]"},
    }
    assert scrub_audit_details({"authorization": "Bearer value"}) == {
        "authorization": "[REDACTED]"
    }


def test_audit_model_rejects_updates_and_deletes() -> None:
    assert event.contains(AuditEvent, "before_update", _reject_audit_mutation)
    assert event.contains(AuditEvent, "before_delete", _reject_audit_mutation)
    with pytest.raises(TypeError, match="append-only"):
        _reject_audit_mutation()


async def test_audit_queries_are_scoped_to_the_authorized_business() -> None:
    repository = FakeAuditRepository()
    manager = AuditManager(
        FakeAuth(),  # type: ignore[arg-type]
        FakeBusinesses(),  # type: ignore[arg-type]
        repository,  # type: ignore[arg-type]
    )
    filters = {
        "interface": None,
        "action": None,
        "outcome": None,
        "target_type": None,
        "actor_user_id": None,
        "occurred_from": None,
        "occurred_to": None,
        "limit": 50,
        "offset": 0,
    }

    await manager.list_for_rest(AsyncMock(), "valid", **filters)
    assert repository.queried_business_id == 11

    principal = MCPPrincipal(
        user_id=7,
        business_id=999,
        scopes=frozenset({"audit:read"}),
        grant_id="grant",
    )
    with pytest.raises(BusinessRequiredError):
        await manager.list_for_principal(AsyncMock(), principal, **filters)


class FakeAuditManager:
    def __init__(self) -> None:
        self.denied = False

    async def list_for_rest(
        self, *_args: object, **_kwargs: object
    ) -> tuple[list[AuditEvent], int]:
        return (
            [
                AuditEvent(
                    id=1,
                    business_id=11,
                    actor_user_id=7,
                    interface=ActionOrigin.REST,
                    action="project.create",
                    target_type="project",
                    target_id=3,
                    outcome="success",
                    occurred_at=datetime.now(UTC),
                )
            ],
            1,
        )

    async def list_for_principal(
        self, *_args: object, **_kwargs: object
    ) -> tuple[list[AuditEvent], int]:
        return await self.list_for_rest()

    async def record_denied_for_principal(
        self, *_args: object, **_kwargs: object
    ) -> None:
        self.denied = True


class FakeSessions:
    @asynccontextmanager
    async def session(self) -> AsyncIterator[object]:
        yield object()


async def fake_session() -> AsyncIterator[object]:
    yield object()


async def test_rest_audit_query_returns_compact_events() -> None:
    app = create_app()
    app.dependency_overrides[get_session] = fake_session
    app.dependency_overrides[get_audit_manager] = FakeAuditManager

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"projectbridge_access": "valid"},
    ) as client:
        response = await client.get("/api/v1/audit-events?limit=10")

    assert response.status_code == 200
    assert response.json()["items"][0]["action"] == "project.create"
    assert response.json()["items"][0]["business_id"] == 11


async def test_mcp_audit_query_requires_dedicated_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = MCPServer("audit-tools-test")
    register_audit_tools(
        server,
        FakeSessions(),  # type: ignore[arg-type]
        FakeAuditManager(),  # type: ignore[arg-type]
    )
    principal = MCPPrincipal(
        user_id=7,
        business_id=11,
        scopes=frozenset({"audit:read"}),
        grant_id="grant",
    )
    requested_scopes: list[tuple[str, ...]] = []

    def require(*scopes: str) -> MCPPrincipal:
        requested_scopes.append(scopes)
        return principal

    monkeypatch.setattr("app.mcp.audit_tools.require_mcp_principal", require)
    async with Client(server) as client:
        result = await client.call_tool("list_audit_events", {"input": {}})

    assert requested_scopes == [()]
    assert result.structured_content["items"][0]["action"] == "project.create"


async def test_mcp_audit_query_records_scope_denial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = MCPServer("audit-denial-test")
    manager = FakeAuditManager()
    register_audit_tools(
        server,
        FakeSessions(),  # type: ignore[arg-type]
        manager,  # type: ignore[arg-type]
    )
    principal = MCPPrincipal(
        user_id=7,
        business_id=11,
        scopes=frozenset(),
        grant_id="grant",
    )
    monkeypatch.setattr(
        "app.mcp.audit_tools.require_mcp_principal", lambda: principal
    )

    async with Client(server) as client:
        result = await client.call_tool("list_audit_events", {"input": {}})

    assert result.is_error is True
    assert manager.denied is True
