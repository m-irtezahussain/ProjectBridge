import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.core.services.mcp_auth import (
    MCPAuthenticationError,
    MCPAuthenticationService,
    MCPAuthorizationError,
    MCPPrincipal,
)

logger = logging.getLogger(__name__)


class MCPDatabaseSessions:
    """Lifecycle-bound database sessions shared by MCP auth and tools."""

    def __init__(self) -> None:
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    def configure(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        self._session_factory = session_factory

    def clear(self) -> None:
        self._session_factory = None

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        if self._session_factory is None:
            raise RuntimeError("MCP database sessions are not configured")
        async with self._session_factory() as session:
            yield session


class ProjectBridgeTokenVerifier:
    """Adapt ProjectBridge's tenant-aware authentication to the MCP SDK."""

    def __init__(
        self,
        settings: Settings,
        authentication: MCPAuthenticationService,
        sessions: MCPDatabaseSessions,
    ) -> None:
        self._settings = settings
        self._authentication = authentication
        self._sessions = sessions

    async def verify_token(self, token: str) -> AccessToken | None:
        """Fail closed unless the token, grant, user, and owned business are valid."""

        try:
            async with self._sessions.session() as session:
                authenticated = await self._authentication.authenticate(session, token)
        except (MCPAuthenticationError, MCPAuthorizationError):
            return None
        except Exception:
            logger.exception("MCP credential verification failed")
            return None

        principal = authenticated.principal
        return AccessToken(
            token=token,
            client_id=authenticated.client_id,
            scopes=sorted(principal.scopes),
            expires_at=authenticated.expires_at,
            resource=self._settings.mcp_resource,
            subject=str(principal.user_id),
            claims={
                "user_id": principal.user_id,
                "business_id": principal.business_id,
                "grant_id": principal.grant_id,
            },
        )


def require_mcp_principal(*required_scopes: str) -> MCPPrincipal:
    """Return the current request principal after enforcing tool-specific scopes."""

    access_token = get_access_token()
    if access_token is None or access_token.claims is None:
        raise MCPAuthenticationError("MCP authentication required")
    scopes = frozenset(access_token.scopes)
    if not frozenset(required_scopes).issubset(scopes):
        raise MCPAuthorizationError("Insufficient MCP scope")
    try:
        user_id = int(access_token.claims["user_id"])
        business_id = int(access_token.claims["business_id"])
        grant_id = str(access_token.claims["grant_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise MCPAuthenticationError("Invalid MCP request identity") from exc
    if user_id < 1 or business_id < 1 or not grant_id:
        raise MCPAuthenticationError("Invalid MCP request identity")
    return MCPPrincipal(
        user_id=user_id,
        business_id=business_id,
        scopes=scopes,
        grant_id=grant_id,
    )
