from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    OAuthAuthorizationCode,
    OAuthClient,
    OAuthGrant,
    OAuthRefreshToken,
)


class OAuthRepository:
    """Transactional storage for OAuth clients, grants, and credentials."""

    async def get_client(
        self, session: AsyncSession, client_id: str
    ) -> OAuthClient | None:
        return await session.get(OAuthClient, client_id)

    def add_client(self, session: AsyncSession, client: OAuthClient) -> None:
        session.add(client)

    async def get_code_for_update(
        self, session: AsyncSession, code_hash: str
    ) -> OAuthAuthorizationCode | None:
        return await session.scalar(
            select(OAuthAuthorizationCode)
            .where(OAuthAuthorizationCode.code_hash == code_hash)
            .with_for_update()
        )

    async def get_grant(
        self, session: AsyncSession, grant_id: str
    ) -> OAuthGrant | None:
        return await session.get(OAuthGrant, grant_id)

    async def get_refresh_for_update(
        self, session: AsyncSession, token_hash: str
    ) -> OAuthRefreshToken | None:
        return await session.scalar(
            select(OAuthRefreshToken)
            .where(OAuthRefreshToken.token_hash == token_hash)
            .with_for_update()
        )

    def add_grant_and_code(
        self,
        session: AsyncSession,
        grant: OAuthGrant,
        code: OAuthAuthorizationCode,
    ) -> None:
        session.add_all([grant, code])

    def add_refresh_token(
        self, session: AsyncSession, token: OAuthRefreshToken
    ) -> None:
        session.add(token)

    async def revoke_refresh_family(
        self, session: AsyncSession, family_id: str, revoked_at: datetime
    ) -> None:
        await session.execute(
            update(OAuthRefreshToken)
            .where(
                OAuthRefreshToken.family_id == family_id,
                OAuthRefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )

    async def revoke_grant(
        self, session: AsyncSession, grant_id: str, revoked_at: datetime
    ) -> None:
        await session.execute(
            update(OAuthGrant)
            .where(OAuthGrant.id == grant_id, OAuthGrant.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
        )
        await session.execute(
            update(OAuthRefreshToken)
            .where(
                OAuthRefreshToken.grant_id == grant_id,
                OAuthRefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
