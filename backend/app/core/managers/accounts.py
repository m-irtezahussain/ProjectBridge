from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.mcp_auth import MCPPrincipal
from app.models import Business, User
from app.repositories.businesses import BusinessRepository
from app.repositories.users import UserRepository


class AccountNotFoundError(ValueError):
    pass


class AccountManager:
    """Resolve current account data without trusting caller-supplied tenant IDs."""

    def __init__(
        self,
        users: UserRepository | None = None,
        businesses: BusinessRepository | None = None,
    ) -> None:
        self._users = users or UserRepository()
        self._businesses = businesses or BusinessRepository()

    async def get_current_account(
        self, session: AsyncSession, principal: MCPPrincipal
    ) -> tuple[User, Business]:
        user = await self._users.get_by_id(session, principal.user_id)
        business = await self._businesses.get_for_owner(session, principal.user_id)
        if (
            user is None
            or business is None
            or business.id != principal.business_id
        ):
            raise AccountNotFoundError("Account not found")
        return user, business
