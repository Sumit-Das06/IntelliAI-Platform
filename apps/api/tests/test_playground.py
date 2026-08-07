"""The playground page: served, honest about consent, invisible to the API.

A page, not an API: it must render for a phone browser, carry the
permanent consent notice, and leave the OpenAPI contract untouched.
Since the console shell landed, the page lives at /console/playground;
the original /playground URL redirects so cohort bookmarks keep working.
"""

from importlib.resources import files

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from intelliai_api.core.config import Settings
from tests.helpers import client_with_db

pytestmark = pytest.mark.anyio

CONSENT_SENTENCE = "Recordings, transcripts, and submitted corrections may be stored to improve"


async def test_the_page_is_served_as_html(settings: Settings, db_engine: AsyncEngine) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        response = await client.get("/console/playground")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "IntelliAI STT Playground" in response.text


async def test_the_original_url_still_reaches_the_page(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # Cohort members bookmarked /playground before the console existed;
    # that link must keep working forever.
    async with client_with_db(settings, db_engine) as (client, _factory):
        redirect = await client.get("/playground")
        followed = await client.get("/playground", follow_redirects=True)

    assert redirect.status_code == 307
    assert redirect.headers["location"] == "/console/playground"
    assert followed.status_code == 200
    assert "IntelliAI STT Playground" in followed.text


async def test_the_consent_notice_is_permanently_visible(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        response = await client.get("/console/playground")

    assert CONSENT_SENTENCE in response.text
    assert "Do not record other people without permission" in response.text


async def test_the_openapi_schema_is_unchanged(settings: Settings, db_engine: AsyncEngine) -> None:
    async with client_with_db(settings, db_engine) as (client, _factory):
        schema = (await client.get("/openapi.json")).json()

    # A page, not an API: no schema entry — and the real API is intact.
    assert "/playground" not in schema["paths"]
    assert "/v1/audio/transcriptions" in schema["paths"]
    assert "/v1/audio/transcriptions/{sample_id}/correction" in schema["paths"]


def test_the_asset_ships_inside_the_package() -> None:
    # importlib.resources is how the route reads it, so this is exactly
    # the packaging guarantee: wherever the package goes, the page goes.
    asset = files("intelliai_api") / "static" / "playground.html"
    assert asset.is_file()
    assert "IntelliAI STT Playground" in asset.read_text(encoding="utf-8")
