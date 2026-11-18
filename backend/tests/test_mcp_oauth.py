import base64
import hashlib
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.config import Settings
from app.core.managers.oauth import OAuthManager
from app.core.services.mcp_oauth import (
    MCPTokenService,
    OAuthProtocolError,
    validate_redirect_uri,
    verify_pkce,
)
from app.models import (
    Business,
    OAuthAuthorizationCode,
    OAuthClient,
    OAuthGrant,
    OAuthRefreshToken,
)
from app.schemas.oauth import OAuthClientRegistrationRequest


def make_settings() -> Settings:
    return Settings(
        APP_ENV="test",
        APP_JWT_SECRET="web-secret-that-is-at-least-thirty-two-characters",
        APP_MCP_JWT_SECRET="mcp-secret-that-is-at-least-thirty-two-characters",
        APP_MCP_ISSUER="https://api.projectbridge.test",
        APP_MCP_RESOURCE="https://api.projectbridge.test/mcp/",
    )


class FakeOAuthRepository:
    def __init__(self) -> None:
        self.clients: dict[str, OAuthClient] = {}
        self.codes: dict[str, OAuthAuthorizationCode] = {}
        self.grants: dict[str, OAuthGrant] = {}
        self.refresh_tokens: dict[str, OAuthRefreshToken] = {}

    async def get_client(self, _session: object, client_id: str) -> OAuthClient | None:
        return self.clients.get(client_id)

    def add_client(self, _session: object, client: OAuthClient) -> None:
        self.clients[client.client_id] = client

    async def get_code_for_update(
        self, _session: object, code_hash: str
    ) -> OAuthAuthorizationCode | None:
        return self.codes.get(code_hash)

    async def get_grant(self, _session: object, grant_id: str) -> OAuthGrant | None:
        return self.grants.get(grant_id)

    async def get_refresh_for_update(
        self, _session: object, token_hash: str
    ) -> OAuthRefreshToken | None:
        return self.refresh_tokens.get(token_hash)

    def add_grant_and_code(
        self,
        _session: object,
        grant: OAuthGrant,
        code: OAuthAuthorizationCode,
    ) -> None:
        self.grants[grant.id] = grant
        self.codes[code.code_hash] = code

    def add_refresh_token(self, _session: object, token: OAuthRefreshToken) -> None:
        self.refresh_tokens[token.token_hash] = token

    async def revoke_refresh_family(
        self, _session: object, family_id: str, revoked_at: datetime
    ) -> None:
        for token in self.refresh_tokens.values():
            if token.family_id == family_id:
                token.revoked_at = revoked_at

    async def revoke_grant(
        self, _session: object, grant_id: str, revoked_at: datetime
    ) -> None:
        grant = self.grants.get(grant_id)
        if grant is not None:
            grant.revoked_at = revoked_at
        for token in self.refresh_tokens.values():
            if token.grant_id == grant_id:
                token.revoked_at = revoked_at


class FakeBusinesses:
    async def get_for_owner(self, _session: object, owner_id: int) -> Business | None:
        return Business(id=3, name="Acme", owned_by=owner_id)


def make_manager() -> tuple[OAuthManager, FakeOAuthRepository]:
    settings = make_settings()
    oauth = FakeOAuthRepository()
    return (
        OAuthManager(
            settings,
            MCPTokenService(settings),
            oauth=oauth,  # type: ignore[arg-type]
            businesses=FakeBusinesses(),  # type: ignore[arg-type]
        ),
        oauth,
    )


def pkce_pair() -> tuple[str, str]:
    verifier = "a" * 43
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def test_mcp_access_token_is_bound_to_its_own_issuer_audience_and_scopes() -> None:
    service = MCPTokenService(make_settings())
    token = service.issue_access_token(
        user_id=7,
        grant_id="grant-id",
        client_id="client-id",
        scopes="projects:read tasks:read",
    )

    claims = service.decode_access_token(token)

    assert claims.user_id == 7
    assert claims.grant_id == "grant-id"
    assert claims.scopes == {"projects:read", "tasks:read"}


def test_pkce_and_redirect_validation_reject_unsafe_values() -> None:
    verifier, challenge = pkce_pair()
    assert verify_pkce(verifier, challenge) is True
    assert verify_pkce("b" * 43, challenge) is False
    with pytest.raises(OAuthProtocolError, match="loopback"):
        validate_redirect_uri("http://attacker.example/callback", allow_http=True)
    with pytest.raises(OAuthProtocolError, match="safe URL"):
        validate_redirect_uri("https://user:password@example.com/callback", allow_http=False)


async def test_authorization_code_is_single_use_and_refresh_reuse_revokes_grant() -> None:
    manager, oauth = make_manager()
    session = AsyncMock()
    registration = await manager.register_client(
        session,
        OAuthClientRegistrationRequest(
            client_name="ChatGPT",
            redirect_uris=["https://chatgpt.com/connector_platform_oauth_redirect"],
        ),
    )
    verifier, challenge = pkce_pair()
    request = await manager.validate_authorization_request(
        session,
        response_type="code",
        client_id=registration.client_id,
        redirect_uri=registration.redirect_uris[0],
        scope="offline_access projects:read",
        state="opaque-client-state",
        code_challenge=challenge,
        code_challenge_method="S256",
        resource=make_settings().mcp_resource,
    )
    code = await manager.authorize(session, user_id=9, request=request)
    first = await manager.exchange_code(
        session,
        code=code,
        client_id=registration.client_id,
        redirect_uri=registration.redirect_uris[0],
        code_verifier=verifier,
        resource=make_settings().mcp_resource,
    )

    with pytest.raises(OAuthProtocolError, match="authorization code"):
        await manager.exchange_code(
            session,
            code=code,
            client_id=registration.client_id,
            redirect_uri=registration.redirect_uris[0],
            code_verifier=verifier,
            resource=make_settings().mcp_resource,
        )

    rotated = await manager.refresh(
        session,
        refresh_token=first.refresh_token,
        client_id=registration.client_id,
        resource=make_settings().mcp_resource,
        requested_scope=None,
    )
    assert rotated.refresh_token != first.refresh_token

    with pytest.raises(OAuthProtocolError, match="Invalid refresh token"):
        await manager.refresh(
            session,
            refresh_token=first.refresh_token,
            client_id=registration.client_id,
            resource=make_settings().mcp_resource,
            requested_scope=None,
        )
    assert next(iter(oauth.grants.values())).revoked_at is not None


def test_production_configuration_requires_https_and_a_separate_mcp_secret() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        Settings(
            APP_ENV="production",
            APP_JWT_SECRET="web-secret-that-is-at-least-thirty-two-characters",
            APP_MCP_JWT_SECRET="mcp-secret-that-is-at-least-thirty-two-characters",
            APP_MCP_ISSUER="http://api.projectbridge.test",
            APP_MCP_RESOURCE="https://api.projectbridge.test/mcp/",
            APP_WEB_URL="https://projectbridge.test",
        )
