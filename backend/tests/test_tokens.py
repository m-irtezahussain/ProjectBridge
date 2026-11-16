from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.config import Settings
from app.core.services.tokens import InvalidTokenError, TokenService


def make_service() -> TokenService:
    return TokenService(
        Settings(
            APP_ENV="test",
            APP_JWT_SECRET="test-secret-that-is-at-least-thirty-two-characters",
            APP_JWT_ISSUER="test-issuer",
            APP_JWT_AUDIENCE="test-audience",
        )
    )


def test_token_round_trip_is_bound_to_type_and_purpose() -> None:
    service = make_service()
    token = service.issue(42, "access")

    assert service.decode(token, "access").user_id == 42
    with pytest.raises(InvalidTokenError):
        service.decode(token, "onboarding")


@pytest.mark.parametrize(
    ("issuer", "audience"),
    [("wrong-issuer", "test-audience"), ("test-issuer", "wrong-audience")],
)
def test_token_rejects_wrong_issuer_or_audience(issuer: str, audience: str) -> None:
    settings = Settings(
        APP_ENV="test",
        APP_JWT_SECRET="test-secret-that-is-at-least-thirty-two-characters",
        APP_JWT_ISSUER="test-issuer",
        APP_JWT_AUDIENCE="test-audience",
    )
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "iss": issuer,
            "aud": audience,
            "sub": "1",
            "purpose": "access",
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "jti": "test-jti",
        },
        settings.jwt_secret,
        algorithm="HS256",
        headers={"typ": "at+jwt"},
    )

    with pytest.raises(InvalidTokenError):
        TokenService(settings).decode(token, "access")


def test_token_rejects_missing_expiry() -> None:
    settings = Settings(
        APP_ENV="test",
        APP_JWT_SECRET="test-secret-that-is-at-least-thirty-two-characters",
    )
    token = jwt.encode(
        {
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "sub": "1",
            "purpose": "access",
            "iat": datetime.now(UTC),
            "jti": "test-jti",
        },
        settings.jwt_secret,
        algorithm="HS256",
        headers={"typ": "at+jwt"},
    )

    with pytest.raises(InvalidTokenError):
        TokenService(settings).decode(token, "access")
