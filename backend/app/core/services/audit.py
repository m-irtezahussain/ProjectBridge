from collections.abc import Mapping, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.mcp_auth import AuthenticatedPrincipal
from app.models import ActionOrigin, AuditEvent
from app.repositories.audit import AuditRepository

_REDACTED_KEYS = (
    "password",
    "secret",
    "token",
    "authorization",
    "api_key",
    "apikey",
    "cookie",
    "credential",
)


def scrub_audit_details(value: object) -> object:
    """Recursively redact secret-bearing fields before persistence."""

    if isinstance(value, Mapping):
        return {
            str(key): (
                "[REDACTED]"
                if any(fragment in str(key).casefold() for fragment in _REDACTED_KEYS)
                else scrub_audit_details(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [scrub_audit_details(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class AuditService:
    """Shared append-only audit writer for REST, MCP, and workers."""

    def __init__(self, repository: AuditRepository | None = None) -> None:
        self._repository = repository or AuditRepository()

    def record(
        self,
        session: AsyncSession,
        *,
        business_id: int,
        actor_user_id: int | None,
        interface: ActionOrigin,
        action: str,
        target_type: str,
        target_id: int | None,
        outcome: str,
        details: dict[str, object] | None = None,
    ) -> None:
        scrubbed = scrub_audit_details(details) if details is not None else None
        self._repository.add(
            session,
            AuditEvent(
                business_id=business_id,
                actor_user_id=actor_user_id,
                interface=interface,
                action=action,
                target_type=target_type,
                target_id=target_id,
                outcome=outcome,
                details=scrubbed if isinstance(scrubbed, dict) else None,
            ),
        )

    def add(
        self,
        session: AsyncSession,
        *,
        principal: AuthenticatedPrincipal,
        tool_name: str,
        target_type: str,
        target_id: int | None,
        outcome: str,
    ) -> None:
        """Compatibility adapter for existing MCP manager call sites."""

        self.record(
            session,
            business_id=principal.business_id,
            actor_user_id=principal.user_id,
            interface=principal.origin,
            action=tool_name,
            target_type=target_type,
            target_id=target_id,
            outcome=outcome,
        )
