import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import BaseModel


class IdempotencyConflictError(ValueError):
    pass


class IdempotencyInProgressError(ValueError):
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
