from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass


class ResourceCursorError(ValueError):
    pass


@dataclass(frozen=True)
class ResourceCursor:
    last_id: int


class ResourceCursorCodec:
    """Signed, opaque cursor bound to a tenant and resource collection."""

    def __init__(self, secret: str) -> None:
        self._secret = secret.encode()

    def encode(
        self,
        *,
        kind: str,
        business_id: int,
        parent_id: int | None,
        last_id: int,
    ) -> str:
        payload = {
            "v": 1,
            "k": kind,
            "b": business_id,
            "p": parent_id,
            "i": last_id,
        }
        body = self._encode_bytes(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        )
        signature = self._sign(body)
        return f"{body}.{signature}"

    def decode(
        self,
        value: str | None,
        *,
        kind: str,
        business_id: int,
        parent_id: int | None,
    ) -> ResourceCursor | None:
        if value is None:
            return None
        if len(value) > 1000:
            raise ResourceCursorError("Invalid resource cursor")
        try:
            body, supplied_signature = value.split(".", 1)
        except ValueError as error:
            raise ResourceCursorError("Invalid resource cursor") from error
        expected_signature = self._sign(body)
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise ResourceCursorError("Invalid resource cursor")
        try:
            payload = json.loads(self._decode_bytes(body))
        except (ValueError, json.JSONDecodeError) as error:
            raise ResourceCursorError("Invalid resource cursor") from error
        if not isinstance(payload, dict) or payload != {
            "v": 1,
            "k": kind,
            "b": business_id,
            "p": parent_id,
            "i": payload.get("i"),
        }:
            raise ResourceCursorError("Resource cursor does not match this collection")
        last_id = payload.get("i")
        if not isinstance(last_id, int) or isinstance(last_id, bool) or last_id < 1:
            raise ResourceCursorError("Invalid resource cursor")
        return ResourceCursor(last_id=last_id)

    def _sign(self, body: str) -> str:
        digest = hmac.new(self._secret, body.encode(), hashlib.sha256).digest()
        return self._encode_bytes(digest[:18])

    @staticmethod
    def _encode_bytes(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode().rstrip("=")

    @staticmethod
    def _decode_bytes(value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
