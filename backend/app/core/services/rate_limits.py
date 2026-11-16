import hashlib
import hmac
from datetime import UTC, datetime, timedelta

from sqlalchemy import case
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthRateLimit


class RateLimitExceededError(ValueError):
    pass


class AuthRateLimiter:
    """Fixed-window auth throttling persisted in PostgreSQL for multi-instance safety."""

    def __init__(self, secret: str, window_minutes: int = 15) -> None:
        self._secret = secret.encode()
        self._window = timedelta(minutes=window_minutes)

    def _key(self, bucket: str, identity: str) -> str:
        value = f"{bucket}:{identity}".encode()
        return hmac.new(self._secret, value, hashlib.sha256).hexdigest()

    async def consume(
        self,
        session: AsyncSession,
        *,
        bucket: str,
        identity: str,
        limit: int,
    ) -> None:
        now = datetime.now(UTC)
        expired = AuthRateLimit.window_started_at <= now - self._window
        statement = (
            insert(AuthRateLimit)
            .values(
                key=self._key(bucket, identity),
                attempts=1,
                window_started_at=now,
            )
            .on_conflict_do_update(
                index_elements=[AuthRateLimit.key],
                set_={
                    "attempts": case(
                        (expired, 1), else_=AuthRateLimit.attempts + 1
                    ),
                    "window_started_at": case(
                        (expired, now), else_=AuthRateLimit.window_started_at
                    ),
                },
            )
            .returning(AuthRateLimit.attempts)
        )
        attempts = await session.scalar(statement)
        await session.commit()
        if attempts is None or attempts > limit:
            raise RateLimitExceededError("Too many requests. Try again later.")
