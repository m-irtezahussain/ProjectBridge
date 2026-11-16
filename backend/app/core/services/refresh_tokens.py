import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.config import Settings
from app.models import RefreshToken


@dataclass(frozen=True)
class IssuedRefreshToken:
    raw_token: str
    record: RefreshToken


class RefreshTokenService:
    """Create opaque 256-bit refresh tokens while persisting only SHA-256 hashes."""

    def __init__(self, settings: Settings) -> None:
        self._secret = settings.jwt_secret.encode()
        self._sliding_lifetime = timedelta(days=settings.refresh_sliding_days)
        self._absolute_lifetime = timedelta(days=settings.refresh_absolute_days)

    @staticmethod
    def hash_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()

    def issue(
        self,
        user_id: int,
        *,
        family_id: str | None = None,
        absolute_expires_at: datetime | None = None,
    ) -> IssuedRefreshToken:
        now = datetime.now(UTC)
        absolute_expiry = absolute_expires_at or now + self._absolute_lifetime
        raw_token = secrets.token_urlsafe(32)
        record = RefreshToken(
            user_id=user_id,
            token_hash=self.hash_token(raw_token),
            family_id=family_id or str(uuid4()),
            expires_at=min(now + self._sliding_lifetime, absolute_expiry),
            absolute_expires_at=absolute_expiry,
        )
        return IssuedRefreshToken(raw_token=raw_token, record=record)

    def rotate(
        self,
        predecessor_raw_token: str,
        user_id: int,
        *,
        family_id: str,
        absolute_expires_at: datetime,
    ) -> IssuedRefreshToken:
        """Derive a stable replacement so near-simultaneous retries are idempotent."""

        digest = hmac.new(
            self._secret,
            f"refresh-rotation:{predecessor_raw_token}".encode(),
            hashlib.sha256,
        ).digest()
        raw_token = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        now = datetime.now(UTC)
        record = RefreshToken(
            user_id=user_id,
            token_hash=self.hash_token(raw_token),
            family_id=family_id,
            expires_at=min(now + self._sliding_lifetime, absolute_expires_at),
            absolute_expires_at=absolute_expires_at,
        )
        return IssuedRefreshToken(raw_token=raw_token, record=record)
