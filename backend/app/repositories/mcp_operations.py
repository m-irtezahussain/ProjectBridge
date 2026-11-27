from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.audit import AuditService
from app.core.services.mcp_auth import AuthenticatedPrincipal
from app.core.services.mcp_mutations import hash_idempotency_key
from app.models import MCPIdempotencyRecord


@dataclass(frozen=True)
class IdempotencyClaim:
    record: MCPIdempotencyRecord
    is_new: bool
    recovered: bool = False


class MCPIdempotencyRepository:
    """Atomically claim or load a tenant-scoped MCP idempotency key."""

    def __init__(
        self,
        lease_seconds: int = 60,
        retention_hours: int = 168,
        cleanup_batch: int = 500,
    ) -> None:
        self._lease = timedelta(seconds=lease_seconds)
        self._retention = timedelta(hours=retention_hours)
        self._cleanup_batch = cleanup_batch

    async def claim(
        self,
        session: AsyncSession,
        *,
        principal: AuthenticatedPrincipal,
        tool_name: str,
        idempotency_key: str,
        fingerprint: str,
    ) -> IdempotencyClaim:
        now = datetime.now(UTC)
        await self.cleanup_expired(session, now=now)
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
                recovery_point="started",
                attempt_count=1,
                locked_until=now + self._lease,
                expires_at=now + self._retention,
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
        if (
            record.state == "started"
            and record.request_fingerprint == fingerprint
            and (record.locked_until is None or record.locked_until <= now)
        ):
            record.locked_until = now + self._lease
            record.expires_at = now + self._retention
            record.attempt_count += 1
            record.updated_at = now
            return IdempotencyClaim(record=record, is_new=True, recovered=True)
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
        record.recovery_point = "completed"
        record.result_type = result_type
        record.result_id = result_id
        record.response_body = response_body
        record.completed_at = datetime.now(UTC)
        record.updated_at = record.completed_at
        record.locked_until = None

    async def cleanup_expired(
        self, session: AsyncSession, *, now: datetime | None = None
    ) -> int:
        cutoff = now or datetime.now(UTC)
        expired_ids = (
            select(MCPIdempotencyRecord.id)
            .where(MCPIdempotencyRecord.expires_at <= cutoff)
            .order_by(MCPIdempotencyRecord.id.asc())
            .limit(self._cleanup_batch)
        )
        result = await session.execute(
            delete(MCPIdempotencyRecord).where(
                MCPIdempotencyRecord.id.in_(expired_ids)
            )
        )
        return int(cast(CursorResult[Any], result).rowcount or 0)


class MCPAuditRepository(AuditService):
    """Backward-compatible name for the shared audit service."""
