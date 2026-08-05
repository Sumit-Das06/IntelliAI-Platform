"""Organization persistence — the tenant aggregate and the memberships it owns."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intelliai_api.db.models import Membership, MembershipRole, Organization, UsageOrigin


class OrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, name: str, *, usage_origin: UsageOrigin = UsageOrigin.CUSTOMER
    ) -> Organization:
        """Create a tenant. ``usage_origin`` defaults to the column default.

        It is a parameter rather than a post-create mutation because a
        tenant's origin decides how every event it ever produces is
        interpreted, and usage events are append-only: traffic recorded
        under the wrong origin cannot be reattributed afterwards. The
        classification has to be true before the first request, so it is
        set at birth or not at all.
        """
        organization = Organization(name=name, usage_origin=usage_origin)
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
