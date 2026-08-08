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


async def test_the_home_page_is_served_as_html(settings: Settings, db_engine: AsyncEngine) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        response = await client.get("/console/home")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'data-page="home"' in response.text
    assert "Welcome to IntelliAI Platform" in response.text
    assert "One API for Speech Intelligence today." in response.text
    # Recent Activity ships as an HONEST empty state until real data
    # wires in — no invented backend, no fake rows.
    assert "Recent Activity" in response.text
    assert "No activity yet" in response.text


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


async def test_the_samples_page_is_served_as_html(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        response = await client.get("/console/samples")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'data-page="samples"' in response.text
    assert "Speech Samples" in response.text
    # The data page carries the permanent consent notice and honest
    # empty/lifecycle vocabulary.
    assert "Recordings, transcripts, and submitted corrections may be stored" in response.text
    assert "No speech samples yet" in response.text
    assert "Lifecycle" in response.text


async def test_the_usage_page_is_served_as_html(settings: Settings, db_engine: AsyncEngine) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        response = await client.get("/console/usage")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'data-page="usage"' in response.text
    # The four stat cards, named exactly as the product names them.
    for card in (
        "API Requests",
        "Speech Minutes",
        "Average Request Duration",
        "Platform Success Rate",
    ):
        assert card in response.text
    # Success rate must state what it measures AND what it excludes.
    assert "Accepted requests completed by IntelliAI STT" in response.text
    assert "rejected as invalid before processing are excluded" in response.text
    # Services, not models: the public product identity.
    assert "Services Used" in response.text
    assert "IntelliAI STT" in response.text
    # Honest empty state with a way forward.
    assert "No API usage yet" in response.text
    assert "Open STT Studio" in response.text


async def test_usage_offers_exactly_the_three_periods(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # Changing the period must re-ask the API — the window is the
    # server's decision, never a client-side reslice of cached data.
    async with client_with_db(settings, db_engine) as (client, _factory):
        page = (await client.get("/console/usage")).text

    for days in (7, 30, 90):
        assert f'data-days="{days}"' in page
    assert 'data-days="30" aria-pressed="true"' in page  # the default
    assert '"/v1/usage/summary?days=" + days' in page


async def test_usage_never_rounds_into_a_perfect_or_empty_record(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # A window containing failures must never print 100%, and a window
    # containing successes must never print 0% — rounding may not cross
    # either boundary. The same honesty the API applies to null rates.
    async with client_with_db(settings, db_engine) as (client, _factory):
        page = (await client.get("/console/usage")).text

    assert 'if (rate < 1 && text === "100.0") text = "99.9";' in page
    assert 'if (rate > 0 && text === "0.0") return "<0.1%";' in page


async def test_usage_distinguishes_a_quiet_window_from_a_new_account(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # "No API usage yet" is a claim about the ACCOUNT. Telling an
    # established customer that during a quiet week would be false, so
    # the page only says it when the widest window is empty too.
    async with client_with_db(settings, db_engine) as (client, _factory):
        page = (await client.get("/console/usage")).text

    assert "No API requests in the last " in page
    assert "Your organization has usage outside this period" in page
    assert "/v1/usage/summary?days=90" in page


async def test_usage_names_services_from_the_catalogue(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # Public product names come from the shared registry, so a service
    # launched later is named correctly without editing this page — and
    # a raw model id is never shown as a product name.
    async with client_with_db(settings, db_engine) as (client, _factory):
        page = (await client.get("/console/usage")).text
        js = (await client.get("/console/assets/console.js")).text

    assert "IntelliAI.serviceName(entry.key)" in page
    assert 'id = String(publicModelId).replace(/^intelliai-/, "")' in js


async def test_usage_reads_only_the_usage_api(settings: Settings, db_engine: AsyncEngine) -> None:
    # The separation law from Commit 7, enforced on the page as well:
    # Usage never derives its numbers from the dataset APIs.
    async with client_with_db(settings, db_engine) as (client, _factory):
        page = (await client.get("/console/usage")).text

    assert "/v1/usage/summary" in page
    assert "/v1/speech-samples" not in page
    for dataset_word in ("Corrections", "Storage Used", "Dataset", "Consent"):
        assert dataset_word not in page


async def test_every_front_door_leads_to_home(settings: Settings, db_engine: AsyncEngine) -> None:
    # A platform whose front door 404s is not a platform — and both
    # roots land on Home, the page that answers "what should I do first?"
    async with client_with_db(settings, db_engine) as (client, _factory):
        root = await client.get("/")
        console = await client.get("/console")

    assert root.status_code == 307
    assert root.headers["location"] == "/console/home"
    assert console.status_code == 307
    assert console.headers["location"] == "/console/home"


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
        "Home",
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
        '{ id: "home", label: "Home", href: "/console/home", status: "live" }',
        '{ id: "keys", label: "API Keys", href: "/console/keys", status: "live" }',
        '{ id: "playground", label: "Playground", href: "/console/playground", status: "live" }',
        '{ id: "services", label: "AI Services", href: "/console/services", status: "live" }',
        '{ id: "samples", label: "Speech Samples", href: "/console/samples", status: "live" }',
        '{ id: "usage", label: "Usage", href: "/console/usage", status: "live" }',
    ):
        assert live_entry in js


async def test_the_public_product_rule_holds(settings: Settings, db_engine: AsyncEngine) -> None:
    # Customers see IntelliAI STT. Foundation models are an
    # implementation detail and never appear in the console.
    async with client_with_db(settings, db_engine) as (client, _factory):
        pages = [
            (await client.get("/console/home")).text,
            (await client.get("/console/keys")).text,
            (await client.get("/console/services")).text,
            (await client.get("/console/samples")).text,
            (await client.get("/console/usage")).text,
            (await client.get("/console/playground")).text,
            (await client.get("/console/assets/console.js")).text,
            (await client.get("/console/assets/console.css")).text,
        ]

    for text in pages:
        assert "whisper" not in text.lower()
        # Dashboard was renamed to Home in Commit 6; the old word must
        # never resurface on any console surface.
        assert "dashboard" not in text.lower()


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
        "home.html",
        "keys.html",
        "services.html",
        "studio.html",
        "samples.html",
        "usage.html",
        "console.css",
        "console.js",
    ):
        asset = console / name
        assert asset.is_file()
