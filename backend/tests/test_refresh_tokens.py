from app.config import Settings
from app.core.services.refresh_tokens import RefreshTokenService


def test_refresh_tokens_are_opaque_and_only_the_hash_is_persisted() -> None:
    service = RefreshTokenService(
        Settings(
            APP_ENV="test",
            APP_JWT_SECRET="test-secret-that-is-at-least-thirty-two-characters",
        )
    )

    issued = service.issue(7)

    assert len(issued.raw_token) >= 43
    assert issued.raw_token != issued.record.token_hash
    assert issued.record.token_hash == service.hash_token(issued.raw_token)
    assert len(issued.record.token_hash) == 64

    first_retry = service.rotate(
        issued.raw_token,
        7,
        family_id=issued.record.family_id,
        absolute_expires_at=issued.record.absolute_expires_at,
    )
    second_retry = service.rotate(
        issued.raw_token,
        7,
        family_id=issued.record.family_id,
        absolute_expires_at=issued.record.absolute_expires_at,
    )
    assert first_retry.raw_token == second_retry.raw_token
