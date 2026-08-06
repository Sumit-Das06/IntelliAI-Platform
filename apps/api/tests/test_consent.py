"""Organization data-collection consent: opt-in by law, revocable, historical.

The gate every future collection commit depends on: nothing may be stored
for model improvement unless the tenant explicitly granted consent, and
revocation must stop future collection while leaving the historical grant
readable (stored samples snapshot the consent they were gathered under).
"""

from collections.abc import Iterator

import pytest
import structlog
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from intelliai_api.core.config import Settings
from intelliai_api.core.errors import ResourceNotFoundError
from intelliai_api.services.identity import BootstrapResult, IdentityService
from tests.helpers import client_with_db

pytestmark = pytest.mark.anyio

PEPPER = "test-pepper"  # matches conftest AuthSettings


@pytest.fixture(autouse=True)
def _unbind_logging() -> Iterator[None]:
    yield
    structlog.reset_defaults()


def _service(session: AsyncSession) -> IdentityService:
    return IdentityService(session, pepper=PEPPER)


async def _tenant(session: AsyncSession, email: str) -> BootstrapResult:
    return await _service(session).bootstrap_organization(
        organization_name="ConsentCo", owner_email=email, owner_name="Owner"
    )


# ── Service rules ────────────────────────────────────────────────────────


async def test_a_tenant_is_born_without_consent(db_session: AsyncSession) -> None:
    # Opt-in by law: the default is FALSE and nothing may assume otherwise.
    result = await _tenant(db_session, "born@example.com")
    assert result.organization.data_consent is False
    assert result.organization.data_consented_at is None
    assert result.organization.consent_reference is None


async def test_grant_records_the_flag_the_moment_and_the_document(
    db_session: AsyncSession,
) -> None:
    result = await _tenant(db_session, "grant@example.com")
    organization = await _service(db_session).grant_data_consent(
        organization_public_id=result.organization.public_id,
        reference="cohort-2026-08-consent-v1",
    )
    assert organization.data_consent is True
    assert organization.data_consented_at is not None
    assert organization.consent_reference == "cohort-2026-08-consent-v1"


async def test_regrant_with_the_same_reference_is_a_no_op(db_session: AsyncSession) -> None:
    # Idempotent: the second identical grant changes nothing — including
    # the timestamp, which records the ORIGINAL act of consent.
    result = await _tenant(db_session, "idempotent@example.com")
    service = _service(db_session)
    first = await service.grant_data_consent(
        organization_public_id=result.organization.public_id, reference="doc-v1"
    )
    first_granted_at = first.data_consented_at
    second = await service.grant_data_consent(
        organization_public_id=result.organization.public_id, reference="doc-v1"
    )
    assert second.data_consented_at == first_granted_at


async def test_regrant_under_a_new_document_refreshes_the_grant(
    db_session: AsyncSession,
) -> None:
    # A changed governing document is a new consent fact: samples snapshot
    # the reference, so the row must carry the one currently in force.
    result = await _tenant(db_session, "renew@example.com")
    service = _service(db_session)
    first = await service.grant_data_consent(
        organization_public_id=result.organization.public_id, reference="doc-v1"
    )
    first_granted_at = first.data_consented_at
    renewed = await service.grant_data_consent(
        organization_public_id=result.organization.public_id, reference="doc-v2"
    )
    assert renewed.consent_reference == "doc-v2"
    assert renewed.data_consented_at is not None
    assert first_granted_at is not None
    assert renewed.data_consented_at >= first_granted_at


async def test_revoke_clears_only_the_permission(db_session: AsyncSession) -> None:
    # The historical grant survives revocation: it records what already-
    # collected samples were gathered under. Only the flag is cleared.
    result = await _tenant(db_session, "revoke@example.com")
    service = _service(db_session)
    await service.grant_data_consent(
        organization_public_id=result.organization.public_id, reference="doc-v1"
    )
    organization = await service.revoke_data_consent(
        organization_public_id=result.organization.public_id
    )
    assert organization.data_consent is False
    assert organization.data_consented_at is not None
    assert organization.consent_reference == "doc-v1"


async def test_revoking_a_non_consented_tenant_is_a_no_op(db_session: AsyncSession) -> None:
    result = await _tenant(db_session, "never@example.com")
    organization = await _service(db_session).revoke_data_consent(
        organization_public_id=result.organization.public_id
    )
    assert organization.data_consent is False
    assert organization.data_consented_at is None


async def test_unknown_organization_is_refused_on_both_operations(
    db_session: AsyncSession,
) -> None:
    service = _service(db_session)
    with pytest.raises(ResourceNotFoundError):
        await service.grant_data_consent(organization_public_id="org_missing")
    with pytest.raises(ResourceNotFoundError):
        await service.revoke_data_consent(organization_public_id="org_missing")


# ── API exposure ─────────────────────────────────────────────────────────


async def test_the_organization_endpoint_states_the_consent_honestly(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, factory):
        async with factory() as session:
            result = await _tenant(session, "api@example.com")
            await session.commit()
        headers = {"Authorization": f"Bearer {result.generated.secret}"}

        before = await client.get("/v1/organization", headers=headers)
        assert before.status_code == 200
        assert before.json()["data_consent"] is False
        assert before.json()["data_consented_at"] is None

        async with factory() as session:
            await _service(session).grant_data_consent(
                organization_public_id=result.organization.public_id, reference="doc-v1"
            )
            await session.commit()

        after = await client.get("/v1/organization", headers=headers)
        assert after.status_code == 200
        assert after.json()["data_consent"] is True
        assert after.json()["data_consented_at"] is not None


# ── CLI surface ──────────────────────────────────────────────────────────


def test_the_cli_knows_both_consent_subcommands() -> None:
    # Wiring only: --org is required on both; business logic is covered by
    # the service tests above and the CLI never contains any.
    from intelliai_api.cli import main

    with pytest.raises(SystemExit) as grant_exit:
        main(["grant-consent"])
    assert grant_exit.value.code == 2  # argparse: missing --org

    with pytest.raises(SystemExit) as revoke_exit:
        main(["revoke-consent"])
    assert revoke_exit.value.code == 2
