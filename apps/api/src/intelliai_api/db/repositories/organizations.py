"""Organization persistence — the tenant aggregate and the memberships it owns."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intelliai_api.db.models import Membership, MembershipRole, Organization


class OrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, name: str) -> Organization:
        organization = Organization(name=name)
        self._session.add(organization)
        # flush, never commit: ids/public_ids get assigned, but the
        # transaction boundary belongs to the caller (request scope).
        await self._session.flush()
        return organization

    async def get_by_public_id(self, public_id: str) -> Organization | None:
        result = await self._session.execute(
            select(Organization).where(Organization.public_id == public_id)
        )
        return result.scalar_one_or_none()

    async def add_member(
        self, organization_id: int, user_id: int, role: MembershipRole
    ) -> Membership:
        membership = Membership(organization_id=organization_id, user_id=user_id, role=role)
        self._session.add(membership)
        await self._session.flush()
        return membership
