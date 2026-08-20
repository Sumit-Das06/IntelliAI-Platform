"""The Commercial Identity Continuity Proof.

Everything the platform can change about *how* a request is served,
proven not to change *anything commercial* about it — end to end, through
the real gateway, the real ledger, the real entitlement check, and the
real rating function.

Seven internal realities are exercised against one identical customer
request:

| Reality | What changes internally |
|---|---|
| engine replacement | a different engine serves the capability |
| artifact swap | a different weights file |
| fine-tune | a model trained further on our data |
| quantization | int8 instead of float |
| LoRA adapter | an adapter stacked on a base |
| multilingual routing | a different engine per language |
| registry promotion | the catalog re-points the public model |

Nothing about any of them may reach: the ledger entry, quota
consumption, pricing, the rated amount, the invoice projection, the
accounting event, or the customer API.

**The negative control is the most important test in this file.** A
proof that "nothing ever changes" is worthless unless the same machinery
can detect a change that SHOULD happen — so the last section changes the
public pricing policy and asserts the money moves, and only the money.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from intelliai_api.core.config import Settings
from intelliai_api.db.models import UsageEvent, UsageOrigin
from intelliai_api.db.repositories import UsageEventRepository, UsageRollupRepository
from intelliai_api.entitlements import period_for
from intelliai_api.pricing import (
    INTERNAL_V1,
    RATING_ALGORITHM_VERSION,
    PriceBook,
    PriceBookCatalog,
    RatedPeriod,
    rate_events,
)
from intelliai_api.registry import Registry
from intelliai_api.registry.records import ArtifactRecord, LicenseVerdict, PublicModelRecord
from intelliai_api.services.identity import BootstrapResult, IdentityService
from intelliai_runtime_contract import (
    CONTRACT_VERSION,
    Capability,
    RuntimeMetadata,
    RuntimeResponse,
    RuntimeTiming,
    SpeechSynthesisRequest,
    SpeechSynthesisResult,
    Usage,
    UsageUnit,
)
from tests.helpers import client_with_db

pytestmark = pytest.mark.anyio

PEPPER = "test-pepper"
FAKE_WAV = b"RIFF\x24\x00\x00\x00WAVEfake-audio"
TEXT = "Hello from IntelliAI."
CHARACTERS = 21
CATALOG = PriceBookCatalog(books=(INTERNAL_V1,))


class Reality:
    """One internal way of serving the same public capability."""

    def __init__(
        self,
        name: str,
        *,
        artifact: str,
        artifact_version: int = 1,
        service_version: str = "0.1.0",
        language: str = "en",
    ) -> None:
        self.name = name
        self.artifact = artifact
        self.artifact_version = artifact_version
        self.service_version = service_version
        self.language = language


REALITIES = [
    Reality("launch engine", artifact="kokoro-82m"),
    Reality("engine replacement", artifact="piper-en-v1", service_version="2.0.0"),
    Reality("artifact swap", artifact="kokoro-82m", artifact_version=7),
    Reality("fine-tune", artifact="intelliai-tts-ft-v2"),
    Reality("quantization", artifact="kokoro-82m-int8"),
    Reality("LoRA adapter", artifact="kokoro-82m+lora-hi", language="hi"),
    Reality("multilingual routing", artifact="future-arabic-v1", language="ar"),
    Reality("registry promotion", artifact="kokoro-82m-v9", artifact_version=9),
]


def registry_promoted_to(reality: Reality) -> Registry:
    """A registry whose public model has been promoted to this artifact.

    This is what a Registry V2 promotion *is*: the same public model id,
    re-pointed. The customer's request does not change; the catalog's
    answer to it does.
    """
    return Registry(
        artifacts=[
            ArtifactRecord(
                id=reality.artifact,
                version=reality.artifact_version,
                capability=Capability.SPEECH_SYNTHESIS,
                provenance=f"continuity proof: {reality.name}",
                license=LicenseVerdict(
                    license="Apache-2.0",
                    commercial_use=True,
                    verified_on=date(2026, 8, 3),
                    source="https://example.invalid/continuity-proof",
                ),
            )
        ],
        models=[
            PublicModelRecord(
                id="intelliai-tts",
                capability=Capability.SPEECH_SYNTHESIS,
                service="tts-runtime",
                artifact_id=reality.artifact,
                description="IntelliAI text to speech",
                released=date(2026, 8, 3),
            )
        ],
    )


class FakeSynthesisClient:
    def __init__(self, reality: Reality) -> None:
        self._reality = reality
        self.requests: list[SpeechSynthesisRequest] = []

    async def synthesize(
        self, request: SpeechSynthesisRequest
    ) -> tuple[bytes, RuntimeResponse[SpeechSynthesisResult]]:
        self.requests.append(request)
        return FAKE_WAV, RuntimeResponse[SpeechSynthesisResult](
            output=SpeechSynthesisResult(
                duration_seconds=3.2,
                sample_rate_hz=24_000,
                voice="reference-alto",
                characters=CHARACTERS,
            ),
            model=self._reality.artifact,
            usage=(Usage(unit=UsageUnit.CHARACTERS, amount=CHARACTERS),),
            timing=RuntimeTiming(total_ms=300.0),
            runtime=RuntimeMetadata(
                service="tts-runtime",
                service_version=self._reality.service_version,
                contract_version=CONTRACT_VERSION,
            ),
        )

    async def close(self) -> None:
        return


async def _tenant(factory: async_sessionmaker[AsyncSession], email: str) -> BootstrapResult:
    async with factory() as session:
        result = await IdentityService(session, pepper=PEPPER).bootstrap_organization(
            organization_name="ContinuityCo", owner_email=email, owner_name="Owner"
        )
        await session.commit()
        return result


class Observation:
    """Everything commercially visible about one served request."""

    def __init__(
        self,
        *,
        reality: Reality,
        status: int,
        body: bytes,
        content_type: str,
        headers: frozenset[str],
        event: UsageEvent,
        quota: dict[str, Decimal],
        rated: RatedPeriod,
        rollup: dict[str, Decimal],
    ) -> None:
        self.reality = reality
        self.status = status
        self.body = body
        self.content_type = content_type
        self.headers = headers
        self.event = event
        self.quota = quota
        self.rated = rated
        self.rollup = rollup

    @property
    def commercial_fingerprint(self) -> tuple[Any, ...]:
        """The complete commercial identity of a request.

        If any internal replacement is ever able to move ANY of these,
        the Commercial Identity Invariant has been broken — and this
        tuple is what makes that a test failure rather than a discovery
        on an invoice.
        """
        return (
            # ── the customer API ──
            self.status,
            self.body,
            self.content_type,
            self.headers,
            # ── the ledger entry ──
            self.event.capability,
            self.event.public_model_id,
            self.event.origin,
            self.event.outcome,
            self.event.billable,
            tuple(sorted((q.unit, q.amount) for q in self.event.quantities)),
            # ── quota, pricing, rated amount, invoice ──
            tuple(sorted(self.quota.items())),
            tuple(sorted(self.rollup.items())),
            self.rated.subtotal,
            self.rated.discount_amount,
            self.rated.total,
            self.rated.currency,
            self.rated.price_book_versions,
            self.rated.rating_algorithm_version,
            tuple(
                (line.unit, line.quantity, line.unit_price, line.amount)
                for line in self.rated.lines
            ),
        )


async def observe(
    settings: Settings,
    db_engine: AsyncEngine,
    reality: Reality,
    *,
    email: str,
    catalog: PriceBookCatalog = CATALOG,
) -> Observation:
    """Serve one identical customer request under one internal reality."""
    fake = FakeSynthesisClient(reality)

    def configure(app: FastAPI) -> None:
        app.state.registry = registry_promoted_to(reality)
        app.state.runtime_clients = {"tts-runtime": fake}

    async with client_with_db(settings, db_engine, configure) as (client, factory):
        tenant = await _tenant(factory, email)
        response = await client.post(
            "/v1/audio/speech",
            headers={"Authorization": f"Bearer {tenant.generated.secret}"},
            json={"model": "intelliai-tts", "input": TEXT},
        )

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
            rollup = await UsageRollupRepository(session).rebuild(
                tenant.organization.id, since=period.start, until=period.end
            )
            await session.commit()

        rated = rate_events(
            events,
            organization_public_id="org_fixed",  # identity is not under test here
            period_label=period.label,
            catalog=catalog,
        )

        # Headers that are request-specific (ids, timing) are not part of
        # commercial identity; their PRESENCE is.
        headers = frozenset(key.lower() for key in response.headers)

        return Observation(
            reality=reality,
            status=response.status_code,
            body=response.content,
            content_type=response.headers["content-type"],
            headers=headers,
            event=event,
            quota=quota,
            rated=rated,
            rollup=rollup,
        )


# ── The proof ───────────────────────────────────────────────────────────


async def test_every_internal_replacement_is_commercially_invisible(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """The whole milestone, in one assertion.

    Eight ways of serving the same request — engine replacement, artifact
    swap, fine-tune, quantization, LoRA, multilingual routing, and a
    registry promotion — produce ONE commercial fingerprint.
    """
    observations = [
        await observe(settings, db_engine, reality, email=f"continuity-{index}@example.com")
        for index, reality in enumerate(REALITIES)
    ]

    fingerprints = {observation.commercial_fingerprint for observation in observations}
    assert len(fingerprints) == 1, "an internal replacement changed the commercial record: " + repr(
        {
            observation.reality.name: observation.commercial_fingerprint
            for observation in observations
        }
    )

    # And the realities really were different — otherwise this proves nothing.
    assert {observation.event.lineage["artifact"] for observation in observations} == {
        reality.artifact for reality in REALITIES
    }
    assert len({observation.event.lineage["service_version"] for observation in observations}) > 1
    assert len({observation.event.lineage["artifact_version"] for observation in observations}) > 1


async def test_the_difference_lives_only_in_internal_lineage(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """What DID change, and where it is allowed to live.

    Lineage is the one place an internal replacement leaves a trace. It
    is stored for cost-to-serve analysis and for joining the usage ledger
    to the evaluation evidence ledger — and it is never projected, never
    priced, and never an admission input.
    """
    observations = [
        await observe(settings, db_engine, reality, email=f"lineage-{index}@example.com")
        for index, reality in enumerate(REALITIES)
    ]

    lineages = [observation.event.lineage for observation in observations]
    assert len({tuple(sorted(lineage.items())) for lineage in lineages}) == len(REALITIES)

    # Nothing from lineage reached the customer.
    for observation in observations:
        rendered = observation.body.decode("latin-1") + repr(sorted(observation.headers))
        assert observation.reality.artifact not in rendered
        assert "lineage" not in rendered.lower()


async def test_a_registry_promotion_changes_only_what_the_runtime_is_asked_for(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """A promotion re-points the catalog; the customer's request is
    untouched and the commercial record is untouched.

    The one thing that legitimately changes is the ARTIFACT ID the
    gateway asks the runtime to load — internal vocabulary, on an
    internal call.
    """
    before = Reality("before promotion", artifact="kokoro-82m")
    after = Reality("after promotion", artifact="kokoro-82m-v9", artifact_version=9)

    asked: list[str] = []
    for index, reality in enumerate((before, after)):
        fake = FakeSynthesisClient(reality)

        def configure(app: FastAPI, reality: Reality = reality, fake: Any = fake) -> None:
            app.state.registry = registry_promoted_to(reality)
            app.state.runtime_clients = {"tts-runtime": fake}

        async with client_with_db(settings, db_engine, configure) as (client, factory):
            tenant = await _tenant(factory, f"promotion-{index}@example.com")
            response = await client.post(
                "/v1/audio/speech",
                headers={"Authorization": f"Bearer {tenant.generated.secret}"},
                json={"model": "intelliai-tts", "input": TEXT},
            )
            assert response.status_code == 200
            # The customer asked for the public model, both times.
            assert response.request.read().decode().count("intelliai-tts") == 1
        requested_artifact = fake.requests[0].model
        assert requested_artifact is not None  # the gateway always pins one
        asked.append(requested_artifact)

    assert asked == ["kokoro-82m", "kokoro-82m-v9"]  # internal, and it moved


async def test_the_public_catalog_is_unchanged_by_promotion(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """`/v1/models` describes products, not the things serving them."""
    payloads = []
    for index, reality in enumerate((REALITIES[0], REALITIES[-1])):
        fake = FakeSynthesisClient(reality)

        def configure(app: FastAPI, reality: Reality = reality, fake: Any = fake) -> None:
            app.state.registry = registry_promoted_to(reality)
            app.state.runtime_clients = {"tts-runtime": fake}

        async with client_with_db(settings, db_engine, configure) as (client, factory):
            tenant = await _tenant(factory, f"catalog-{index}@example.com")
            response = await client.get(
                "/v1/models", headers={"Authorization": f"Bearer {tenant.generated.secret}"}
            )
            assert response.status_code == 200
            payloads.append(response.json())

    assert payloads[0] == payloads[1]
    assert "kokoro" not in repr(payloads[0])


# ── Reproducibility: the third leg of the triple ────────────────────────


async def test_rating_is_reproducible_across_realities_and_repetitions(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """The Rating Reproducibility Invariant (§8.6).

    Same ledger, same price book version, same algorithm version — same
    money, whatever served it and however many times it is asked.
    """
    observation = await observe(settings, db_engine, REALITIES[0], email="reproduce@example.com")
    assert observation.rated.rating_algorithm_version == RATING_ALGORITHM_VERSION

    events = [observation.event]
    results = {
        rate_events(
            events,
            organization_public_id="org_fixed",
            period_label="2026-08",
            catalog=CATALOG,
        )
        for _ in range(100)
    }
    assert len(results) == 1


def test_an_unknown_rating_algorithm_is_refused_not_substituted() -> None:
    """The failure this prevents is the quiet one: asking for version 1
    in 2029, silently receiving version 3, and reporting a number the
    customer never paid."""
    with pytest.raises(ValueError, match="rating algorithm version 2 is not implemented"):
        rate_events(
            [],
            organization_public_id="org_x",
            period_label="2026-08",
            catalog=CATALOG,
            algorithm_version=2,
        )


def test_the_reproducible_triple_is_recorded_on_every_result() -> None:
    """An invoice that records events and prices but not the arithmetic
    can be re-derived to a different number by a future release."""
    rated = rate_events([], organization_public_id="org_x", period_label="2026-08", catalog=CATALOG)
    assert rated.rating_algorithm_version == 1
    assert hasattr(rated, "price_book_versions")
    assert hasattr(rated, "agreement_id")


# ── The negative control ────────────────────────────────────────────────


async def test_a_deliberate_pricing_policy_change_does_move_the_money(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """The most important test in this file.

    A proof that "nothing ever changes" is worthless unless the same
    machinery can detect a change that SHOULD happen. Here the public
    pricing policy changes — the one legitimate reason the number moves —
    and the fingerprint is expected to differ.

    Everything that is not money stays identical, so the change is
    attributable rather than mysterious.
    """
    doubled = PriceBookCatalog(
        books=(
            PriceBook(
                version="continuity-doubled",
                effective_from=INTERNAL_V1.effective_from,
                currency=INTERNAL_V1.currency,
                unit_prices={unit: price * 2 for unit, price in INTERNAL_V1.unit_prices.items()},
            ),
        )
    )

    standard = await observe(settings, db_engine, REALITIES[0], email="policy-standard@example.com")
    repriced = await observe(
        settings,
        db_engine,
        REALITIES[0],
        email="policy-repriced@example.com",
        catalog=doubled,
    )

    # The machinery CAN see a difference — so its silence elsewhere means
    # something.
    assert standard.commercial_fingerprint != repriced.commercial_fingerprint
    assert repriced.rated.subtotal == standard.rated.subtotal * 2
    assert repriced.rated.price_book_versions == ("continuity-doubled",)

    # ...and only the money moved. The facts are identical.
    assert standard.status == repriced.status
    assert standard.body == repriced.body
    assert standard.quota == repriced.quota
    assert standard.rollup == repriced.rollup
    assert [(q.unit, q.amount) for q in standard.event.quantities] == [
        (q.unit, q.amount) for q in repriced.event.quantities
    ]
    assert standard.event.public_model_id == repriced.event.public_model_id


async def test_quota_is_unmoved_by_a_pricing_change(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """Quota is measured in USAGE and pricing is measured in MONEY; a
    price change must not consume a customer's allowance."""
    standard = await observe(settings, db_engine, REALITIES[0], email="q-standard@example.com")
    doubled = PriceBookCatalog(
        books=(
            PriceBook(
                version="q-doubled",
                effective_from=INTERNAL_V1.effective_from,
                currency=INTERNAL_V1.currency,
                unit_prices={u: p * 2 for u, p in INTERNAL_V1.unit_prices.items()},
            ),
        )
    )
    repriced = await observe(
        settings, db_engine, REALITIES[0], email="q-doubled@example.com", catalog=doubled
    )

    assert standard.quota == repriced.quota
    # M35 billing law: synthesis quantities carry CHARACTERS and nothing
    # else — the measured duration is telemetry beside the lineage, never
    # a rated/quota quantity (audio_seconds has a book price for STT, so
    # its presence here would double-charge synthesis).
    assert standard.quota["characters"] == Decimal(CHARACTERS)
    assert "audio_seconds" not in standard.quota
    assert standard.event.lineage is not None
    assert standard.event.lineage["measured_audio_seconds"] == 3.2
