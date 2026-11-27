from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.services.mcp_oauth import (
    MCPAccessClaims,
    MCPTokenService,
    OAuthProtocolError,
    parse_scopes,
)
from app.models import ActionOrigin
from app.repositories.businesses import BusinessRepository
from app.repositories.oauth import OAuthRepository
from app.repositories.users import UserRepository


class MCPAuthenticationError(ValueError):
    """Raised when an MCP credential cannot be trusted."""


class MCPAuthorizationError(ValueError):
    """Raised when a valid MCP credential lacks a required scope."""


@dataclass(frozen=True)
class MCPPrincipal:
    """Server-resolved tenant identity shared by REST and MCP entry points."""

    user_id: int
    business_id: int
    scopes: frozenset[str]
    grant_id: str
    origin: ActionOrigin = ActionOrigin.MCP


AuthenticatedPrincipal = MCPPrincipal


@dataclass(frozen=True)
class MCPAuthenticationResult:
    """Verified request identity plus protocol fields needed by the MCP SDK."""

    principal: MCPPrincipal
    client_id: str
    expires_at: int


class MCPAuthenticationService:
    """Authenticate an MCP token and resolve its owner-scoped business identity."""

    def __init__(
        self,
        settings: Settings,
        tokens: MCPTokenService,
        oauth: OAuthRepository | None = None,
        users: UserRepository | None = None,
        businesses: BusinessRepository | None = None,
    ) -> None:
        self._settings = settings
        self._tokens = tokens
        self._oauth = oauth or OAuthRepository()
        self._users = users or UserRepository()
        self._businesses = businesses or BusinessRepository()

    async def authenticate(
        self,
        session: AsyncSession,
        bearer_token: str,
        *,
        required_scopes: Iterable[str] = (),
    ) -> MCPAuthenticationResult:
        claims = self._decode_token(bearer_token)
        grant = await self._oauth.get_grant(session, claims.grant_id)
        if (
            grant is None
            or grant.revoked_at is not None
            or grant.user_id != claims.user_id
            or grant.client_id != claims.client_id
            or grant.resource != self._settings.mcp_resource
        ):
            raise MCPAuthenticationError("Invalid or expired MCP credential")
        try:
            granted_scopes = parse_scopes(grant.scopes)
        except OAuthProtocolError as exc:
            raise MCPAuthenticationError("Invalid or expired MCP credential") from exc
        if not claims.scopes.issubset(granted_scopes):
            raise MCPAuthenticationError("Invalid or expired MCP credential")

        user = await self._users.get_by_id(session, claims.user_id)
        if user is None:
            raise MCPAuthenticationError("Invalid or expired MCP credential")
        business = await self._businesses.get_for_owner(session, user.id)
        if business is None:
            raise MCPAuthenticationError("Invalid or expired MCP credential")

        required = frozenset(required_scopes)
        if not required.issubset(claims.scopes):
            raise MCPAuthorizationError("Insufficient MCP scope")
        return MCPAuthenticationResult(
            principal=MCPPrincipal(
                user_id=user.id,
                business_id=business.id,
                scopes=claims.scopes,
                grant_id=grant.id,
            ),
            client_id=claims.client_id,
            expires_at=claims.expires_at,
        )

    def _decode_token(self, token: str) -> MCPAccessClaims:
        try:
            return self._tokens.decode_access_token(token)
        except OAuthProtocolError as exc:
            raise MCPAuthenticationError("Invalid or expired MCP credential") from exc
