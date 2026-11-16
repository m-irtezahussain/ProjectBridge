from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class UserRepository:
    """Database access for users, including their derived onboarding state."""

    async def get_by_email(self, session: AsyncSession, email: str) -> User | None:
        return await session.scalar(select(User).where(User.email == email))

    async def get_by_id(self, session: AsyncSession, user_id: int) -> User | None:
        return await session.scalar(select(User).where(User.id == user_id))

    def add(self, session: AsyncSession, user: User) -> None:
        session.add(user)
