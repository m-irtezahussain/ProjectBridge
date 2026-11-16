from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RefreshToken


class RefreshTokenRepository:
    """Transactional storage and family revocation for refresh credentials."""

    async def get_for_update(
        self, session: AsyncSession, token_hash: str
    ) -> RefreshToken | None:
        return await session.scalar(
            select(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .with_for_update()
        )

    def add(self, session: AsyncSession, token: RefreshToken) -> None:
        session.add(token)

    async def revoke_family(
        self, session: AsyncSession, family_id: str, revoked_at: datetime
    ) -> None:
        await session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.family_id == family_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )

    async def revoke_user(
        self, session: AsyncSession, user_id: int, revoked_at: datetime
    ) -> None:
        await session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
