"""Language-routed serving, end to end through the real gateway.

One public model, several artifacts, resolved per request from registry
state — over the full HTTP stack, the real ledger, the real admission and
entitlement checks. The runtimes are fakes, which is the point: nothing
above the runtime's engine module knows an engine exists, so a *routing*
proof needs no models.

What is being proven is a boundary as much as a feature. The gateway
supplies the customer's declaration and accepts whatever the registry
returns; it contains no `if language == ...` anywhere, and the tests
below would keep passing if it did — which is why the routing decisions
they exercise are all expressed as catalog records, never as code.
"""

from datetime import UTC, date, datetime
from typing import Any

import pytest
import structlog
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from intelliai_api.api.v1.audio.speech import SpeechRequest
from intelliai_api.core.config import Settings
from intelliai_api.db.models import UsageEvent, UsageOrigin
from intelliai_api.db.repositories import UsageEventRepository
from intelliai_api.entitlements import period_for
from intelliai_api.pricing import INTERNAL_V1, PriceBookCatalog, rate_events
from intelliai_api.registry import (
    ArtifactRecord,
    LanguageEvidence,
    LanguageStatus,
    LicenseVerdict,
    PublicModelRecord,
    PublicVoiceRecord,
    Registry,
    RouteSelector,
    ServingRoute,
)
from intelliai_api.services.identity import BootstrapResult, IdentityService
from intelliai_runtime_contract import Capability
from tests.helpers import client_with_db
from tests.test_speech_api import FakeSynthesisClient
from tests.test_speech_api import make_envelope as make_speech_envelope
from tests.test_transcriptions_api import FakeRuntimeClient
from tests.test_transcriptions_api import make_envelope as make_stt_envelope

pytestmark = pytest.mark.anyio

PEPPER = "test-pepper"

MIT = LicenseVerdict(
    license="MIT",
    commercial_use=True,
    verified_on=date(2026, 7, 31),
    source="https://example.com/license",
    covers="the whole serving path for this route",
)

EVIDENCE = LanguageEvidence(
    corpus="stt-eval-seed@v1",
    quality_baseline="test-baseline",
    production_benchmark="test-benchmark",
    approval="test approval",
    approved_on=date(2026, 8, 5),
)


def _artifact(artifact_id: str, capability: Capability) -> ArtifactRecord:
    return ArtifactRecord(
        id=artifact_id,
        version=1,
        capability=capability,
        provenance="language routing test",
        license=MIT,
    )


def _route(language: str, artifact_id: str | None, **over: Any) -> ServingRoute:
    fields: dict[str, Any] = {
        "public_model_id": "intelliai-stt",
        "selector": RouteSelector(language=language),
        "status": LanguageStatus.AVAILABLE if artifact_id else LanguageStatus.UNAVAILABLE,
    }
    if artifact_id is not None:
        fields["artifact_id"] = artifact_id
        fields["license"] = MIT
    fields.update(over)
    return ServingRoute.model_validate(fields)


def stt_registry(*, hindi_deployment: str | None = None) -> Registry:
    """One public model, three artifacts, routed by declared language.

    `en` is a promise with evidence, `hi` is served best-effort by a
    different artifact, `ar` is refused. Every one of those is a record.
    """
    return Registry(
        artifacts=[
            _artifact("whisper-small", Capability.TRANSCRIPTION),
            _artifact("future-hi-v1", Capability.TRANSCRIPTION),
        ],
        models=[
            PublicModelRecord(
                id="intelliai-stt",
                capability=Capability.TRANSCRIPTION,
                service="stt-runtime",
                artifact_id="whisper-small",
                released=date(2026, 8, 2),
            )
        ],
        routes=[
            _route("en", "whisper-small", status=LanguageStatus.SUPPORTED, evidence=EVIDENCE),
            _route("hi", "future-hi-v1", deployment=hindi_deployment),
            _route("ar", None),
        ],
    )


def install(registry: Registry, **clients: Any) -> Any:
    def configure(app: FastAPI) -> None:
        app.state.registry = registry
        app.state.runtime_clients = dict(clients)

    return configure


async def _tenant(factory: async_sessionmaker[AsyncSession], email: str) -> BootstrapResult:
    async with factory() as session:
        result = await IdentityService(session, pepper=PEPPER).bootstrap_organization(
            organization_name="RoutingCo", owner_email=email, owner_name="Owner"
        )
        await session.commit()
        return result


