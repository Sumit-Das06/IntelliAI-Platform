"""Per-request contribution opt-out: the X-IntelliAI-Contribution header.

The laws pinned here: the header can only NARROW collection —
organization consent remains the ceiling; ``off`` (case-insensitively,
trimmed) opts this request out of sample collection; anything absent,
unknown, or malformed preserves existing behavior; and none of it can
change the transcription response or fail the request. This is the
honest backing for the keyboard's "Improve IntelliAI STT" toggle.
"""

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from intelliai_api.core.config import Settings
from tests.helpers import client_with_db
from tests.test_collection import (
    SAMPLE_HEADER,
    _bearer,
    _post_kwargs,
    _rows,
    _tenant,
    install,
)
from tests.test_storage import FakeObjectStorage
from tests.test_transcriptions_api import FakeRuntimeClient, make_envelope

pytestmark = pytest.mark.anyio

CONTRIBUTION_HEADER = "X-IntelliAI-Contribution"


async def _transcribe(client: Any, secret: str, *, contribution: str | None = None) -> Any:
    headers = _bearer(secret)
    if contribution is not None:
        headers[CONTRIBUTION_HEADER] = contribution
    return await client.post(
        "/v1/audio/transcriptions", headers=headers, **_post_kwargs(language="en")
    )


async def test_contribution_off_collects_no_sample(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = FakeRuntimeClient(envelope=make_envelope())
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "contrib-off@example.com", consent=True)
        response = await _transcribe(client, tenant.generated.secret, contribution="off")

        # Transcription itself is untouched: 200, real transcript, no
        # sample header, and no stored object or row.
        assert response.status_code == 200
        assert response.json() == {"text": "ask not what your country"}
        assert SAMPLE_HEADER not in response.headers
        assert storage.puts == []
        samples, events = await _rows(factory, tenant.organization.id)
        assert samples == []
        assert events == []


async def test_contribution_absent_preserves_collection(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = FakeRuntimeClient(envelope=make_envelope())
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "contrib-absent@example.com", consent=True)
        response = await _transcribe(client, tenant.generated.secret)  # no header

        assert response.status_code == 200
        assert response.headers[SAMPLE_HEADER].startswith("smp_")
        samples, _ = await _rows(factory, tenant.organization.id)
        assert len(samples) == 1


async def test_org_consent_off_is_the_ceiling_contribution_cannot_widen(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # Consent OFF means nothing is collected, no matter what the client
    # sends — the header can only narrow, never widen.
    runtime = FakeRuntimeClient(envelope=make_envelope())
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "contrib-noconsent@example.com", consent=False)
        # Even with the header absent (the "contribute" default) there is
        # no sample, because consent is the ceiling.
        response = await _transcribe(client, tenant.generated.secret)

        assert response.status_code == 200
        assert SAMPLE_HEADER not in response.headers
        samples, _ = await _rows(factory, tenant.organization.id)
        assert samples == []


async def test_off_is_case_and_space_insensitive(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = FakeRuntimeClient(envelope=make_envelope())
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "contrib-variants@example.com", consent=True)
        for value in ("off", "OFF", "  Off  "):
            response = await _transcribe(client, tenant.generated.secret, contribution=value)
            assert response.status_code == 200, value
            assert SAMPLE_HEADER not in response.headers, value
        samples, _ = await _rows(factory, tenant.organization.id)
        assert samples == []


async def test_malformed_values_preserve_collection_and_never_fail(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # A metadata header must never fail a transcription, and only the
    # exact opt-out token opts out — everything else behaves as before.
    runtime = FakeRuntimeClient(envelope=make_envelope())
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "contrib-malformed@example.com", consent=True)
        # Only the exact token "off" opts out; near-misses do not.
        values = ("on", "true", "1", "no", "disable", "of", "offx", "")
        for value in values:
            response = await _transcribe(client, tenant.generated.secret, contribution=value)
            assert response.status_code == 200, value
            assert response.json() == {"text": "ask not what your country"}, value
            assert response.headers[SAMPLE_HEADER].startswith("smp_"), value
        samples, _ = await _rows(factory, tenant.organization.id)
        # One collected sample per non-opt-out request above.
        assert len(samples) == len(values)


async def test_client_label_and_contribution_compose(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # The keyboard's real combination: identified as keyboard/1.0 AND
    # opting this request out. Label is recorded intent; contribution
    # off means no sample exists to carry it.
    runtime = FakeRuntimeClient(envelope=make_envelope())
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "contrib-keyboard@example.com", consent=True)
        response = await client.post(
            "/v1/audio/transcriptions",
            headers={
                **_bearer(tenant.generated.secret),
                "X-IntelliAI-Client": "keyboard/1.0",
                CONTRIBUTION_HEADER: "off",
            },
            **_post_kwargs(language="en"),
        )
        assert response.status_code == 200
        assert SAMPLE_HEADER not in response.headers
        samples, _ = await _rows(factory, tenant.organization.id)
        assert samples == []
