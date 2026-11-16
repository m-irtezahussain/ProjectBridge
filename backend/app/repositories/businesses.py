from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Business


class BusinessRepository:
    """Tenant-safe database access for a user's owned business."""

    async def get_for_owner(
        self, session: AsyncSession, owner_id: int
    ) -> Business | None:
        return await session.scalar(
            select(Business).where(Business.owned_by == owner_id)
        )

    def add(self, session: AsyncSession, business: Business) -> None:
        session.add(business)
