from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.core.services.mcp_auth import MCPPrincipal
from app.core.services.mcp_mutations import hash_idempotency_key
from app.models import MCPIdempotencyRecord
from app.repositories.mcp_operations import MCPIdempotencyRepository


def principal() -> MCPPrincipal:
    return MCPPrincipal(
        user_id=7,
        business_id=11,
        scopes=frozenset({"projects:write"}),
        grant_id="grant-id",
    )


async def test_expired_started_claim_is_recovered_with_a_fresh_lease() -> None:
    now = datetime.now(UTC)
    record = MCPIdempotencyRecord(
        id=1,
        business_id=11,
        user_id=7,
        grant_id="grant-id",
        tool_name="update_project",
        key_hash=hash_idempotency_key("retry-key"),
        request_fingerprint="fingerprint",
        state="started",
        recovery_point="started",
        attempt_count=1,
        locked_until=now - timedelta(seconds=1),
        expires_at=now + timedelta(days=7),
        updated_at=now - timedelta(minutes=1),
    )
    session = AsyncMock()
    cleanup_result = MagicMock()
    cleanup_result.rowcount = 0
    session.execute.return_value = cleanup_result
    session.scalar.side_effect = [None, record]
    repository = MCPIdempotencyRepository(lease_seconds=60)

    claim = await repository.claim(
        session,
        principal=principal(),
        tool_name="update_project",
        idempotency_key="retry-key",
        fingerprint="fingerprint",
    )

    assert claim.is_new is True
    assert claim.recovered is True
    assert record.attempt_count == 2
    assert record.locked_until is not None
    assert record.locked_until > now


async def test_expired_records_are_deleted_in_bounded_batches() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.rowcount = 17
    session.execute.return_value = result
    repository = MCPIdempotencyRepository(cleanup_batch=25)

    deleted = await repository.cleanup_expired(session)

    assert deleted == 17
    statement = session.execute.await_args.args[0]
    assert "LIMIT" in str(statement)
