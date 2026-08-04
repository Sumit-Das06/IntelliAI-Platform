"""Authentication capability: API key verification → AuthContext.

The full ADR-0012 pipeline, HTTP-free and therefore testable without a
server: given a candidate key string, either return the canonical
``AuthContext`` (ADR-0014) or raise a typed ``AuthenticationError`` whose
``code`` tells the caller exactly what went wrong:

- ``invalid_api_key``   — malformed, or well-formed but matching nothing.
  One code for both on purpose: outsiders learn nothing about which keys
  exist.
- ``api_key_revoked``   — the key was genuine; the caller once held it, so
  naming the state is help, not a leak.
- ``api_key_expired``   — likewise; the fix (rotate) differs from revoked.

(``missing_api_key`` is raised by the HTTP layer — absence of a header is
a transport concern, not a credential concern.)
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from intelliai_api.core.errors import AuthenticationError
from intelliai_api.core.security import hash_api_key, is_well_formed, verify_api_key
from intelliai_api.core.time import utc_now
from intelliai_api.db.models import ApiKey, Organization, UsageOrigin
from intelliai_api.db.repositories import ApiKeyRepository

# Policy: how often the usage stamp is worth a write (ADR-0012, stage 1).
LAST_USED_WRITE_INTERVAL = timedelta(seconds=60)


@dataclass(frozen=True)
class AuthContext:
    """The canonical authenticated identity (ADR-0014).

    Constructed ONLY by authentication after full verification — holding
    one is proof the caller was verified. Immutable: identity is a fact
    about the request, not a variable. Future fields (user, scopes,
    billing context, trace ids) are added with defaults; signatures
    never change.
    """

    organization: Organization
    api_key: ApiKey
    request_id: str | None
    authenticated_at: datetime

    @property
    def organization_id(self) -> int:
        """Internal id — what repositories scope by."""
        return self.organization.id

    @property
    def organization_public_id(self) -> str:
        """Public id — what logs and responses show."""
        return self.organization.public_id

    @property
    def key_public_id(self) -> str:
        return self.api_key.public_id

    @property
    def usage_origin(self) -> UsageOrigin:
        """Why this caller's traffic exists — stamped onto every usage event.

        A commercial classification carried by the tenant, resolved here
        because authentication is the one place the tenant is identified.
        It is deliberately NOT a scope: it says nothing about what the
        caller may do, only about how their consumption is later
        interpreted. Measurement is unconditional; rating reads this.
        """
        return self.organization.usage_origin


class AuthService:
    def __init__(self, session: AsyncSession, *, pepper: str) -> None:
        self._api_keys = ApiKeyRepository(session)
        self._pepper = pepper

    async def authenticate(self, candidate: str, *, request_id: str | None = None) -> AuthContext:
        # Cheap structural check first: garbage never reaches the database.
        if not is_well_formed(candidate):
            raise self._invalid()

        api_key = await self._api_keys.get_by_hash(hash_api_key(candidate, self._pepper))
        if api_key is None or not verify_api_key(candidate, self._pepper, api_key.key_hash):
            raise self._invalid()

        # State checks only AFTER the key proved genuine — these codes are
        # help for the legitimate holder, not information for guessers.
        if api_key.revoked_at is not None:
            raise AuthenticationError("This API key has been revoked.", code="api_key_revoked")
        now = utc_now()
        if api_key.expires_at is not None and api_key.expires_at <= now:
            raise AuthenticationError("This API key has expired.", code="api_key_expired")

        await self._api_keys.touch_last_used(
            api_key.id, now=now, min_interval=LAST_USED_WRITE_INTERVAL
        )
        return AuthContext(
            organization=api_key.organization,
            api_key=api_key,
            request_id=request_id,
            authenticated_at=now,
        )

    @staticmethod
    def _invalid() -> AuthenticationError:
        return AuthenticationError(
            "Invalid API key. Provide 'Authorization: Bearer ik_live_...'.",
            code="invalid_api_key",
        )
