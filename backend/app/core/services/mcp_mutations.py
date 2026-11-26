from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.repositories.mcp_operations import IdempotencyClaim


class IdempotencyConflictError(ValueError):
    pass


class IdempotencyInProgressError(ValueError):
    pass


class MutationVersionConflictError(ValueError):
    pass


@dataclass(frozen=True)
class MCPMutationResult[EntityT]:
    entity: EntityT
    replayed: bool


def hash_idempotency_key(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def request_fingerprint(
    tool_name: str, payload: BaseModel | Mapping[str, object]
) -> str:
    serialized = (
        payload.model_dump(mode="json")
        if isinstance(payload, BaseModel)
        else dict(payload)
    )
    canonical = json.dumps(
        {"tool": tool_name, "payload": serialized},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def completed_idempotency_replay(
    claim: IdempotencyClaim,
    *,
    fingerprint: str,
    result_type: str,
) -> dict[str, object] | None:
    if claim.record.request_fingerprint != fingerprint:
        raise IdempotencyConflictError(
            "Idempotency key was already used with different input"
        )
    if claim.is_new:
        return None
    if (
        claim.record.state != "completed"
        or claim.record.result_type != result_type
        or claim.record.result_id is None
        or claim.record.response_body is None
    ):
        raise IdempotencyInProgressError(
            "The mutation is still in progress; retry with the same idempotency key"
        )
    return claim.record.response_body
