"""Identity service tests: business rules, atomicity, events, shown-once."""

from collections.abc import Iterator

import pytest
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from intelliai_api.core.config import Settings
from intelliai_api.core.errors import ConflictError, InvalidRequestError
from intelliai_api.core.logging import configure_logging
from intelliai_api.core.security import verify_api_key
from intelliai_api.db.models import MembershipRole, Organization, UsageOrigin
from intelliai_api.db.repositories import ApiKeyRepository, UserRepository
from intelliai_api.pricing.rating import RATEABLE_ORIGINS
from intelliai_api.services.identity import (
    TENANT_ORIGINS,
    IdentityService,
    normalize_email,
    tenant_origin,
)

pytestmark = pytest.mark.anyio

PEPPER = "service-test-pepper"


@pytest.fixture(autouse=True)
def _unbind_logging() -> Iterator[None]:
    """Undo any `configure_logging` a test performs.

    `configure_logging` binds structlog's PrintLogger to whatever stdout
    is current — under `capsys` that is a captured stream which pytest
    closes at teardown. The binding is global and outlives the test, so
    the next test to log anything raises `I/O operation on closed file`.
    Without this, the order tests happen to be written in is load-bearing.
    """
    yield
    structlog.reset_defaults()


def _service(session: AsyncSession) -> IdentityService:
    return IdentityService(session, pepper=PEPPER)


async def test_bootstrap_creates_the_complete_tenant(db_session: AsyncSession) -> None:
    result = await _service(db_session).bootstrap_organization(
        organization_name="Acme",
        owner_email="Owner@Example.COM",
        owner_name="Owner",
    )

    assert result.organization.public_id.startswith("org_")
    assert result.owner.email == "owner@example.com"  # normalized by the service
    assert result.membership.role is MembershipRole.OWNER
    assert result.membership.organization_id == result.organization.id
    assert result.membership.user_id == result.owner.id
    # The returned plaintext verifies against the persisted hash:
    assert verify_api_key(result.generated.secret, PEPPER, result.api_key.key_hash)


async def test_plaintext_never_persisted(db_session: AsyncSession) -> None:
    result = await _service(db_session).bootstrap_organization(
        organization_name="Acme",
        owner_email="secret@example.com",
        owner_name="Owner",
    )

    stored = await ApiKeyRepository(db_session).get_by_hash(result.api_key.key_hash)
    assert stored is not None
    for value in (stored.name, stored.key_prefix, stored.key_last4, stored.key_hash):
        assert result.generated.secret not in value


async def test_duplicate_email_conflicts_and_persists_nothing(
    db_session: AsyncSession,
) -> None:
    await UserRepository(db_session).create("taken@example.com", "Existing")

    with pytest.raises(ConflictError) as excinfo:
        await _service(db_session).bootstrap_organization(
            organization_name="GhostOrg",
            owner_email="  TAKEN@example.com ",  # normalization applies to the check
            owner_name="Late",
        )

    assert excinfo.value.code == "email_already_registered"
    ghost_orgs = await db_session.execute(
        select(func.count()).select_from(Organization).where(Organization.name == "GhostOrg")
    )
    assert ghost_orgs.scalar_one() == 0


async def test_service_never_commits(db_session: AsyncSession) -> None:
    """The atomic scope belongs to the service; the commit trigger does not."""
    await _service(db_session).bootstrap_organization(
        organization_name="RollbackCo",
        owner_email="rollback@example.com",
        owner_name="Owner",
    )
    await db_session.rollback()  # entrypoint decides NOT to commit

    remaining = await db_session.execute(
        select(func.count()).select_from(Organization).where(Organization.name == "RollbackCo")
    )
    assert remaining.scalar_one() == 0


async def test_domain_events_are_emitted(
    db_session: AsyncSession,
    settings: Settings,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(settings)  # test env → JSON lines on stdout

    result = await _service(db_session).bootstrap_organization(
        organization_name="EventCo",
        owner_email="events@example.com",
        owner_name="Owner",
    )

    out = capsys.readouterr().out
    for event in (
        "organization.created",
        "user.created",
        "membership.created",
        "apikey.created",
    ):
        assert event in out, f"missing domain event {event}"
    # The display prefix MAY appear (that is its job); the full secret NEVER:
    assert result.generated.secret not in out
    assert result.api_key.key_prefix in out
    # Public IDs must survive redaction (field named key_id, not api_key_id):
    assert result.api_key.public_id in out


def test_normalize_email() -> None:
    assert normalize_email("  Sumit@EXAMPLE.Com ") == "sumit@example.com"


class TestTenantOrigin:
    """A tenant's origin decides how every event it ever emits is read.

    Usage events are append-only, so this classification cannot be
    corrected after the fact — traffic recorded against a customer org is
    rated as revenue and counted as demand, permanently. It is therefore
    set at birth, and an origin nobody registered is refused rather than
    defaulted.
    """

    async def test_a_tenant_is_a_customer_unless_told_otherwise(
        self, db_session: AsyncSession
    ) -> None:
        result = await _service(db_session).bootstrap_organization(
            organization_name="Acme",
            owner_email="default@example.com",
            owner_name="Owner",
        )
        assert result.organization.usage_origin is UsageOrigin.CUSTOMER

    async def test_our_own_measurement_traffic_can_be_created_as_such(
        self, db_session: AsyncSession
    ) -> None:
        result = await _service(db_session).bootstrap_organization(
            organization_name="IntelliAI Benchmark",
            owner_email="bench@example.com",
            owner_name="Owner",
            usage_origin=UsageOrigin.BENCHMARK,
        )
        assert result.organization.usage_origin is UsageOrigin.BENCHMARK

    async def test_the_benchmark_tenant_is_never_rated(self, db_session: AsyncSession) -> None:
        # The isolation is not a property of the name or of a convention:
        # rating filters on the origin, so a benchmark tenant cannot bill
        # even if someone points a customer-shaped workload at it.
        result = await _service(db_session).bootstrap_organization(
            organization_name="IntelliAI Benchmark",
            owner_email="unrated@example.com",
            owner_name="Owner",
            usage_origin=UsageOrigin.BENCHMARK,
        )
        assert result.organization.usage_origin not in RATEABLE_ORIGINS

    def test_every_registered_origin_is_offerable(self) -> None:
        # The entrypoint reads its choices from TENANT_ORIGINS rather than
        # hardcoding a list that would silently rot when the taxonomy grows.
        assert set(TENANT_ORIGINS) == {origin.value for origin in UsageOrigin}

    def test_a_registered_origin_parses(self) -> None:
        assert tenant_origin("benchmark") is UsageOrigin.BENCHMARK

    def test_an_unregistered_origin_is_refused_not_defaulted(self) -> None:
        # Guessing here means our own traffic is rated as revenue.
        with pytest.raises(InvalidRequestError, match="unknown usage origin"):
            tenant_origin("benchmarking")
