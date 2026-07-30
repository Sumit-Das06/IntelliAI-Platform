"""Repository tests against real Postgres, isolated by savepoint rollback.

Every test runs inside a rolled-back transaction (see ``db_session`` in
conftest): real SQL, real constraints, zero residue.
"""

from datetime import timedelta

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from intelliai_api.core.security import generate_api_key
from intelliai_api.core.time import utc_now
from intelliai_api.db.models import MembershipRole
from intelliai_api.db.repositories import (
    ApiKeyRepository,
    OrganizationRepository,
    UserRepository,
)

pytestmark = pytest.mark.anyio

PEPPER = "repo-test-pepper"


async def _org_with_key(session: AsyncSession, org_name: str) -> tuple[int, str, str]:
    """Helper: organization + one stored key; returns (org_id, key public_id, hash)."""
    org = await OrganizationRepository(session).create(org_name)
    generated = generate_api_key(PEPPER)
    key = await ApiKeyRepository(session).add(
        organization_id=org.id,
        name=f"{org_name}-key",
        prefix=generated.prefix,
        last4=generated.last4,
        key_hash=generated.hash,
    )
    return org.id, key.public_id, generated.hash


# ── Organizations & memberships ─────────────────────────────────────────


async def test_create_organization_assigns_ids_and_defaults(
    db_session: AsyncSession,
) -> None:
    org = await OrganizationRepository(db_session).create("Acme")
    assert org.id is not None
    assert org.public_id.startswith("org_")
    await db_session.commit()
    assert org.created_at is not None  # database-generated


async def test_membership_pair_unique_at_database_level(
    db_session: AsyncSession,
) -> None:
    orgs = OrganizationRepository(db_session)
    org = await orgs.create("Acme")
    user = await UserRepository(db_session).create("dup@example.com", "Dup")

    await orgs.add_member(org.id, user.id, MembershipRole.OWNER)
    with pytest.raises(IntegrityError):
        await orgs.add_member(org.id, user.id, MembershipRole.MEMBER)


# ── Users ───────────────────────────────────────────────────────────────


async def test_get_by_email_round_trip(db_session: AsyncSession) -> None:
    users = UserRepository(db_session)
    created = await users.create("found@example.com", "Found")
    assert (await users.get_by_email("found@example.com")) is created
    assert (await users.get_by_email("missing@example.com")) is None


# ── API keys: the tenant-owned aggregate ────────────────────────────────


async def test_get_by_hash_finds_key_with_organization_eagerly_loaded(
    db_session: AsyncSession,
) -> None:
    _, _, key_hash = await _org_with_key(db_session, "EagerCo")

    found = await ApiKeyRepository(db_session).get_by_hash(key_hash)

    assert found is not None
    # The auth path needs the org without a lazy load (async would raise):
    assert "organization" not in inspect(found).unloaded
    assert found.organization.name == "EagerCo"


async def test_get_by_hash_misses_unknown_hash(db_session: AsyncSession) -> None:
    assert (await ApiKeyRepository(db_session).get_by_hash("0" * 64)) is None


async def test_scoped_point_read_cannot_cross_tenants(
    db_session: AsyncSession,
) -> None:
    """THE tenant-isolation test at the repository level."""
    org_a, key_a_public, _ = await _org_with_key(db_session, "OrgA")
    org_b, key_b_public, _ = await _org_with_key(db_session, "OrgB")
    keys = ApiKeyRepository(db_session)

    assert (await keys.get_for_organization(org_a, key_a_public)) is not None
    # Org A asking for Org B's key: it simply does not exist.
    assert (await keys.get_for_organization(org_a, key_b_public)) is None
    assert (await keys.get_for_organization(org_b, key_a_public)) is None


async def test_listing_is_scoped_to_the_organization(
    db_session: AsyncSession,
) -> None:
    org_a, _, _ = await _org_with_key(db_session, "ListA")
    _org_b, _, _ = await _org_with_key(db_session, "ListB")

    listed = await ApiKeyRepository(db_session).list_for_organization(org_a)

    assert len(listed) == 1
    assert all(key.organization_id == org_a for key in listed)


async def test_touch_last_used_writes_once_per_interval(
    db_session: AsyncSession,
) -> None:
    _org_id, _, key_hash = await _org_with_key(db_session, "ThrottleCo")
    keys = ApiKeyRepository(db_session)
    key = await keys.get_by_hash(key_hash)
    assert key is not None and key.last_used_at is None

    first = utc_now()
    await keys.touch_last_used(key.id, now=first, min_interval=timedelta(seconds=60))
    await db_session.refresh(key)
    assert key.last_used_at == first

    # Within the interval: the conditional UPDATE must not fire.
    second = first + timedelta(seconds=5)
    await keys.touch_last_used(key.id, now=second, min_interval=timedelta(seconds=60))
    await db_session.refresh(key)
    assert key.last_used_at == first

    # Beyond the interval: it updates again.
    third = first + timedelta(seconds=61)
    await keys.touch_last_used(key.id, now=third, min_interval=timedelta(seconds=60))
    await db_session.refresh(key)
    assert key.last_used_at == third


# ── Savepoint isolation, proven ─────────────────────────────────────────
# Both tests insert the SAME unique email and commit. They can only both
# pass if each test's work — commits included — is fully rolled back.


async def test_isolation_proof_first(db_session: AsyncSession) -> None:
    await UserRepository(db_session).create("isolation@example.com", "First")
    await db_session.commit()


async def test_isolation_proof_second(db_session: AsyncSession) -> None:
    await UserRepository(db_session).create("isolation@example.com", "Second")
    await db_session.commit()
