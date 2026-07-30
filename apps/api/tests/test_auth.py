"""Authentication tests: the pipeline HTTP-free, then through the full app.

The HTTP tests run the real app in-process (ASGITransport, same event
loop) with its session factory bound to the rolled-back test connection —
full-stack authentication against real Postgres, zero residue.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from intelliai_api.core.config import Settings
from intelliai_api.core.errors import AuthenticationError
from intelliai_api.core.time import utc_now
from intelliai_api.main import create_app
from intelliai_api.services.auth import AuthService
from intelliai_api.services.identity import BootstrapResult, IdentityService

pytestmark = pytest.mark.anyio

PEPPER = "test-pepper"  # must match conftest AuthSettings


async def _bootstrap(session: AsyncSession, email: str = "auth@example.com") -> BootstrapResult:
    return await IdentityService(session, pepper=PEPPER).bootstrap_organization(
        organization_name="AuthCo", owner_email=email, owner_name="Owner"
    )


# ── Service level: the pipeline without HTTP ────────────────────────────


async def test_valid_key_yields_immutable_auth_context(db_session: AsyncSession) -> None:
    result = await _bootstrap(db_session)
    service = AuthService(db_session, pepper=PEPPER)

    context = await service.authenticate(result.generated.secret, request_id="req_test")

    assert context.organization_id == result.organization.id
    assert context.organization_public_id.startswith("org_")
    assert context.key_public_id == result.api_key.public_id
    assert context.request_id == "req_test"
    assert context.authenticated_at.tzinfo is not None
    with pytest.raises(AttributeError):
        context.organization = context.organization  # type: ignore[misc]


async def test_authentication_stamps_last_used(db_session: AsyncSession) -> None:
    result = await _bootstrap(db_session)
    await AuthService(db_session, pepper=PEPPER).authenticate(result.generated.secret)
    await db_session.refresh(result.api_key)
    assert result.api_key.last_used_at is not None


@pytest.mark.parametrize(
    "candidate",
    ["", "garbage", "ik_live_short", "ik_live_" + "A" * 43],  # last: well-formed, unknown
)
async def test_unknown_or_malformed_keys_are_invalid(
    db_session: AsyncSession, candidate: str
) -> None:
    with pytest.raises(AuthenticationError) as excinfo:
        await AuthService(db_session, pepper=PEPPER).authenticate(candidate)
    assert excinfo.value.code == "invalid_api_key"


async def test_revoked_key_gets_its_own_code(db_session: AsyncSession) -> None:
    result = await _bootstrap(db_session)
    result.api_key.revoked_at = utc_now()
    await db_session.flush()

    with pytest.raises(AuthenticationError) as excinfo:
        await AuthService(db_session, pepper=PEPPER).authenticate(result.generated.secret)
    assert excinfo.value.code == "api_key_revoked"


async def test_expired_key_gets_its_own_code(db_session: AsyncSession) -> None:
    result = await _bootstrap(db_session)
    result.api_key.expires_at = utc_now() - timedelta(seconds=1)
    await db_session.flush()

    with pytest.raises(AuthenticationError) as excinfo:
        await AuthService(db_session, pepper=PEPPER).authenticate(result.generated.secret)
    assert excinfo.value.code == "api_key_expired"


# ── HTTP level: through the real app ────────────────────────────────────


@asynccontextmanager
async def _client_with_db(
    settings: Settings, db_engine: AsyncEngine
) -> AsyncIterator[tuple[AsyncClient, async_sessionmaker[AsyncSession]]]:
    """The real app, its sessions joined to one rolled-back transaction."""
    async with db_engine.connect() as connection:
        outer = await connection.begin()
        factory = async_sessionmaker(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        app = create_app(settings)
        app.state.session_factory = factory
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client, factory
        await outer.rollback()


async def test_missing_header_is_401_with_www_authenticate(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with _client_with_db(settings, db_engine) as (client, _):
        response = await client.get("/v1/organization")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "missing_api_key"


async def test_wrong_scheme_is_missing_api_key(settings: Settings, db_engine: AsyncEngine) -> None:
    async with _client_with_db(settings, db_engine) as (client, _):
        response = await client.get(
            "/v1/organization", headers={"Authorization": "Basic dXNlcjpwYXNz"}
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_api_key"


async def test_unknown_key_is_401_invalid(settings: Settings, db_engine: AsyncEngine) -> None:
    async with _client_with_db(settings, db_engine) as (client, _):
        response = await client.get(
            "/v1/organization",
            headers={"Authorization": "Bearer ik_live_" + "A" * 43},
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"


async def test_valid_key_reaches_the_protected_endpoint(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with _client_with_db(settings, db_engine) as (client, factory):
        async with factory() as session:
            result = await _bootstrap(session, email="http@example.com")
            await session.commit()

        response = await client.get(
            "/v1/organization",
            headers={"Authorization": f"Bearer {result.generated.secret}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == result.organization.public_id
    assert body["name"] == "AuthCo"
    assert "created_at" in body


async def test_revoked_key_is_rejected_over_http(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with _client_with_db(settings, db_engine) as (client, factory):
        async with factory() as session:
            result = await _bootstrap(session, email="revoked@example.com")
            result.api_key.revoked_at = utc_now()
            await session.commit()

        response = await client.get(
            "/v1/organization",
            headers={"Authorization": f"Bearer {result.generated.secret}"},
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "api_key_revoked"


async def test_auth_binds_org_and_key_into_request_logs(
    settings: Settings,
    db_engine: AsyncEngine,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async with _client_with_db(settings, db_engine) as (client, factory):
        async with factory() as session:
            result = await _bootstrap(session, email="logs@example.com")
            await session.commit()

        await client.get(
            "/v1/organization",
            headers={"Authorization": f"Bearer {result.generated.secret}"},
        )

    out = capsys.readouterr().out
    completed = [line for line in out.splitlines() if "request_completed" in line]
    assert completed, "expected a request_completed log line"
    assert result.organization.public_id in completed[-1]
    assert result.api_key.public_id in completed[-1]
    assert result.generated.secret not in out
