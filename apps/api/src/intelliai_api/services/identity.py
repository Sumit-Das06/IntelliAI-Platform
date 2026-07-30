"""Identity capability: organizations, owners, and API key issuance.

Business rules that live here and nowhere else:

- An organization is born with exactly one OWNER member and one API key —
  atomically. A tenant that half-exists is worse than none.
- Emails are normalized (trimmed, lowercased) before storage; repositories
  store exactly what they receive.
- The plaintext key is returned exactly once and never persisted or logged.

Domain events (log-based for now): ``organization.created``,
``user.created``, ``membership.created``, ``apikey.created``. Emitted after
flush (public IDs exist) but before commit — if the transaction rolls back,
the log line is a false positive, which is acceptable for *log* events;
the day events drive billing (M4), they move inside the transaction as
outbox rows.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from intelliai_api.core.errors import ConflictError, InvalidRequestError, ResourceNotFoundError
from intelliai_api.core.security import GeneratedKey, generate_api_key
from intelliai_api.core.time import utc_now
from intelliai_api.db.models import ApiKey, Membership, MembershipRole, Organization, User
from intelliai_api.db.repositories import (
    ApiKeyRepository,
    OrganizationRepository,
    UserRepository,
)
from intelliai_api.services.auth import AuthContext

logger = structlog.get_logger("intelliai_api.identity")


def normalize_email(email: str) -> str:
    return email.strip().lower()


@dataclass(frozen=True)
class BootstrapResult:
    organization: Organization
    owner: User
    membership: Membership
    api_key: ApiKey
    generated: GeneratedKey  # .secret is shown once by the caller, then dies


class IdentityService:
    def __init__(self, session: AsyncSession, *, pepper: str) -> None:
        self._session = session
        self._pepper = pepper
        self._organizations = OrganizationRepository(session)
        self._users = UserRepository(session)
        self._api_keys = ApiKeyRepository(session)

    async def bootstrap_organization(
        self,
        *,
        organization_name: str,
        owner_email: str,
        owner_name: str,
        key_name: str = "bootstrap",
    ) -> BootstrapResult:
        """Create organization + owner + membership + first key, atomically.

        Deliberately NOT idempotent: a repeated call cannot re-show the
        original key (shown-once), so silently "succeeding" would hand back
        a half-truth. A duplicate owner email fails loudly with
        ``ConflictError`` and nothing is persisted.
        """
        email = normalize_email(owner_email)
        if await self._users.get_by_email(email) is not None:
            raise ConflictError(
                f"A user with email {email!r} already exists.",
                code="email_already_registered",
                param="owner_email",
            )

        organization = await self._organizations.create(organization_name.strip())
        logger.info("organization.created", organization_id=organization.public_id)

        owner = await self._users.create(email, owner_name.strip())
        logger.info("user.created", user_id=owner.public_id)

        membership = await self._organizations.add_member(
            organization.id, owner.id, MembershipRole.OWNER
        )
        logger.info(
            "membership.created",
            membership_id=membership.public_id,
            organization_id=organization.public_id,
            user_id=owner.public_id,
            role=MembershipRole.OWNER.value,
        )

        api_key, generated = await self.issue_api_key(
            organization_id=organization.id,
            name=key_name,
            created_by_user_id=owner.id,
        )

        return BootstrapResult(
            organization=organization,
            owner=owner,
            membership=membership,
            api_key=api_key,
            generated=generated,
        )

    async def issue_api_key(
        self,
        *,
        organization_id: int,
        name: str,
        created_by_user_id: int | None = None,
        expires_at: datetime | None = None,
    ) -> tuple[ApiKey, GeneratedKey]:
        """Mint and persist a key; the plaintext exists only in the return value."""
        generated = generate_api_key(self._pepper)
        api_key = await self._api_keys.add(
            organization_id=organization_id,
            name=name.strip(),
            prefix=generated.prefix,
            last4=generated.last4,
            key_hash=generated.hash,
            created_by_user_id=created_by_user_id,
            expires_at=expires_at,
        )
        # Field is key_id, not api_key_id: the redaction processor masks
        # anything matching "api_key", and public IDs are meant to be seen.
        logger.info(
            "apikey.created",
            key_id=api_key.public_id,
            key_prefix=api_key.key_prefix,
        )
        return api_key, generated

    # ── AuthContext-facing operations (the public API's surface) ─────────

    async def create_key(
        self,
        auth: AuthContext,
        *,
        name: str,
        expires_at: datetime | None = None,
    ) -> tuple[ApiKey, GeneratedKey]:
        """Issue a key for the authenticated organization.

        Names are labels, not identities — duplicates are allowed on
        purpose (two servers may both be called "prod"; the public_id is
        the identity). An expiry in the past is a request error.
        """
        if expires_at is not None and expires_at <= utc_now():
            raise InvalidRequestError(
                "expires_at must be in the future.",
                code="expires_at_in_past",
                param="expires_at",
            )
        return await self.issue_api_key(
            organization_id=auth.organization_id,
            name=name,
            expires_at=expires_at,
        )

    async def list_keys(self, auth: AuthContext) -> Sequence[ApiKey]:
        """Metadata only — plaintext secrets do not exist to be listed."""
        return await self._api_keys.list_for_organization(auth.organization_id)

    async def revoke_key(self, auth: AuthContext, key_public_id: str) -> ApiKey:
        """Soft-revoke; idempotent.

        A foreign org's key does not exist from this caller's point of view
        (404, never 403 — no existence disclosure). Repeat revocations
        return the already-revoked key unchanged and emit no second event.
        """
        api_key = await self._api_keys.get_for_organization(auth.organization_id, key_public_id)
        if api_key is None:
            raise ResourceNotFoundError(
                f"No API key {key_public_id!r} exists in this organization.",
                code="api_key_not_found",
                param="key_id",
            )
        if api_key.revoked_at is None:
            api_key.revoked_at = utc_now()
            await self._session.flush()
            logger.info(
                "apikey.revoked",
                key_id=api_key.public_id,
                organization_id=auth.organization_public_id,
            )
        return api_key
