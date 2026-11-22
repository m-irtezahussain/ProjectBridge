from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from mcp.server.auth.provider import AccessToken

from app.config import Settings
from app.core.services.mcp_auth import (
    MCPAuthenticationError,
    MCPAuthenticationService,
    MCPAuthorizationError,
)
from app.core.services.mcp_oauth import MCPTokenService
from app.mcp.auth import (
    MCPDatabaseSessions,
    ProjectBridgeTokenVerifier,
    require_mcp_principal,
)
from app.models import Business, OAuthGrant, User


def make_settings() -> Settings:
    return Settings(
        APP_ENV="test",
        APP_JWT_SECRET="web-secret-that-is-at-least-thirty-two-characters",
        APP_MCP_JWT_SECRET="mcp-secret-that-is-at-least-thirty-two-characters",
        APP_MCP_ISSUER="https://api.projectbridge.test",
        APP_MCP_RESOURCE="https://api.projectbridge.test/mcp/",
    )


class FakeOAuth:
    def __init__(self, grant: OAuthGrant | None) -> None:
        self.grant = grant

    async def get_grant(self, _session: object, grant_id: str) -> OAuthGrant | None:
        if self.grant is not None and self.grant.id == grant_id:
            return self.grant
        return None


class FakeUsers:
    def __init__(self, user: User | None) -> None:
        self.user = user

    async def get_by_id(self, _session: object, user_id: int) -> User | None:
        if self.user is not None and self.user.id == user_id:
            return self.user
        return None


class FakeBusinesses:
    def __init__(self, business: Business | None) -> None:
        self.business = business

    async def get_for_owner(
        self, _session: object, owner_id: int
    ) -> Business | None:
        if self.business is not None and self.business.owned_by == owner_id:
            return self.business
        return None


def make_authentication(
    *,
    grant: OAuthGrant | None = None,
    include_user: bool = True,
    include_business: bool = True,
) -> tuple[MCPAuthenticationService, MCPTokenService, OAuthGrant]:
    settings = make_settings()
    active_grant = grant or OAuthGrant(
        id="grant-id",
        user_id=7,
        client_id="chatgpt-client",
        resource=settings.mcp_resource,
        scopes="offline_access projects:read tasks:read",
    )
    owner = User(
        id=7,
        full_name="Maya Chen",
        email="maya@example.com",
        password_hash="$argon2id$valid-test-password-hash",
    )
    owned_business = Business(
        id=11,
        name="Acme Studio",
        owned_by=owner.id,
    )
    tokens = MCPTokenService(settings)
    service = MCPAuthenticationService(
        settings,
        tokens,
        oauth=FakeOAuth(active_grant),  # type: ignore[arg-type]
        users=FakeUsers(owner if include_user else None),  # type: ignore[arg-type]
        businesses=FakeBusinesses(  # type: ignore[arg-type]
            owned_business if include_business else None
        ),
    )
    return service, tokens, active_grant


def issue_token(tokens: MCPTokenService, grant: OAuthGrant) -> str:
    return tokens.issue_access_token(
        user_id=grant.user_id,
        grant_id=grant.id,
        client_id=grant.client_id,
        scopes="projects:read tasks:read",
    )


async def test_authentication_resolves_server_side_principal() -> None:
    service, tokens, grant = make_authentication()

    result = await service.authenticate(
        object(),  # type: ignore[arg-type]
        issue_token(tokens, grant),
        required_scopes=["projects:read"],
    )

    assert result.principal.user_id == 7
    assert result.principal.business_id == 11
    assert result.principal.grant_id == "grant-id"
    assert result.principal.scopes == {"projects:read", "tasks:read"}
    assert result.client_id == "chatgpt-client"
    assert result.expires_at > int(datetime.now(UTC).timestamp())


async def test_authentication_rejects_revoked_or_scope_escalated_grants() -> None:
    service, tokens, grant = make_authentication()
    grant.revoked_at = datetime.now(UTC)
    with pytest.raises(MCPAuthenticationError):
        await service.authenticate(
            object(),  # type: ignore[arg-type]
            issue_token(tokens, grant),
        )

    grant.revoked_at = None
    grant.scopes = "projects:read"
    with pytest.raises(MCPAuthenticationError):
        await service.authenticate(
            object(),  # type: ignore[arg-type]
            issue_token(tokens, grant),
        )


