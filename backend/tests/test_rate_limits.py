from unittest.mock import AsyncMock

import pytest

from app.core.services.rate_limits import AuthRateLimiter, RateLimitExceededError


async def test_rate_limiter_persists_attempt() -> None:
    session = AsyncMock()
    session.scalar.return_value = 3

    await AuthRateLimiter("test-secret").consume(
        session,
        bucket="login-email",
        identity="maya@example.com",
        limit=10,
    )

    session.scalar.assert_awaited_once()
    session.commit.assert_awaited_once()


async def test_rate_limiter_rejects_attempt_over_limit() -> None:
    session = AsyncMock()
    session.scalar.return_value = 11

    with pytest.raises(RateLimitExceededError, match="Too many requests"):
        await AuthRateLimiter("test-secret").consume(
            session,
            bucket="login-email",
            identity="maya@example.com",
            limit=10,
        )

    session.commit.assert_awaited_once()
