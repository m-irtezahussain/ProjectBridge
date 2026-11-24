from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Business, User


class UserRepository:
    """Database access for users, including their derived onboarding state."""

    async def get_by_email(self, session: AsyncSession, email: str) -> User | None:
        return await session.scalar(select(User).where(User.email == email))

    async def get_by_id(self, session: AsyncSession, user_id: int) -> User | None:
        return await session.scalar(select(User).where(User.id == user_id))

    async def get_business_assignee(
        self, session: AsyncSession, business_id: int, user_id: int
    ) -> User | None:
        """Return an assignable user without ever crossing the business boundary.

        Businesses currently contain their owner only. Keeping this lookup behind a
        tenant-scoped repository method lets future membership records be added here
        without weakening task assignment checks.
        """
        return await session.scalar(
            select(User)
            .join(Business, Business.owned_by == User.id)
            .where(Business.id == business_id, User.id == user_id)
        )

    async def list_business_assignees(
        self, session: AsyncSession, business_id: int
    ) -> list[User]:
        result = await session.scalars(
            select(User)
            .join(Business, Business.owned_by == User.id)
            .where(Business.id == business_id)
            .order_by(User.full_name.asc(), User.id.asc())
        )
        return list(result.all())

    def add(self, session: AsyncSession, user: User) -> None:
        session.add(user)