def _bearer(secret: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {secret}"}


def post_kwargs(**form: str) -> dict[str, Any]:
    return {
        "files": {"file": ("clip.wav", b"fake-wav-bytes", "audio/wav")},
        "data": {"model": "intelliai-stt", **form},
    }


# ── One public model, two artifacts, routed by declared language ────────


@pytest.mark.parametrize(
    ("language", "artifact"),
    [("en", "whisper-small"), ("hi", "future-hi-v1"), ("hi-IN", "future-hi-v1")],
)
async def test_declared_language_selects_the_artifact(
    settings: Settings, db_engine: AsyncEngine, language: str, artifact: str
) -> None:
    fake = FakeRuntimeClient(envelope=make_stt_envelope())
    configure = install(stt_registry(), **{"stt-runtime": fake})
    async with client_with_db(settings, db_engine, configure) as (client, factory):
        tenant = await _tenant(factory, f"route-{language}@example.com")
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **post_kwargs(language=language),
        )
        assert response.status_code == 200
        # The ARTIFACT that crossed the plane is the routing proof; the
        # public model the customer named never changed.
        (call,) = fake.calls
        assert call[1].model == artifact
        # The full tag reaches the runtime; only ROUTING normalized it.
        assert call[1].language == language


async def test_an_undeclared_language_takes_the_default_route(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeRuntimeClient(envelope=make_stt_envelope())
    configure = install(stt_registry(), **{"stt-runtime": fake})
    async with client_with_db(settings, db_engine, configure) as (client, factory):
        tenant = await _tenant(factory, "route-none@example.com")
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **post_kwargs(),
        )
        assert response.status_code == 200
        assert fake.calls[0][1].model == "whisper-small"


async def test_the_public_response_is_identical_whichever_artifact_served(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # The Commercial Identity Invariant at the routing layer: routing
    # changes which artifact serves, and nothing the customer can see.
    bodies: list[bytes] = []
    for language in ("en", "hi"):
        fake = FakeRuntimeClient(envelope=make_stt_envelope())
        configure = install(stt_registry(), **{"stt-runtime": fake})
        async with client_with_db(settings, db_engine, configure) as (client, factory):
            tenant = await _tenant(factory, f"same-{language}@example.com")
            response = await client.post(
                "/v1/audio/transcriptions",
                headers=_bearer(tenant.generated.secret),
                **post_kwargs(language=language, response_format="verbose_json"),
            )
            assert response.status_code == 200
            bodies.append(response.content)
    assert bodies[0] == bodies[1]


# ── The commercial continuity fingerprint, per route ────────────────────


async def _commercial_fingerprint(
    settings: Settings, db_engine: AsyncEngine, *, language: str, email: str
) -> tuple[Any, ...]:
    """Everything commercially visible about one language-routed request."""
    fake = FakeRuntimeClient(envelope=make_stt_envelope())
    configure = install(stt_registry(), **{"stt-runtime": fake})
    async with client_with_db(settings, db_engine, configure) as (client, factory):
        tenant = await _tenant(factory, email)
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **post_kwargs(language=language),
        )
        assert response.status_code == 200
        async with factory() as session:
            events = list(
                await UsageEventRepository(session).list_for_organization(
                    tenant.organization.id,
                    since=datetime(2020, 1, 1, tzinfo=UTC),
                    until=datetime(2099, 1, 1, tzinfo=UTC),
                )
            )
            (event,) = events
            period = period_for(event.occurred_at)
            quota = await UsageEventRepository(session).totals_for_organization(
                tenant.organization.id,
                since=period.start,
                until=period.end,
                origins=[UsageOrigin.CUSTOMER],
            )
            await session.commit()
        rated = rate_events(
            events,
            organization_public_id="org_fixed",
            period_label=period.label,
            catalog=PriceBookCatalog(books=(INTERNAL_V1,)),
        )
    return (
        response.status_code,
        response.content,
        response.headers["content-type"],
        frozenset(key.lower() for key in response.headers),
        event.capability,
        event.public_model_id,
        event.origin,
        event.outcome,
        event.billable,
        tuple(sorted((q.unit, q.amount) for q in event.quantities)),
        tuple(sorted(quota.items())),
        rated.subtotal,
        rated.total,
        rated.currency,
        rated.price_book_versions,
        rated.rating_algorithm_version,
    )


