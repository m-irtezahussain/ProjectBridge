from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.mcp_auth import MCPPrincipal
from app.core.services.mcp_mutations import hash_idempotency_key
from app.models import MCPAuditEvent, MCPIdempotencyRecord


@dataclass(frozen=True)
class IdempotencyClaim:
    record: MCPIdempotencyRecord
    is_new: bool


class MCPIdempotencyRepository:
    """Atomically claim or load a tenant-scoped MCP idempotency key."""

    async def claim(
        self,
        session: AsyncSession,
        *,
        principal: MCPPrincipal,
        tool_name: str,
        idempotency_key: str,
        fingerprint: str,
    ) -> IdempotencyClaim:
        key_hash = hash_idempotency_key(idempotency_key)
        statement = (
            insert(MCPIdempotencyRecord)
            .values(
                business_id=principal.business_id,
                user_id=principal.user_id,
                grant_id=principal.grant_id,
                tool_name=tool_name,
                key_hash=key_hash,
                request_fingerprint=fingerprint,
                state="started",
            )
            .on_conflict_do_nothing(
                constraint="uq_mcp_idempotency_scope_key"
            )
            .returning(MCPIdempotencyRecord.id)
        )
        record_id = await session.scalar(statement)
        if record_id is not None:
            record = await session.get(MCPIdempotencyRecord, record_id)
            if record is None:
                raise RuntimeError("Claimed idempotency record was not found")
            return IdempotencyClaim(record=record, is_new=True)
        record = await session.scalar(
            select(MCPIdempotencyRecord)
            .where(
                MCPIdempotencyRecord.business_id == principal.business_id,
                MCPIdempotencyRecord.grant_id == principal.grant_id,
                MCPIdempotencyRecord.tool_name == tool_name,
                MCPIdempotencyRecord.key_hash == key_hash,
            )
            .with_for_update()
        )
        if record is None:
            raise RuntimeError("Existing idempotency record was not found")
        return IdempotencyClaim(record=record, is_new=False)

    def complete(
        self,
        record: MCPIdempotencyRecord,
        *,
        result_type: str,
        result_id: int,
        response_body: dict[str, object],
    ) -> None:
        record.state = "completed"
        record.result_type = result_type
        record.result_id = result_id
        record.response_body = response_body
        record.completed_at = datetime.now(UTC)


class MCPAuditRepository:
    """Append immutable audit events for MCP write attempts."""

    def add(
        self,
        session: AsyncSession,
        *,
        principal: MCPPrincipal,
        tool_name: str,
        target_type: str,
        target_id: int | None,
        outcome: str,
    ) -> None:
        session.add(
            MCPAuditEvent(
                business_id=principal.business_id,
                user_id=principal.user_id,
                grant_id=principal.grant_id,
                tool_name=tool_name,
                target_type=target_type,
                target_id=target_id,
                outcome=outcome,
            )
        )
