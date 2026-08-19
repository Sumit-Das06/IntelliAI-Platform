"""/v1/models: a product catalog that never leaks implementation."""

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from intelliai_api.core.config import Settings
from intelliai_api.services.identity import BootstrapResult, IdentityService
from tests.helpers import client_with_db

pytestmark = pytest.mark.anyio

PEPPER = "test-pepper"

# Words that must NEVER appear in a customer-facing catalog response:
# artifacts, engines, upstreams, licenses, precision, topology.
FORBIDDEN_TERMS = (
    "whisper",
    "qwen",
    "llama",
    "gguf",
    "kokoro",
    "hexgrad",
    "artifact",
    "engine",
    "faster",
    "systran",
    "license",
    "apache",
    "int8",
    "runtime",
    "ct2",
)


async def _tenant(factory: async_sessionmaker[AsyncSession], email: str) -> BootstrapResult:
    async with factory() as session:
        result = await IdentityService(session, pepper=PEPPER).bootstrap_organization(
            organization_name="CatalogCo", owner_email=email, owner_name="Owner"
        )
        await session.commit()
        return result


def _bearer(secret: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {secret}"}


async def test_list_is_openai_shaped_product_catalog(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, factory):
        tenant = await _tenant(factory, "models-list@example.com")
        response = await client.get("/v1/models", headers=_bearer(tenant.generated.secret))
        assert response.status_code == 200
        body = response.json()
        assert body["object"] == "list"
        models = {model["id"]: model for model in body["data"]}
        assert set(models) == {"intelliai-stt", "intelliai-tts"}
        for model in models.values():
            assert model["object"] == "model"
            assert model["owned_by"] == "intelliai"
            assert isinstance(model["created"], int) and model["created"] > 0
        assert models["intelliai-stt"]["description"] == "IntelliAI speech-to-text"
        assert models["intelliai-tts"]["description"] == "IntelliAI text-to-speech"


async def test_catalog_never_leaks_implementation(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, factory):
        tenant = await _tenant(factory, "models-leak@example.com")
        response = await client.get("/v1/models", headers=_bearer(tenant.generated.secret))
        lowered = response.text.lower()
        for term in FORBIDDEN_TERMS:
            assert term not in lowered, f"catalog response leaks {term!r}"


async def test_retrieve_and_unknown(settings: Settings, db_engine: AsyncEngine) -> None:
    async with client_with_db(settings, db_engine) as (client, factory):
        tenant = await _tenant(factory, "models-get@example.com")
        headers = _bearer(tenant.generated.secret)
        found = await client.get("/v1/models/intelliai-stt", headers=headers)
        assert found.status_code == 200
        assert found.json()["id"] == "intelliai-stt"
        missing = await client.get("/v1/models/gpt-4o", headers=headers)
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "model_not_found"


async def test_auth_is_required(settings: Settings, db_engine: AsyncEngine) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        assert (await client.get("/v1/models")).status_code == 401