async def test_the_commercial_fingerprint_is_identical_per_route(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """Two routes, two artifacts, one commercial identity.

    The M4 continuity proof, now driven by real routing rather than by a
    re-pointed default route: the customer bought `intelliai-stt`, and
    which artifact answered is not a commercial fact.
    """
    english = await _commercial_fingerprint(
        settings, db_engine, language="en", email="fingerprint-en@example.com"
    )
    hindi = await _commercial_fingerprint(
        settings, db_engine, language="hi", email="fingerprint-hi@example.com"
    )
    assert english == hindi


async def test_language_is_recorded_as_a_fact_without_touching_the_money(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # The other half of the fingerprint: language must be IN the ledger
    # and OUT of the pricing. A proof that nothing changed is worthless
    # if the thing that should change did not.
    fake = FakeRuntimeClient(envelope=make_stt_envelope())
    configure = install(stt_registry(), **{"stt-runtime": fake})
    async with client_with_db(settings, db_engine, configure) as (client, factory):
        tenant = await _tenant(factory, "fact@example.com")
        await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **post_kwargs(language="hi-IN"),
        )
        async with factory() as session:
            event = (
                await session.scalars(
                    select(UsageEvent).where(UsageEvent.organization_id == tenant.organization.id)
                )
            ).one()
            # The OBSERVED language, as the runtime reported it — a fact,
            # not the declaration that did the routing.
            assert event.language == "en"


# ── Deployment-keyed clients ────────────────────────────────────────────


async def test_a_route_reaches_the_deployment_that_hosts_its_artifact(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # Two deployments of ONE capability service: the registry says which
    # hosts the artifact, and the gateway calls that one.
    default_client = FakeRuntimeClient(envelope=make_stt_envelope())
    indic_client = FakeRuntimeClient(envelope=make_stt_envelope())
    configure = install(
        stt_registry(hindi_deployment="stt-runtime-indic"),
        **{"stt-runtime": default_client, "stt-runtime-indic": indic_client},
    )
    async with client_with_db(settings, db_engine, configure) as (client, factory):
        tenant = await _tenant(factory, "deployment@example.com")
        headers = _bearer(tenant.generated.secret)
        await client.post("/v1/audio/transcriptions", headers=headers, **post_kwargs(language="hi"))
        await client.post("/v1/audio/transcriptions", headers=headers, **post_kwargs(language="en"))
    assert [call[1].model for call in indic_client.calls] == ["future-hi-v1"]
    assert [call[1].model for call in default_client.calls] == ["whisper-small"]


async def test_an_unconfigured_deployment_is_an_operations_error_not_the_customers(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    configure = install(
        stt_registry(hindi_deployment="stt-runtime-indic"),
        **{"stt-runtime": FakeRuntimeClient(envelope=make_stt_envelope())},
    )
    async with client_with_db(settings, db_engine, configure) as (client, factory):
        tenant = await _tenant(factory, "missing-deployment@example.com")
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **post_kwargs(language="hi"),
        )
        assert response.status_code == 500
        assert "stt-runtime-indic" not in response.text  # topology is not customer surface


# ── Refusal, and the demand it records ──────────────────────────────────


async def test_an_unavailable_language_is_refused_honestly(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeRuntimeClient(envelope=make_stt_envelope())
    configure = install(stt_registry(), **{"stt-runtime": fake})
    async with client_with_db(settings, db_engine, configure) as (client, factory):
        tenant = await _tenant(factory, "refused@example.com")
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **post_kwargs(language="ar"),
        )
        assert response.status_code == 400
        error = response.json()["error"]
        assert error["code"] == "language_not_supported"
        assert error["param"] == "language"
        # It names what IS served, so the caller can act on the answer.
        assert "en" in error["message"] and "hi" in error["message"]
        # Nothing crossed the plane: no inference, no cost, no ledger row.
        assert fake.calls == []


async def test_a_refusal_produces_no_billable_event(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    configure = install(
        stt_registry(), **{"stt-runtime": FakeRuntimeClient(envelope=make_stt_envelope())}
    )
    async with client_with_db(settings, db_engine, configure) as (client, factory):
        tenant = await _tenant(factory, "refused-ledger@example.com")
        await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **post_kwargs(language="ar"),
        )
        async with factory() as session:
            events = await session.scalars(
                select(UsageEvent).where(UsageEvent.organization_id == tenant.organization.id)
            )
            assert list(events.all()) == []


async def test_a_refusal_is_recorded_as_demand_evidence(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # The only evidence we will ever have that someone wanted Arabic.
    configure = install(
        stt_registry(), **{"stt-runtime": FakeRuntimeClient(envelope=make_stt_envelope())}
    )
    async with client_with_db(settings, db_engine, configure) as (client, factory):
        tenant = await _tenant(factory, "demand@example.com")
        with structlog.testing.capture_logs() as logs:
            await client.post(
                "/v1/audio/transcriptions",
                headers=_bearer(tenant.generated.secret),
                **post_kwargs(language="ar-EG"),
            )
    refusals = [entry for entry in logs if entry["event"] == "language.refused"]
    assert len(refusals) == 1
    refusal = refusals[0]
    assert refusal["capability"] == "transcription"
    assert refusal["model"] == "intelliai-stt"
    assert refusal["language"] == "ar"
    assert refusal["served_languages"] == ["en", "hi"]
    assert refusal["organization_id"] == tenant.organization.public_id


async def test_a_refusal_never_leaks_implementation(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    configure = install(
        stt_registry(), **{"stt-runtime": FakeRuntimeClient(envelope=make_stt_envelope())}
    )
    async with client_with_db(settings, db_engine, configure) as (client, factory):
        tenant = await _tenant(factory, "refused-leak@example.com")
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            **post_kwargs(language="ar"),
        )
    lowered = response.text.lower()
    for term in ("whisper", "future-hi-v1", "artifact", "deployment", "route", "openai"):
        assert term not in lowered, f"refusal leaks {term!r}"


# ── Capability precedence ───────────────────────────────────────────────


async def test_the_wrong_capability_is_reported_before_the_language(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # Asking a synthesis model to transcribe is the more fundamental
    # mistake; hearing about a language it never served would mislead.
    registry = Registry(
        artifacts=[
            _artifact("whisper-small", Capability.TRANSCRIPTION),
            _artifact("kokoro-82m", Capability.SPEECH_SYNTHESIS),
        ],
        models=[
            PublicModelRecord(
                id="intelliai-stt",
                capability=Capability.TRANSCRIPTION,
                service="stt-runtime",
                artifact_id="whisper-small",
                released=date(2026, 8, 2),
            ),
            PublicModelRecord(
                id="intelliai-tts",
                capability=Capability.SPEECH_SYNTHESIS,
                service="tts-runtime",
                artifact_id="kokoro-82m",
                released=date(2026, 8, 3),
            ),
        ],
        routes=[
            ServingRoute(
                public_model_id="intelliai-tts",
                selector=RouteSelector(language="ar"),
                status=LanguageStatus.UNAVAILABLE,
            )
        ],
    )
    configure = install(
        registry, **{"stt-runtime": FakeRuntimeClient(envelope=make_stt_envelope())}
    )
    async with client_with_db(settings, db_engine, configure) as (client, factory):
        tenant = await _tenant(factory, "capability@example.com")
        response = await client.post(
            "/v1/audio/transcriptions",
            headers=_bearer(tenant.generated.secret),
            files={"file": ("clip.wav", b"fake-wav-bytes", "audio/wav")},
            data={"model": "intelliai-tts", "language": "ar"},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "capability_mismatch"


# ── Synthesis: the voice is the routing key, and the ledger fact ────────


def tts_registry(*, alto_artifact: str | None = None) -> Registry:
    voices = [
        PublicVoiceRecord(
            id="reference-alto",
            model="intelliai-tts",
            languages=("en",),
            released=date(2026, 8, 3),
            artifact_id=alto_artifact,
        ),
        PublicVoiceRecord(
            id="reference-polyglot",
            model="intelliai-tts",
            languages=("en", "hi"),
            released=date(2026, 8, 5),
        ),
    ]
    return Registry(
        artifacts=[
            _artifact("kokoro-82m", Capability.SPEECH_SYNTHESIS),
            _artifact("future-multi-v1", Capability.SPEECH_SYNTHESIS),
        ],
        models=[
            PublicModelRecord(
                id="intelliai-tts",
                capability=Capability.SPEECH_SYNTHESIS,
                service="tts-runtime",
                artifact_id="kokoro-82m",
                released=date(2026, 8, 3),
            )
        ],
        voices=voices,
        routes=[
            ServingRoute(
                public_model_id="intelliai-tts",
                selector=RouteSelector(language="en"),
                status=LanguageStatus.SUPPORTED,
                artifact_id=alto_artifact or "kokoro-82m",
                license=MIT,
                evidence=EVIDENCE,
            ),
            ServingRoute(
                public_model_id="intelliai-tts",
                selector=RouteSelector(language="hi"),
                status=LanguageStatus.AVAILABLE,
                artifact_id=alto_artifact or "kokoro-82m",
                license=MIT,
            ),
        ],
    )


def speech_body(**over: object) -> dict[str, Any]:
    return {"model": "intelliai-tts", "input": "Hello from IntelliAI.", **over}


async def test_a_bound_voice_routes_to_its_own_artifact(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeSynthesisClient(envelope=make_speech_envelope(artifact="future-multi-v1"))
    configure = install(tts_registry(alto_artifact="future-multi-v1"), **{"tts-runtime": fake})
    async with client_with_db(settings, db_engine, configure) as (client, factory):
        tenant = await _tenant(factory, "voice-bound@example.com")
        response = await client.post(
            "/v1/audio/speech",
            headers=_bearer(tenant.generated.secret),
            json=speech_body(voice="reference-alto"),
        )
        assert response.status_code == 200
        (call,) = fake.calls
        assert call.model == "future-multi-v1"  # the VOICE chose the artifact


async def test_the_ledger_records_the_language_of_the_voice_that_rendered(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # Closes M4's TTS-language gap without any public language field.
    fake = FakeSynthesisClient(envelope=make_speech_envelope(voice="reference-alto"))
    configure = install(tts_registry(), **{"tts-runtime": fake})
    async with client_with_db(settings, db_engine, configure) as (client, factory):
        tenant = await _tenant(factory, "tts-language@example.com")
        response = await client.post(
            "/v1/audio/speech",
            headers=_bearer(tenant.generated.secret),
            json=speech_body(voice="reference-alto"),
        )
        assert response.status_code == 200
        async with factory() as session:
            event = (
                await session.scalars(
                    select(UsageEvent).where(UsageEvent.organization_id == tenant.organization.id)
                )
            ).one()
            assert event.language == "en"


async def test_a_multilingual_voice_records_no_language_rather_than_guessing(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # The Ledger Fact Invariant: with two declared languages and no public
    # language input, nothing about the request says which was spoken.
    fake = FakeSynthesisClient(envelope=make_speech_envelope(voice="reference-polyglot"))
    configure = install(tts_registry(), **{"tts-runtime": fake})
    async with client_with_db(settings, db_engine, configure) as (client, factory):
        tenant = await _tenant(factory, "tts-polyglot@example.com")
        response = await client.post(
            "/v1/audio/speech",
            headers=_bearer(tenant.generated.secret),
            json=speech_body(voice="reference-polyglot"),
        )
        assert response.status_code == 200
        async with factory() as session:
            event = (
                await session.scalars(
                    select(UsageEvent).where(UsageEvent.organization_id == tenant.organization.id)
                )
            ).one()
            assert event.language is None


async def test_synthesis_has_no_public_language_field_and_none_leaks_inward(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    # F-M5-7: language is expressed through voice selection in M5. The
    # public schema is a tolerant reader by decision (SDKs send extras),
    # so a `language` key is ignored like any other unknown field — what
    # matters is that it reaches NOTHING: not the contract call, not the
    # routing decision, not the ledger. The contract's own `language`
    # field has existed since M3 and stays unpopulated: no public source
    # can fill it, and no engine reads it.
    assert "language" not in SpeechRequest.model_fields
    fake = FakeSynthesisClient(envelope=make_speech_envelope(voice="reference-alto"))
    configure = install(tts_registry(), **{"tts-runtime": fake})
    async with client_with_db(settings, db_engine, configure) as (client, factory):
        tenant = await _tenant(factory, "tts-no-language@example.com")
        response = await client.post(
            "/v1/audio/speech",
            headers=_bearer(tenant.generated.secret),
            json=speech_body(voice="reference-alto", language="hi"),
        )
        assert response.status_code == 200
        (call,) = fake.calls
        assert call.language is None
        async with factory() as session:
            event = (
                await session.scalars(
                    select(UsageEvent).where(UsageEvent.organization_id == tenant.organization.id)
                )
            ).one()
            # The voice's language, not the ignored input.
            assert event.language == "en"
