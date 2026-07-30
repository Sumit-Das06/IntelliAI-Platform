"""User persistence.

Users are tenant-independent records (they exist across organizations), so
these methods are legitimately unscoped. Email normalization (lowercasing)
is a business rule and happens in the service layer — this repository
stores exactly what it is given.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intelliai_api.db.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, email: str, name: str) -> User:
        user = User(email=email, name=name)
        self._session.add(user)
        await self._session.flush()
        return user

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()
