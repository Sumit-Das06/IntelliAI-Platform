"""Key-management endpoint tests: lifecycle, isolation, idempotency, envelopes."""

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from intelliai_api.core.config import Settings
from intelliai_api.core.logging import configure_logging
from intelliai_api.core.security import is_well_formed
from intelliai_api.services.identity import BootstrapResult, IdentityService
from tests.helpers import client_with_db

pytestmark = pytest.mark.anyio

PEPPER = "test-pepper"  # matches conftest AuthSettings

RESPONSE_FIELDS = {
    "id",
    "name",
    "key_prefix",
    "key_last4",
    "created_at",
    "last_used_at",
    "expires_at",
    "revoked_at",
}


async def _tenant(
    factory: async_sessionmaker[AsyncSession], email: str, org: str = "KeysCo"
) -> BootstrapResult:
    async with factory() as session:
        result = await IdentityService(session, pepper=PEPPER).bootstrap_organization(
            organization_name=org, owner_email=email, owner_name="Owner"
        )
        await session.commit()
        return result


def _bearer(secret: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {secret}"}


# ── Create ──────────────────────────────────────────────────────────────


async def test_create_returns_201_with_plaintext_exactly_once(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, factory):
        tenant = await _tenant(factory, "create@example.com")

        response = await client.post(
            "/v1/api-keys",
            json={"name": "prod-server"},
            headers=_bearer(tenant.generated.secret),
        )

        assert response.status_code == 201
        body = response.json()
        assert set(body) == RESPONSE_FIELDS | {"key"}
        assert body["id"].startswith("key_")
        assert body["name"] == "prod-server"
        assert is_well_formed(body["key"])
        assert body["key"].startswith(body["key_prefix"])
        assert body["revoked_at"] is None

        # The new key immediately works:
        whoami = await client.get("/v1/organization", headers=_bearer(body["key"]))
        assert whoami.status_code == 200


async def test_create_rejects_empty_name_with_envelope(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, factory):
        tenant = await _tenant(factory, "emptyname@example.com")

        response = await client.post(
            "/v1/api-keys", json={"name": ""}, headers=_bearer(tenant.generated.secret)
        )

        assert response.status_code == 400
        err = response.json()["error"]
        assert err["type"] == "invalid_request_error"
        assert err["code"] == "validation_error"
        assert err["param"] == "name"


async def test_create_rejects_past_expiry(settings: Settings, db_engine: AsyncEngine) -> None:
    async with client_with_db(settings, db_engine) as (client, factory):
        tenant = await _tenant(factory, "expiry@example.com")

        response = await client.post(
            "/v1/api-keys",
            json={"name": "old", "expires_at": "2020-01-01T00:00:00Z"},
            headers=_bearer(tenant.generated.secret),
        )

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "expires_at_in_past"


async def test_unauthenticated_requests_are_401(settings: Settings, db_engine: AsyncEngine) -> None:
    async with client_with_db(settings, db_engine) as (client, _):
        for call in (
            client.post("/v1/api-keys", json={"name": "x"}),
            client.get("/v1/api-keys"),
            client.post("/v1/api-keys/key_nope/revoke"),
        ):
            response = await call
            assert response.status_code == 401
            assert response.json()["error"]["code"] == "missing_api_key"


# ── List ────────────────────────────────────────────────────────────────


async def test_list_returns_metadata_never_secrets(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, factory):
        tenant = await _tenant(factory, "list@example.com")
        created = await client.post(
            "/v1/api-keys",
            json={"name": "second"},
            headers=_bearer(tenant.generated.secret),
        )
        second_secret = created.json()["key"]

        response = await client.get("/v1/api-keys", headers=_bearer(tenant.generated.secret))

        assert response.status_code == 200
        data: list[dict[str, Any]] = response.json()["data"]
        assert len(data) == 2  # bootstrap key + second
        assert all(set(item) == RESPONSE_FIELDS for item in data)
        # Neither full secret appears anywhere in the listing:
        assert tenant.generated.secret not in response.text
        assert second_secret not in response.text


async def test_listing_is_tenant_scoped(settings: Settings, db_engine: AsyncEngine) -> None:
    async with client_with_db(settings, db_engine) as (client, factory):
        org_a = await _tenant(factory, "lista@example.com", org="OrgA")
        org_b = await _tenant(factory, "listb@example.com", org="OrgB")

        listing = await client.get("/v1/api-keys", headers=_bearer(org_a.generated.secret))

        ids = {item["id"] for item in listing.json()["data"]}
        assert org_a.api_key.public_id in ids
        assert org_b.api_key.public_id not in ids


# ── Revoke ──────────────────────────────────────────────────────────────


async def test_revoke_takes_effect_on_next_request_and_is_idempotent(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, factory):
        tenant = await _tenant(factory, "revoke@example.com")
        created = await client.post(
            "/v1/api-keys",
            json={"name": "victim"},
            headers=_bearer(tenant.generated.secret),
        )
        victim_secret = created.json()["key"]
        victim_id = created.json()["id"]

        first = await client.post(
            f"/v1/api-keys/{victim_id}/revoke",
            headers=_bearer(tenant.generated.secret),
        )
        assert first.status_code == 200
        revoked_at = first.json()["revoked_at"]
        assert revoked_at is not None

        # Immediate effect: the revoked key fails authentication.
        rejected = await client.get("/v1/organization", headers=_bearer(victim_secret))
        assert rejected.status_code == 401
        assert rejected.json()["error"]["code"] == "api_key_revoked"

        # Idempotent: same outcome, same timestamp, still 200.
        second = await client.post(
            f"/v1/api-keys/{victim_id}/revoke",
            headers=_bearer(tenant.generated.secret),
        )
        assert second.status_code == 200
        assert second.json()["revoked_at"] == revoked_at


async def test_cross_tenant_revoke_and_unknown_key_are_404(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """THE isolation test at the HTTP level, both directions plus unknown."""
    async with client_with_db(settings, db_engine) as (client, factory):
        org_a = await _tenant(factory, "xa@example.com", org="OrgA")
        org_b = await _tenant(factory, "xb@example.com", org="OrgB")

        for attacker, target in (
            (org_a, org_b.api_key.public_id),  # A attacks B
            (org_b, org_a.api_key.public_id),  # B attacks A
            (org_a, "key_000000000000000000000000"),  # nonexistent
        ):
            response = await client.post(
                f"/v1/api-keys/{target}/revoke",
                headers=_bearer(attacker.generated.secret),
            )
            assert response.status_code == 404
            err = response.json()["error"]
            assert err["type"] == "resource_not_found_error"
            assert err["code"] == "api_key_not_found"

        # And the attacked keys still work — nothing was revoked:
        for tenant in (org_a, org_b):
            ok = await client.get("/v1/organization", headers=_bearer(tenant.generated.secret))
            assert ok.status_code == 200


# ── Events ──────────────────────────────────────────────────────────────


async def test_revocation_emits_event_once(
    settings: Settings,
    db_engine: AsyncEngine,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(settings)
    async with client_with_db(settings, db_engine) as (client, factory):
        tenant = await _tenant(factory, "events@example.com")
        created = await client.post(
            "/v1/api-keys",
            json={"name": "event-victim"},
            headers=_bearer(tenant.generated.secret),
        )
        victim_id = created.json()["id"]

        for _ in range(2):  # revoke twice: transition once, no-op once
            await client.post(
                f"/v1/api-keys/{victim_id}/revoke",
                headers=_bearer(tenant.generated.secret),
            )

    out = capsys.readouterr().out
    assert out.count("apikey.revoked") == 1
    assert victim_id in out
