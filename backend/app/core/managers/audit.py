from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.managers.auth import AuthenticationError, AuthManager
from app.core.managers.projects import BusinessRequiredError
from app.core.services.audit import AuditService
from app.core.services.mcp_auth import MCPPrincipal
from app.models import ActionOrigin, AuditEvent
from app.repositories.audit import AuditRepository
from app.repositories.businesses import BusinessRepository


class AuditManager:
    """Authorize tenant-scoped audit queries for REST and MCP."""

    def __init__(
        self,
        auth: AuthManager,
        businesses: BusinessRepository | None = None,
        audit: AuditRepository | None = None,
    ) -> None:
        self._auth = auth
        self._businesses = businesses or BusinessRepository()
        self._audit = audit or AuditRepository()
        self._writer = AuditService(self._audit)

    async def list_for_rest(
        self,
        session: AsyncSession,
        access_token: str | None,
        *,
        interface: ActionOrigin | None,
        action: str | None,
        outcome: str | None,
        target_type: str | None,
        actor_user_id: int | None,
        occurred_from: datetime | None,
        occurred_to: datetime | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AuditEvent], int]:
        user = await self._auth.get_user(session, access_token, "access")
        if user is None:
            raise AuthenticationError("Authentication required")
        business = await self._businesses.get_for_owner(session, user.id)
        if business is None:
            raise BusinessRequiredError("Business registration required")
        result = await self._audit.list_page(
            session,
            business.id,
            interface=interface,
            action=action,
            outcome=outcome,
            target_type=target_type,
            actor_user_id=actor_user_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            limit=limit,
            offset=offset,
        )
        self._writer.record(
            session,
            business_id=business.id,
            actor_user_id=user.id,
            interface=ActionOrigin.REST,
            action="audit.query",
            target_type="business",
            target_id=business.id,
            outcome="success",
            details={"limit": limit, "offset": offset},
        )
        await session.commit()
        return result

    async def list_for_principal(
        self,
        session: AsyncSession,
        principal: MCPPrincipal,
        *,
        interface: ActionOrigin | None,
        action: str | None,
        outcome: str | None,
        target_type: str | None,
        actor_user_id: int | None,
        occurred_from: datetime | None,
        occurred_to: datetime | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AuditEvent], int]:
        business = await self._businesses.get_for_owner(session, principal.user_id)
        if business is None or business.id != principal.business_id:
            raise BusinessRequiredError("Business registration required")
        result = await self._audit.list_page(
            session,
            principal.business_id,
            interface=interface,
            action=action,
            outcome=outcome,
            target_type=target_type,
            actor_user_id=actor_user_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            limit=limit,
            offset=offset,
        )
        self._writer.record(
            session,
            business_id=principal.business_id,
            actor_user_id=principal.user_id,
            interface=ActionOrigin.MCP,
            action="audit.query",
            target_type="business",
            target_id=principal.business_id,
            outcome="success",
            details={"limit": limit, "offset": offset},
        )
        await session.commit()
        return result

    async def record_denied_for_principal(
        self,
        session: AsyncSession,
        principal: MCPPrincipal,
        *,
        action: str,
        required_permission: str,
    ) -> None:
        business = await self._businesses.get_for_owner(session, principal.user_id)
        if business is None or business.id != principal.business_id:
            return
        self._writer.record(
            session,
            business_id=principal.business_id,
            actor_user_id=principal.user_id,
            interface=ActionOrigin.MCP,
            action=action,
            target_type="business",
            target_id=principal.business_id,
            outcome="denied",
            details={"required_permission": required_permission},
        )
        await session.commit()
