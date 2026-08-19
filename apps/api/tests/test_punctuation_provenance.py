"""M30 punctuation provenance: raw original, served current, event trail.

The laws held here: when the runtime's punctuation stage rewrote the
served text (contract field ``raw_text``), the immutable
``original_transcript`` is the RAW ASR output, ``current_transcript``
starts as what the user was SHOWN, the append-only trail reads
collected → punctuated (→ corrected), the public response body carries
only the final text, and billing never changes. With no stage (raw_text
absent) every pre-M30 behavior is byte-identical — pinned by the
existing collection suite, untouched.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from intelliai_api.core.config import Settings
from intelliai_api.db.models import UsageEvent
from intelliai_runtime_contract import (
    RuntimeResponse,
    RuntimeTiming,
    TranscriptionResult,
    TranscriptionSegment,
    Usage,
    UsageUnit,
)
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
from tests.test_transcriptions_api import META, FakeRuntimeClient

pytestmark = pytest.mark.anyio

RAW = "मैं घर जा रहा हूँ आप क्या कर रहे हैं"
PUNCTUATED = "मैं घर जा रहा हूँ। आप क्या कर रहे हैं?"


def punctuated_envelope() -> RuntimeResponse[TranscriptionResult]:
    return RuntimeResponse[TranscriptionResult](
        output=TranscriptionResult(
            text=PUNCTUATED,
            language="hi",
            duration_seconds=8.0,
            segments=(TranscriptionSegment(start_seconds=0.0, end_seconds=8.0, text=PUNCTUATED),),
            raw_text=RAW,
        ),
        model="qwen3-asr-0.6b-hi-ft-e3",
        usage=(Usage(unit=UsageUnit.AUDIO_SECONDS, amount=8.0),),
        timing=RuntimeTiming(total_ms=900.0, stages={"inference": 700.0, "punctuation": 45.0}),
        runtime=META,
    )


async def test_punctuated_result_stores_raw_original_and_served_current(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = FakeRuntimeClient(envelope=punctuated_envelope())
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "punct-provenance@example.com", consent=True)
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **_post_kwargs(language="hi"),
        )

        assert response.status_code == 200
        # The customer sees ONLY the final punctuated text — no raw field,
        # no stage vocabulary, in the public body.
        assert response.json() == {"text": PUNCTUATED}
        sample_id = response.headers[SAMPLE_HEADER]

        (sample,), events = await _rows(factory, tenant.organization.id)
        assert sample.public_id == sample_id
        # The flywheel's ground truth stays the machine's RAW words:
        assert sample.original_transcript == RAW
        # ...and the user corrects what the user was shown:
        assert sample.current_transcript == PUNCTUATED
        assert [event.event for event in events] == ["collected", "punctuated"]
        punctuated_event = events[-1]
        assert punctuated_event.detail == {
            "stage": "punctuation-restoration",
            "restorer": "hi-punct-v1",
        }


async def test_correction_on_a_punctuated_sample_keeps_all_three_forms(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = FakeRuntimeClient(envelope=punctuated_envelope())
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "punct-correction@example.com", consent=True)
        created = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **_post_kwargs(language="hi"),
        )
        sample_id = created.headers[SAMPLE_HEADER]

        corrected_text = "मैं घर जा रहा हूँ! आप क्या कर रहे हैं?"
        corrected = await client.post(
            f"/v1/audio/transcriptions/{sample_id}/correction",
            headers=_bearer(tenant.generated.secret),
            json={"corrected_text": corrected_text},
        )
        assert corrected.status_code == 200

        (sample,), events = await _rows(factory, tenant.organization.id)
        # raw ASR → punctuated → human corrected: nothing lost.
        assert sample.original_transcript == RAW
        assert sample.current_transcript == corrected_text
        assert [event.event for event in events] == ["collected", "punctuated", "corrected"]


async def test_punctuation_adds_zero_billed_units(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    runtime = FakeRuntimeClient(envelope=punctuated_envelope())
    storage = FakeObjectStorage()
    async with client_with_db(settings, db_engine, install(runtime, storage)) as (
        client,
        factory,
    ):
        tenant = await _tenant(factory, "punct-billing@example.com", consent=True)
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **_post_kwargs(language="hi"),
        )
        assert response.status_code == 200

        from sqlalchemy import func, select

        async with factory() as session:
            billed = await session.scalar(
                select(func.count(UsageEvent.id)).where(
                    UsageEvent.organization_id == tenant.organization.id
                )
            )
        # Exactly one usage event — the AUDIO seconds. Text length and
        # punctuation processing are never billable quantities, and a
        # rewritten transcript never bills twice.
        assert billed == 1
