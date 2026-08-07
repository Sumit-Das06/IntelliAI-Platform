"""The console shell: served, navigable, invisible to the API contract.

The console is pages, not APIs — it must render the platform shell,
serve its shared assets with honest content types, keep the OpenAPI
schema untouched, and obey the public product rule: customers see
IntelliAI services, never foundation-model names.
"""

from importlib.resources import files

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from intelliai_api.core.config import Settings
from tests.helpers import client_with_db

pytestmark = pytest.mark.anyio


async def test_the_dashboard_is_served_as_html(settings: Settings, db_engine: AsyncEngine) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        response = await client.get("/console")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'data-page="dashboard"' in response.text
    assert "Welcome to IntelliAI" in response.text


async def test_the_keys_page_is_served_as_html(settings: Settings, db_engine: AsyncEngine) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        response = await client.get("/console/keys")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'data-page="keys"' in response.text
    assert "Manage API keys for accessing IntelliAI AI Services." in response.text
    # The page carries its own empty state and the shown-once warning:
    # both are product promises, not decoration.
    assert "No API Keys Yet" in response.text
    assert "it will never be shown again" in response.text


async def test_the_services_page_is_served_as_html(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        response = await client.get("/console/services")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'data-page="services"' in response.text
    assert "The IntelliAI product catalogue" in response.text


async def test_the_catalogue_speaks_in_products_and_languages(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # The catalogue data lives in the shared console kit: categories are
    # product truths (Speech, Document Intelligence, ...), languages carry
    # honest tiers (Hindi and Arabic are beta), and every future service
    # is one entry — this test pins the vocabulary customers see.
    async with client_with_db(settings, db_engine) as (client, _factory):
        js = (await client.get("/console/assets/console.js")).text

    for category in (
        "Speech",
        "Speech Synthesis",
        "Document Intelligence",
        "Translation",
        "Vision",
        "LLM",
    ):
        assert category in js
    assert '{ name: "English", tier: "production" }' in js
    assert '{ name: "Hindi", tier: "beta" }' in js
    assert '{ name: "Arabic", tier: "beta" }' in js


async def test_the_root_url_leads_to_the_console(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # A platform whose front door 404s is not a platform.
    async with client_with_db(settings, db_engine) as (client, _factory):
        response = await client.get("/")

    assert response.status_code == 307
    assert response.headers["location"] == "/console"


async def test_the_shared_assets_are_served_with_their_types(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        css = await client.get("/console/assets/console.css")
        js = await client.get("/console/assets/console.js")

    assert css.status_code == 200
    assert css.headers["content-type"].startswith("text/css")
    assert "--accent" in css.text  # the design tokens live here
    assert js.status_code == 200
    assert js.headers["content-type"].startswith("text/javascript")
    assert "IntelliAI" in js.text


async def test_an_unknown_asset_is_a_plain_404(settings: Settings, db_engine: AsyncEngine) -> None:
    # The allowlist is the whole route: no directory semantics, no
    # traversal surface, no error event for a mistyped filename.
    async with client_with_db(settings, db_engine) as (client, _factory):
        response = await client.get("/console/assets/secrets.txt")

    assert response.status_code == 404


async def test_the_navigation_carries_the_whole_platform(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # The IA ships complete on day one: live pages link, future pages
    # show as Soon — adding a service is one NAV entry, nothing else.
    async with client_with_db(settings, db_engine) as (client, _factory):
        js = (await client.get("/console/assets/console.js")).text

    for label in (
        "Dashboard",
        "API Keys",
        "Playground",
        "AI Services",
        "Speech Samples",
        "Datasets",
        "Usage",
        "Logs",
        "Settings",
        "Billing",
    ):
        assert label in js
    for service in (
        "IntelliAI STT",
        "IntelliAI TTS",
        "IntelliAI OCR",
        "IntelliAI Translate",
        "IntelliAI Vision",
        "IntelliAI LLM",
    ):
        assert service in js
    # Pages that have shipped must be LIVE in the registry — reverting a
    # flip would silently unlink a working page from the whole console.
    for live_entry in (
        '{ id: "dashboard", label: "Dashboard", href: "/console", status: "live" }',
        '{ id: "keys", label: "API Keys", href: "/console/keys", status: "live" }',
        '{ id: "playground", label: "Playground", href: "/console/playground", status: "live" }',
        '{ id: "services", label: "AI Services", href: "/console/services", status: "live" }',
    ):
        assert live_entry in js


async def test_the_public_product_rule_holds(settings: Settings, db_engine: AsyncEngine) -> None:
    # Customers see IntelliAI STT. Foundation models are an
    # implementation detail and never appear in the console.
    async with client_with_db(settings, db_engine) as (client, _factory):
        pages = [
            (await client.get("/console")).text,
            (await client.get("/console/keys")).text,
            (await client.get("/console/services")).text,
            (await client.get("/console/playground")).text,
            (await client.get("/console/assets/console.js")).text,
            (await client.get("/console/assets/console.css")).text,
        ]

    for text in pages:
        assert "whisper" not in text.lower()


async def test_the_openapi_schema_is_unchanged(settings: Settings, db_engine: AsyncEngine) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        schema = (await client.get("/openapi.json")).json()

    # Pages, not APIs: nothing under /console enters the contract.
    assert not any(path.startswith("/console") for path in schema["paths"])
    assert "/" not in schema["paths"]


def test_the_console_assets_ship_inside_the_package() -> None:
    # importlib.resources is how the routes read them, so this is exactly
    # the packaging guarantee: wherever the package goes, the console goes.
    console = files("intelliai_api") / "static" / "console"
    for name in (
        "dashboard.html",
        "keys.html",
        "services.html",
        "studio.html",
        "console.css",
        "console.js",
    ):
        asset = console / name
        assert asset.is_file()