async def test_authentication_rejects_wrong_audience_and_expired_tokens() -> None:
    service, tokens, grant = make_authentication()
    settings = make_settings()
    valid = issue_token(tokens, grant)
    header, payload, signature = valid.split(".")
    replacement = "A" if signature[0] != "A" else "B"
    tampered = f"{header}.{payload}.{replacement}{signature[1:]}"
    with pytest.raises(MCPAuthenticationError):
        await service.authenticate(
            object(),  # type: ignore[arg-type]
            tampered,
        )

    wrong_audience_settings = settings.model_copy(
        update={"mcp_resource": "https://api.projectbridge.test/another-resource"}
    )
    wrong_audience = issue_token(MCPTokenService(wrong_audience_settings), grant)
    with pytest.raises(MCPAuthenticationError):
        await service.authenticate(
            object(),  # type: ignore[arg-type]
            wrong_audience,
        )

    now = datetime.now(UTC)
    expired = jwt.encode(
        {
            "iss": settings.mcp_issuer,
            "aud": settings.mcp_resource,
            "sub": str(grant.user_id),
            "grant_id": grant.id,
            "client_id": grant.client_id,
            "scope": "projects:read",
            "iat": now - timedelta(minutes=10),
            "exp": now - timedelta(minutes=5),
            "jti": "expired-token",
        },
        settings.mcp_jwt_secret,
        algorithm="HS256",
        headers={"typ": "at+jwt"},
    )
    with pytest.raises(MCPAuthenticationError):
        await service.authenticate(
            object(),  # type: ignore[arg-type]
            expired,
        )


async def test_authentication_rejects_claims_that_no_longer_match_grant() -> None:
    service, tokens, grant = make_authentication()
    token = issue_token(tokens, grant)
    grant.client_id = "another-client"

    with pytest.raises(MCPAuthenticationError):
        await service.authenticate(
            object(),  # type: ignore[arg-type]
            token,
        )


async def test_authentication_rejects_missing_scope_user_or_business() -> None:
    service, tokens, grant = make_authentication()
    token = issue_token(tokens, grant)
    with pytest.raises(MCPAuthorizationError):
        await service.authenticate(
            object(),  # type: ignore[arg-type]
            token,
            required_scopes=["projects:write"],
        )

    missing_user, missing_user_tokens, missing_user_grant = make_authentication(
        include_user=False
    )
    with pytest.raises(MCPAuthenticationError):
        await missing_user.authenticate(
            object(),  # type: ignore[arg-type]
            issue_token(missing_user_tokens, missing_user_grant),
        )

    missing_business, missing_business_tokens, missing_business_grant = (
        make_authentication(include_business=False)
    )
    with pytest.raises(MCPAuthenticationError):
        await missing_business.authenticate(
            object(),  # type: ignore[arg-type]
            issue_token(missing_business_tokens, missing_business_grant),
        )


async def test_token_verifier_exposes_only_server_resolved_identity() -> None:
    service, tokens, grant = make_authentication()
    sessions = MCPDatabaseSessions()
    verifier = ProjectBridgeTokenVerifier(make_settings(), service, sessions)

    @asynccontextmanager
    async def session_factory() -> AsyncIterator[object]:
        yield object()

    sessions.configure(session_factory)  # type: ignore[arg-type]
    access = await verifier.verify_token(issue_token(tokens, grant))

    assert access is not None
    assert access.subject == "7"
    assert access.resource == make_settings().mcp_resource
    assert access.claims == {
        "user_id": 7,
        "business_id": 11,
        "grant_id": "grant-id",
    }


def test_tool_scope_helper_reconstructs_principal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    access = AccessToken(
        token="not-exposed-to-tool-inputs",
        client_id="chatgpt-client",
        scopes=["projects:read"],
        subject="7",
        claims={"user_id": 7, "business_id": 11, "grant_id": "grant-id"},
    )
    monkeypatch.setattr("app.mcp.auth.get_access_token", lambda: access)

    principal = require_mcp_principal("projects:read")

    assert principal.user_id == 7
    assert principal.business_id == 11
    with pytest.raises(MCPAuthorizationError):
        require_mcp_principal("projects:write")
