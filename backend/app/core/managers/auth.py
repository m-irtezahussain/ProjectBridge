import hmac
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.audit import AuditService
from app.core.services.passwords import password_service
from app.core.services.refresh_tokens import RefreshTokenService
from app.core.services.tokens import InvalidTokenError, TokenPurpose, TokenService
from app.models import ActionOrigin, Business, User
from app.repositories.businesses import BusinessRepository
from app.repositories.refresh_tokens import RefreshTokenRepository
from app.repositories.users import UserRepository
from app.schemas.auth import SessionResponse
from app.schemas.business import BusinessCreate
from app.schemas.user import UserCreate


class AuthenticationError(ValueError):
    pass


class BusinessAlreadyRegisteredError(ValueError):
    pass


@dataclass(frozen=True)
class AuthResult:
    token: str | None
    refresh_token: str | None
    purpose: TokenPurpose | None
    next: str


class AuthManager:
    """Shared authentication and onboarding rules for REST and future MCP interfaces."""

    refresh_retry_grace = timedelta(seconds=5)

    def __init__(
        self,
        token_service: TokenService,
        refresh_token_service: RefreshTokenService,
        users: UserRepository | None = None,
        businesses: BusinessRepository | None = None,
        refresh_tokens: RefreshTokenRepository | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self._tokens = token_service
        self._refresh_token_service = refresh_token_service
        self._users = users or UserRepository()
        self._businesses = businesses or BusinessRepository()
        self._refresh_tokens = refresh_tokens or RefreshTokenRepository()
        self._audit = audit or AuditService()
        self._dummy_password_hash = password_service.hash_password(
            "projectbridge dummy password for timing"
        )

    async def signup(self, session: AsyncSession, data: UserCreate) -> AuthResult:
        password_hash = password_service.hash_password(data.password)
        existing = await self._users.get_by_email(session, data.email)
        if existing is not None:
            return AuthResult(
                token=None,
                refresh_token=None,
                purpose=None,
                next="/business/register",
            )

        user = User(
            full_name=data.full_name,
            email=data.email,
            password_hash=password_hash,
        )
        self._users.add(session, user)
        try:
            await session.flush()
            token = self._tokens.issue(user.id, "onboarding")
            user.access_token = token
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return AuthResult(
                token=None,
                refresh_token=None,
                purpose=None,
                next="/business/register",
            )
        return AuthResult(
            token=token,
            refresh_token=None,
            purpose="onboarding",
            next="/business/register",
        )

    async def login(self, session: AsyncSession, email: str, password: str) -> AuthResult:
        user = await self._users.get_by_email(session, email)
        password_hash = user.password_hash if user is not None else self._dummy_password_hash
        password_matches = password_service.verify_password(password, password_hash)
        if user is None or not password_matches:
            if user is not None:
                business = await self._businesses.get_for_owner(session, user.id)
                if business is not None:
                    self._audit.record(
                        session,
                        business_id=business.id,
                        actor_user_id=user.id,
                        interface=ActionOrigin.REST,
                        action="auth.login",
                        target_type="user",
                        target_id=user.id,
                        outcome="denied",
                        details={"reason": "invalid_credentials"},
                    )
                    await session.commit()
            raise AuthenticationError("Invalid email or password")

        now = datetime.now(UTC)
        await self._refresh_tokens.revoke_user(session, user.id, now)
        issued_refresh = self._refresh_token_service.issue(user.id)
        self._refresh_tokens.add(session, issued_refresh.record)
        token = self._tokens.issue(user.id, "access")
        user.access_token = token
        business = await self._businesses.get_for_owner(session, user.id)
        if business is not None:
            self._audit.record(
                session,
                business_id=business.id,
                actor_user_id=user.id,
                interface=ActionOrigin.REST,
                action="auth.login",
                target_type="user",
                target_id=user.id,
                outcome="success",
            )
        await session.commit()
        return AuthResult(
            token=token,
            refresh_token=issued_refresh.raw_token,
            purpose="access",
            next="/dashboard" if user.has_business else "/business/register",
        )

    async def refresh(self, session: AsyncSession, raw_token: str | None) -> AuthResult:
        if raw_token is None:
            raise AuthenticationError("Invalid or expired session")
        token_hash = self._refresh_token_service.hash_token(raw_token)
        record = await self._refresh_tokens.get_for_update(session, token_hash)
        if record is None:
            raise AuthenticationError("Invalid or expired session")

        now = datetime.now(UTC)
        user = await self._users.get_by_id(session, record.user_id)
        if record.used_at is not None:
            if (
                user is not None
                and user.access_token is not None
                and record.replaced_by_token_hash is not None
                and now - record.used_at <= self.refresh_retry_grace
                and record.absolute_expires_at > now
            ):
                replacement = self._refresh_token_service.rotate(
                    raw_token,
                    user.id,
                    family_id=record.family_id,
                    absolute_expires_at=record.absolute_expires_at,
                )
                replacement_record = await self._refresh_tokens.get_for_update(
                    session, record.replaced_by_token_hash
                )
                if (
                    replacement.record.token_hash == record.replaced_by_token_hash
                    and replacement_record is not None
                    and replacement_record.used_at is None
                    and replacement_record.revoked_at is None
                    and replacement_record.expires_at > now
                ):
                    next_path = (
                        "/dashboard" if user.has_business else "/business/register"
                    )
                    access_token = user.access_token
                    await session.commit()
                    return AuthResult(
                        token=access_token,
                        refresh_token=replacement.raw_token,
                        purpose="access",
                        next=next_path,
                    )
            await self._refresh_tokens.revoke_family(session, record.family_id, now)
            if user is not None:
                user.access_token = None
            await session.commit()
            raise AuthenticationError("Invalid or expired session")
        if (
            record.revoked_at is not None
            or record.expires_at <= now
            or record.absolute_expires_at <= now
            or user is None
        ):
            await self._refresh_tokens.revoke_family(session, record.family_id, now)
            if user is not None:
                user.access_token = None
            await session.commit()
            raise AuthenticationError("Invalid or expired session")

        record.used_at = now
        replacement = self._refresh_token_service.rotate(
            raw_token,
            user.id,
            family_id=record.family_id,
            absolute_expires_at=record.absolute_expires_at,
        )
        record.replaced_by_token_hash = replacement.record.token_hash
        self._refresh_tokens.add(session, replacement.record)
        access_token = self._tokens.issue(user.id, "access")
        user.access_token = access_token
        await session.commit()
        return AuthResult(
            token=access_token,
            refresh_token=replacement.raw_token,
            purpose="access",
            next="/dashboard" if user.has_business else "/business/register",
        )

    async def get_user(
        self,
        session: AsyncSession,
        token: str | None,
        purpose: TokenPurpose,
    ) -> User | None:
        if token is None:
            return None
        try:
            claims = self._tokens.decode(token, purpose)
        except InvalidTokenError:
            return None
        user = await self._users.get_by_id(session, claims.user_id)
        if (
            user is None
            or user.access_token is None
            or not hmac.compare_digest(user.access_token, token)
        ):
            return None
        return user

    async def session_status(
        self,
        session: AsyncSession,
        access_token: str | None,
        onboarding_token: str | None,
    ) -> SessionResponse:
        user = await self.get_user(session, access_token, "access")
        if user is None:
            user = await self.get_user(session, onboarding_token, "onboarding")
        if user is None:
            return SessionResponse(
                authenticated=False,
                has_business=False,
                next="/login",
            )
        return SessionResponse(
            authenticated=True,
            has_business=user.has_business,
            full_name=user.full_name,
            email=user.email,
            next="/dashboard" if user.has_business else "/business/register",
        )

    async def register_business(
        self,
        session: AsyncSession,
        data: BusinessCreate,
        access_token: str | None,
        onboarding_token: str | None,
    ) -> Business:
        user = await self.get_user(session, access_token, "access")
        if user is None:
            user = await self.get_user(session, onboarding_token, "onboarding")
        if user is None:
            raise AuthenticationError("Authentication required")
        existing_business = await self._businesses.get_for_owner(session, user.id)
        if user.has_business or existing_business is not None:
            if existing_business is not None:
                self._audit.record(
                    session,
                    business_id=existing_business.id,
                    actor_user_id=user.id,
                    interface=ActionOrigin.REST,
                    action="business.register",
                    target_type="business",
                    target_id=existing_business.id,
                    outcome="conflict",
                )
                await session.commit()
            raise BusinessAlreadyRegisteredError("Business is already registered")

        business = Business(name=data.name, owned_by=user.id)
        self._businesses.add(session, business)
        try:
            await session.flush()
            self._audit.record(
                session,
                business_id=business.id,
                actor_user_id=user.id,
                interface=ActionOrigin.REST,
                action="business.register",
                target_type="business",
                target_id=business.id,
                outcome="success",
            )
            await self._refresh_tokens.revoke_user(
                session, user.id, datetime.now(UTC)
            )
            user.access_token = None
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise BusinessAlreadyRegisteredError(
                "Business is already registered"
            ) from exc
        return business

    async def logout(
        self,
        session: AsyncSession,
        access_token: str | None,
        onboarding_token: str | None,
        refresh_token: str | None,
    ) -> None:
        user = await self.get_user(session, access_token, "access")
        if user is None:
            user = await self.get_user(session, onboarding_token, "onboarding")
        refresh_record = None
        if refresh_token is not None:
            refresh_record = await self._refresh_tokens.get_for_update(
                session, self._refresh_token_service.hash_token(refresh_token)
            )
            if refresh_record is not None:
                await self._refresh_tokens.revoke_family(
                    session, refresh_record.family_id, datetime.now(UTC)
                )
                if user is None:
                    user = await self._users.get_by_id(session, refresh_record.user_id)
        if user is not None:
            await self._refresh_tokens.revoke_user(
                session, user.id, datetime.now(UTC)
            )
            user.access_token = None
            business = await self._businesses.get_for_owner(session, user.id)
            if business is not None:
                self._audit.record(
                    session,
                    business_id=business.id,
                    actor_user_id=user.id,
                    interface=ActionOrigin.REST,
                    action="auth.logout",
                    target_type="user",
                    target_id=user.id,
                    outcome="success",
                )
        if user is not None or refresh_record is not None:
            await session.commit()
