from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.config import Settings
from app.core.managers.auth import (
    AuthenticationError,
    AuthManager,
    BusinessAlreadyRegisteredError,
)
from app.core.services.refresh_tokens import RefreshTokenService
from app.core.services.tokens import TokenService
from app.models import Business, RefreshToken, User
from app.schemas import BusinessCreate, UserCreate


class FakeUsers:
    def __init__(self) -> None:
        self.items: dict[int, User] = {}

    async def get_by_email(self, _session: object, email: str) -> User | None:
        return next((user for user in self.items.values() if user.email == email), None)

    async def get_by_id(self, _session: object, user_id: int) -> User | None:
        return self.items.get(user_id)

    def add(self, _session: object, user: User) -> None:
        user.id = len(self.items) + 1
        user.owned_businesses = []
        self.items[user.id] = user


class FakeBusinesses:
    def __init__(self, users: FakeUsers) -> None:
        self.items: dict[int, Business] = {}
        self.users = users

    async def get_for_owner(self, _session: object, owner_id: int) -> Business | None:
        return self.items.get(owner_id)

    def add(self, _session: object, business: Business) -> None:
        business.id = len(self.items) + 1
        self.items[business.owned_by] = business
        self.users.items[business.owned_by].owned_businesses.append(business)


class FakeRefreshTokens:
    def __init__(self) -> None:
        self.items: dict[str, RefreshToken] = {}

    async def get_for_update(
        self, _session: object, token_hash: str
    ) -> RefreshToken | None:
        return self.items.get(token_hash)

    def add(self, _session: object, token: RefreshToken) -> None:
        token.id = len(self.items) + 1
        self.items[token.token_hash] = token

    async def revoke_family(
        self, _session: object, family_id: str, revoked_at: datetime
    ) -> None:
        for token in self.items.values():
            if token.family_id == family_id and token.revoked_at is None:
                token.revoked_at = revoked_at

    async def revoke_user(
        self, _session: object, user_id: int, revoked_at: datetime
    ) -> None:
        for token in self.items.values():
            if token.user_id == user_id and token.revoked_at is None:
                token.revoked_at = revoked_at


def make_manager() -> tuple[AuthManager, FakeUsers, FakeRefreshTokens]:
    users = FakeUsers()
    businesses = FakeBusinesses(users)
    refresh_tokens = FakeRefreshTokens()
    settings = Settings(
        APP_ENV="test",
        APP_JWT_SECRET="test-secret-that-is-at-least-thirty-two-characters",
    )
    return (
        AuthManager(
            TokenService(settings),
            RefreshTokenService(settings),
            users,
            businesses,
            refresh_tokens,
        ),
        users,
        refresh_tokens,
    )


async def test_signup_business_registration_and_login_navigation() -> None:
    manager, users, _refresh_tokens = make_manager()
    session = AsyncMock()
    signup = await manager.signup(
        session,
        UserCreate(
            full_name="Maya Chen",
            email="maya@example.com",
            password="a long memorable passphrase",
        ),
    )

    assert signup.next == "/business/register"
    assert signup.token is not None
    before = await manager.session_status(session, None, signup.token)
    assert before.authenticated is True
    assert before.has_business is False

    await manager.register_business(
        session,
        BusinessCreate(name="Acme Studio"),
        None,
        signup.token,
    )
    assert users.items[1].access_token is None

    login = await manager.login(
        session, "maya@example.com", "a long memorable passphrase"
    )
    assert login.next == "/dashboard"
    assert login.refresh_token is not None

    with pytest.raises(BusinessAlreadyRegisteredError):
        await manager.register_business(
            session,
            BusinessCreate(name="Second Business"),
            login.token,
            None,
        )


async def test_duplicate_signup_has_same_public_navigation_without_a_token() -> None:
    manager, _users, _refresh_tokens = make_manager()
    session = AsyncMock()
    data = UserCreate(
        full_name="Maya Chen",
        email="maya@example.com",
        password="a long memorable passphrase",
    )

    created = await manager.signup(session, data)
    duplicate = await manager.signup(session, data)

    assert created.next == duplicate.next == "/business/register"
    assert duplicate.token is None


async def test_refresh_retry_is_idempotent_then_late_reuse_revokes_family() -> None:
    manager, users, refresh_tokens = make_manager()
    session = AsyncMock()
    await manager.signup(
        session,
        UserCreate(
            full_name="Maya Chen",
            email="maya@example.com",
            password="a long memorable passphrase",
        ),
    )
    login = await manager.login(
        session, "maya@example.com", "a long memorable passphrase"
    )
    assert login.refresh_token is not None

    rotated = await manager.refresh(session, login.refresh_token)
    assert rotated.refresh_token is not None
    assert rotated.refresh_token != login.refresh_token

    retry = await manager.refresh(session, login.refresh_token)
    assert retry.refresh_token == rotated.refresh_token
    assert retry.token == rotated.token

    original_record = refresh_tokens.items[
        RefreshTokenService.hash_token(login.refresh_token)
    ]
    original_record.used_at = datetime(2000, 1, 1, tzinfo=UTC)

    with pytest.raises(AuthenticationError, match="Invalid or expired session"):
        await manager.refresh(session, login.refresh_token)

    assert users.items[1].access_token is None
    assert all(token.revoked_at is not None for token in refresh_tokens.items.values())


async def test_expired_refresh_token_is_rejected() -> None:
    manager, _users, refresh_tokens = make_manager()
    session = AsyncMock()
    await manager.signup(
        session,
        UserCreate(
            full_name="Maya Chen",
            email="maya@example.com",
            password="a long memorable passphrase",
        ),
    )
    login = await manager.login(
        session, "maya@example.com", "a long memorable passphrase"
    )
    assert login.refresh_token is not None
    record = next(iter(refresh_tokens.items.values()))
    record.expires_at = datetime(2000, 1, 1, tzinfo=UTC)

    with pytest.raises(AuthenticationError, match="Invalid or expired session"):
        await manager.refresh(session, login.refresh_token)


async def test_logout_revokes_refresh_family_when_access_is_expired() -> None:
    manager, users, refresh_tokens = make_manager()
    session = AsyncMock()
    await manager.signup(
        session,
        UserCreate(
            full_name="Maya Chen",
            email="maya@example.com",
            password="a long memorable passphrase",
        ),
    )
    login = await manager.login(
        session, "maya@example.com", "a long memorable passphrase"
    )
    assert login.refresh_token is not None

    await manager.logout(session, None, None, login.refresh_token)

    assert users.items[1].access_token is None
    assert all(token.revoked_at is not None for token in refresh_tokens.items.values())
