"""API key persistence — tenant-owned: organization scope is mandatory.

Every read here requires an explicit ``organization_id`` — with ONE
documented exception, ``get_by_hash``, because authentication cannot know
the organization until the key is found: the key IS the tenant locator.
If you are writing a query on api_keys without an organization_id and you
are not the authentication path, stop — you are probably writing a leak.
"""

from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from intelliai_api.db.models import ApiKey


class ApiKeyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        organization_id: int,
        name: str,
        prefix: str,
        last4: str,
        key_hash: str,
        created_by_user_id: int | None = None,
        expires_at: datetime | None = None,
    ) -> ApiKey:
        api_key = ApiKey(
            organization_id=organization_id,
            name=name,
            key_prefix=prefix,
            key_last4=last4,
            key_hash=key_hash,
            created_by_user_id=created_by_user_id,
            expires_at=expires_at,
        )
        self._session.add(api_key)
        await self._session.flush()
        return api_key

    async def get_by_hash(self, key_hash: str) -> ApiKey | None:
        """The ONE unscoped read: the authentication locator.

        Eager-loads the organization — the auth path always needs it, and
        async lazy-loading would raise on access anyway.
        """
        result = await self._session.execute(
            select(ApiKey)
            .options(selectinload(ApiKey.organization))
            .where(ApiKey.key_hash == key_hash)
        )
        return result.scalar_one_or_none()

    async def list_for_organization(self, organization_id: int) -> Sequence[ApiKey]:
        result = await self._session.scalars(
            select(ApiKey)
            .where(ApiKey.organization_id == organization_id)
            .order_by(ApiKey.created_at.desc(), ApiKey.id.desc())
        )
        return result.all()

    async def get_for_organization(self, organization_id: int, public_id: str) -> ApiKey | None:
        """Scoped point-read: a foreign org's key simply does not exist here
        (the API layer renders that as 404, never 403 — no enumeration)."""
        result = await self._session.execute(
            select(ApiKey).where(
                ApiKey.organization_id == organization_id,
                ApiKey.public_id == public_id,
            )
        )
        return result.scalar_one_or_none()

    async def touch_last_used(
        self, api_key_id: int, *, now: datetime, min_interval: timedelta
    ) -> None:
        """Throttled usage stamp: writes at most once per ``min_interval``.

        A single conditional UPDATE — the WHERE clause is the throttle, so
        concurrent requests cannot stampede the row (ADR-0012 optimization
        target, stage 1).
        """
        await self._session.execute(
            update(ApiKey)
            .where(
                ApiKey.id == api_key_id,
                or_(
                    ApiKey.last_used_at.is_(None),
                    ApiKey.last_used_at < now - min_interval,
                ),
            )
            .values(last_used_at=now)
        )
