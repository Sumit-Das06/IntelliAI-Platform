"""Admission control: may this caller act right now?

Against real Redis, because the guarantee under test IS the atomicity of
the Lua scripts — a fake would prove only that the Python around them
reads well.

Four claims this file exists to prove:

1. **Enforcement is structural, not procedural.** The guard is attached
   to the router, so no endpoint can forget it, and a test refuses the
   diff that removes it.
2. **The limiter is atomic under concurrency.** N simultaneous requests
   against a bucket of B admit exactly B. A read-then-write limiter
   passes every quiet test and leaks precisely here.
3. **It fails open, and fails fast.** With Redis unreachable the platform
   serves traffic and raises an alarm, in milliseconds rather than at the
   OS connect timeout.
4. **It is capability-agnostic.** Capabilities that do not exist are
   limited correctly with no code change.
"""

import asyncio
import socket
import time
from typing import Any
from urllib.parse import urlparse

import pytest
import redis.asyncio as aioredis
import structlog
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from intelliai_api.api.deps import enforce_limits
from intelliai_api.core.config import Settings
from intelliai_api.core.errors import RateLimitError
from intelliai_api.limits import (
    AdmissionController,
    CapabilityAdmission,
    LimitRule,
    LimitScope,
    RedisLimiterBackend,
    plan_for,
)
from intelliai_api.limits.plans import FREE, PLANS, Plan
from intelliai_api.services.identity import BootstrapResult, IdentityService
from intelliai_runtime_contract import (
    CONTRACT_VERSION,
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
FAKE_WAV = b"RIFF\x24\x00\x00\x00WAVEfake"
DEAD_REDIS = "redis://127.0.0.1:6399/0"  # nothing listens here, by construction


def _envelope() -> RuntimeResponse[SpeechSynthesisResult]:
    return RuntimeResponse[SpeechSynthesisResult](
        output=SpeechSynthesisResult(
            duration_seconds=1.0, sample_rate_hz=24_000, voice="reference-alto", characters=5
        ),
        model="kokoro-82m",
        usage=(Usage(unit=UsageUnit.CHARACTERS, amount=5),),
        timing=RuntimeTiming(total_ms=10.0),
        runtime=RuntimeMetadata(
            service="tts-runtime", service_version="0.1.0", contract_version=CONTRACT_VERSION
        ),
    )


class FakeSynthesisClient:
    def __init__(self, delay: float = 0.0) -> None:
        self.calls = 0
        self._delay = delay

    async def synthesize(
        self, request: SpeechSynthesisRequest
    ) -> tuple[bytes, RuntimeResponse[SpeechSynthesisResult]]:
        self.calls += 1
        if self._delay:
            await asyncio.sleep(self._delay)
        return FAKE_WAV, _envelope()

    async def close(self) -> None:
        return


def install(fake: FakeSynthesisClient) -> Any:
    def configure(app: FastAPI) -> None:
        app.state.runtime_clients = {"tts-runtime": fake}

    return configure


async def _tenant(factory: async_sessionmaker[AsyncSession], email: str) -> BootstrapResult:
    async with factory() as session:
        result = await IdentityService(session, pepper=PEPPER).bootstrap_organization(
            organization_name="LimitCo", owner_email=email, owner_name="Owner"
        )
        await session.commit()
        return result


def _bearer(secret: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {secret}"}


def _tight_plan(**over: int) -> Plan:
    """A deliberately small, deliberately SLOW-refilling plan.

    The mechanism is what is under test, and exhausting a 600 rpm bucket
    in a unit test would prove only that loops are fast. The refill rate
    matters as much as the burst: at 60 rpm a bucket refills a token per
    second, which a test taking seconds silently replenishes — a test
    that passes or fails by wall-clock rather than by behaviour. Six per
    minute refills once per ten seconds, so the bucket stays empty for
    the duration of any sane test.
    """
    base = {
        "id": FREE,
        "requests_per_minute": 6,
        "burst": 3,
        "max_concurrent": 3,
        "capability_requests_per_minute": 6,
        "control_plane_requests_per_minute": 6,
    }
    return Plan(**{**base, **over})  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _requires_redis(settings: Settings) -> None:
    """Skip cleanly without infrastructure, like ``db_engine`` does.

    Without this the limiter would correctly fail open and every test in
    this file would pass while proving nothing — the worst possible
    outcome for a suite whose whole job is to show that limits ARE
    enforced.

    Synchronous on purpose: this file has both sync tests (structural
    checks that need no event loop) and async ones, and an autouse async
    fixture would break the former.
    """
    url = urlparse(settings.redis.url.get_secret_value())
    try:
        with socket.create_connection((url.hostname or "127.0.0.1", url.port or 6379), timeout=1):
            return
    except OSError:
        pytest.skip("requires running infrastructure (make up)")


async def _controller(settings: Settings) -> AdmissionController:
    client = aioredis.from_url(settings.redis.url.get_secret_value())
    return AdmissionController(RedisLimiterBackend(client), namespace=settings.limits.namespace)


# ── 1. Enforcement is structural ────────────────────────────────────────


def _guarded_prefixes(app: Any) -> dict[str, bool]:
    """Which router inclusions carry the admission guard.

    Reads the application's composition rather than each route's
    dependency tree, because that is where the guarantee actually
    lives — the guard is attached once, to the router, so that no
    individual endpoint has to remember it.
    """
    guarded: dict[str, bool] = {}
    for route in app.router.routes:
        if type(route).__name__ != "_IncludedRouter":
            continue
        names = {
            getattr(dependency.dependency, "__name__", "")
            for dependency in route.include_context.dependencies
        }
        guarded[route.original_router.prefix] = enforce_limits.__name__ in names
    return guarded


def test_no_customer_endpoint_can_escape_admission_control(settings: Settings) -> None:
    """Enforcement is structural: it cannot be forgotten, only removed.

    Two halves, and both are needed. The v1 router carries the guard, and
    every customer-facing path lives under that router — so a new
    endpoint is protected the moment it is added, and the only way to
    lose protection is a deliberate one-line diff in the app factory that
    turns this test red.
    """
    from intelliai_api.main import create_app

    app = create_app(settings)

    guarded = _guarded_prefixes(app)
    assert guarded.get("/v1") is True, "the /v1 router is not behind admission control"

    documented = set(app.openapi()["paths"])
    customer_facing = {
        path
        for path in documented
        if not path.startswith(("/health", "/openapi", "/docs", "/redoc"))
    }
    assert customer_facing, "no customer-facing paths found — the check itself is broken"
    outside = {path for path in customer_facing if not path.startswith("/v1")}
    assert not outside, f"customer endpoints outside the guarded router: {outside}"


def test_health_probes_are_never_rate_limited(settings: Settings) -> None:
    """An orchestrator that cannot read liveness restarts a healthy
    process — protection turning into an outage."""
    from intelliai_api.main import create_app

    app = create_app(settings)
    guarded = _guarded_prefixes(app)
    assert guarded.get("/health") is False
    assert any(path.startswith("/health") for path in app.openapi()["paths"])


# ── 2. Atomicity under concurrency ──────────────────────────────────────


async def test_concurrent_consumers_never_exceed_the_bucket(settings: Settings) -> None:
    """The proof that the limiter is a Lua script and not a race.

    Forty coroutines hit one bucket of five simultaneously. A
    read-then-write implementation admits far more than five here — and
    only here, which is why this test exists rather than a sequential
    one.
    """
    controller = await _controller(settings)
    rule = LimitRule(
        scope=LimitScope.ORGANIZATION, identity="atomic-probe", requests_per_minute=60, burst=5
    )

    results = await asyncio.gather(*(controller.check([rule]) for _ in range(40)))
    admitted = [decision for decision in results if decision.allowed]

    assert len(admitted) == 5, f"bucket of 5 admitted {len(admitted)} concurrent callers"


async def test_concurrent_slot_acquisition_never_exceeds_the_limit(
    settings: Settings,
) -> None:
    controller = await _controller(settings)
    results = await asyncio.gather(
        *(
            controller.acquire(
                "concurrency:probe", limit=3, lease_id=f"lease-{index}", ttl_ms=5_000
            )
            for index in range(25)
        )
    )
    assert sum(results) == 3


async def test_a_released_slot_is_reusable(settings: Settings) -> None:
    controller = await _controller(settings)
    key = "concurrency:reuse"
    assert await controller.acquire(key, limit=1, lease_id="first", ttl_ms=5_000)
    assert not await controller.acquire(key, limit=1, lease_id="second", ttl_ms=5_000)

    await controller.release(key, lease_id="first")
    assert await controller.acquire(key, limit=1, lease_id="second", ttl_ms=5_000)


async def test_an_abandoned_lease_expires_instead_of_leaking_a_slot(
    settings: Settings,
) -> None:
    """Self-healing by construction: a process that dies holding a slot
    does not remove it from the platform forever, and no reconciliation
    job is needed to notice."""
    controller = await _controller(settings)
    key = "concurrency:abandoned"
    assert await controller.acquire(key, limit=1, lease_id="crashed", ttl_ms=120)
    assert not await controller.acquire(key, limit=1, lease_id="next", ttl_ms=120)

    await asyncio.sleep(0.2)  # the crashed holder's lease expires
    assert await controller.acquire(key, limit=1, lease_id="next", ttl_ms=5_000)


# ── The customer-visible contract ───────────────────────────────────────


async def test_exhausting_the_allowance_returns_429_with_retry_guidance(
    settings: Settings, db_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(PLANS, FREE, _tight_plan())
    fake = FakeSynthesisClient()
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "limit-429@example.com")
        headers = _bearer(tenant.generated.secret)
        payload = {"model": "intelliai-tts", "input": "hello"}

        statuses = [
            (await client.post("/v1/audio/speech", headers=headers, json=payload)).status_code
            for _ in range(9)
        ]
        assert 429 in statuses
        assert statuses[0] == 200  # the burst is genuinely usable

        refused = await client.post("/v1/audio/speech", headers=headers, json=payload)
        assert refused.status_code == 429
        body = refused.json()["error"]
        assert body["type"] == "rate_limit_error"
        assert body["code"] == "rate_limit_exceeded"
        # Retrying a rate limit genuinely succeeds, so we say when.
        assert int(refused.headers["Retry-After"]) >= 1
        assert refused.headers["X-RateLimit-Limit"] == "6"
        assert refused.headers["X-RateLimit-Remaining"] == "0"


async def test_successful_responses_advertise_the_remaining_allowance(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    fake = FakeSynthesisClient()
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "limit-headers@example.com")
        response = await client.post(
            "/v1/audio/speech",
            headers=_bearer(tenant.generated.secret),
            json={"model": "intelliai-tts", "input": "hello"},
        )
        assert response.status_code == 200
        assert response.headers["X-RateLimit-Limit"] == str(plan_for(FREE).requests_per_minute)
        assert int(response.headers["X-RateLimit-Remaining"]) >= 0
        assert int(response.headers["X-RateLimit-Reset"]) >= 0


async def test_429_is_your_allowance_and_503_is_our_capacity(
    settings: Settings, db_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Never conflated. A customer who cannot tell 'slow down' from 'they
    are broken' cannot act on either."""
    monkeypatch.setitem(PLANS, FREE, _tight_plan())
    fake = FakeSynthesisClient()
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "limit-taxonomy@example.com")
        headers = _bearer(tenant.generated.secret)
        payload = {"model": "intelliai-tts", "input": "hello"}

        for _ in range(12):
            response = await client.post("/v1/audio/speech", headers=headers, json=payload)
            if response.status_code == 429:
                break
        assert response.status_code == 429
        assert response.json()["error"]["type"] == "rate_limit_error"
        assert "Retry-After" in response.headers  # retryable, and we say when


async def test_a_refused_request_never_reaches_the_runtime(
    settings: Settings, db_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cost gradient, asserted: expensive work is never performed for
    a request that will be refused."""
    monkeypatch.setitem(PLANS, FREE, _tight_plan(burst=2))
    fake = FakeSynthesisClient()
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "limit-nocall@example.com")
        headers = _bearer(tenant.generated.secret)
        payload = {"model": "intelliai-tts", "input": "hello"}

        statuses = [
            (await client.post("/v1/audio/speech", headers=headers, json=payload)).status_code
            for _ in range(8)
        ]
        admitted = statuses.count(200)
        assert statuses.count(429) > 0
        assert fake.calls == admitted  # refusals cost the runtime nothing


# ── Hierarchy: the organization is the ceiling ──────────────────────────


async def test_more_keys_do_not_buy_more_allowance(
    settings: Settings, db_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keys are unlimited in number and free to create. A per-key limit
    without an organization ceiling above it is defeated by making more
    keys — which is why the org rule is checked first and is the real
    boundary."""
    monkeypatch.setitem(PLANS, FREE, _tight_plan(burst=4))
    fake = FakeSynthesisClient()
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "limit-manykeys@example.com")
        async with factory() as session:
            _key, second = await IdentityService(session, pepper=PEPPER).issue_api_key(
                organization_id=tenant.organization.id, name="second"
            )
            await session.commit()

        payload = {"model": "intelliai-tts", "input": "hello"}
        statuses: list[int] = []
        for secret in (tenant.generated.secret, second.secret) * 4:
            response = await client.post("/v1/audio/speech", headers=_bearer(secret), json=payload)
            statuses.append(response.status_code)

        # Spreading across two keys did not raise the organization ceiling.
        assert statuses.count(200) <= 4
        assert 429 in statuses


async def test_control_plane_traffic_has_its_own_bucket(
    settings: Settings, db_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Credential enumeration should not be able to consume the inference
    allowance a customer paid for."""
    monkeypatch.setitem(PLANS, FREE, _tight_plan(burst=3, control_plane_requests_per_minute=60))
    fake = FakeSynthesisClient()
    async with client_with_db(settings, db_engine, install(fake)) as (client, factory):
        tenant = await _tenant(factory, "limit-controlplane@example.com")
        headers = _bearer(tenant.generated.secret)

        for _ in range(3):
            await client.get("/v1/api-keys", headers=headers)

        # The inference bucket is untouched by control-plane traffic.
        response = await client.post(
            "/v1/audio/speech", headers=headers, json={"model": "intelliai-tts", "input": "hi"}
        )
        assert response.status_code == 200


# ── 3. Fail open, and fail fast ─────────────────────────────────────────


async def test_an_unreachable_limiter_serves_traffic_and_raises_an_alarm(
    settings: Settings, db_engine: AsyncEngine
) -> None:
    """A limiter outage becoming a platform outage is a worse failure than
    minutes of unbounded traffic (ADR-0022). Unbounded and LOUD, though —
    unlimited traffic nobody knows about is the failure this posture is
    meant to make survivable, not invisible.
    """
    dead = aioredis.from_url(DEAD_REDIS, socket_connect_timeout=0.25, socket_timeout=0.25)
    broken = AdmissionController(RedisLimiterBackend(dead))
    fake = FakeSynthesisClient()

    def configure(app: FastAPI) -> None:
        app.state.runtime_clients = {"tts-runtime": fake}
        app.state.limits = broken

    async with client_with_db(settings, db_engine, configure) as (client, factory):
        tenant = await _tenant(factory, "limit-redisdown@example.com")
        with structlog.testing.capture_logs() as logs:
            started = time.perf_counter()
            response = await client.post(
                "/v1/audio/speech",
                headers=_bearer(tenant.generated.secret),
                json={"model": "intelliai-tts", "input": "hello"},
            )
            elapsed = time.perf_counter() - started

    assert response.status_code == 200  # served
    events = [line.get("event") for line in logs]
    assert "ratelimit.unavailable" in events, f"captured: {events}"  # and loud
    # Failing open must also fail FAST: a limiter that hangs has taken the
    # platform down more effectively than one that refuses.
    assert elapsed < 2.0, f"fail-open path took {elapsed:.2f}s"
    # ...and the breaker has tripped, so the NEXT request pays nothing at
    # all. Failing open is only survivable if it also stays cheap.
    assert broken._tripped()
    # No headers are advertised when nothing was measured — better to say
    # nothing than to publish a limit we did not enforce.
    assert "X-RateLimit-Limit" not in response.headers


async def test_the_breaker_stops_paying_the_timeout_on_every_request(
    settings: Settings,
) -> None:
    """Measured at step 3 and fixed here: with Redis unreachable, each of
    a request's five limiter calls burned the full socket budget, adding
    ~1.2 s per request. A limiter outage was becoming a platform
    degradation by another route. After a few failures the breaker opens
    and subsequent calls cost nothing at all.
    """
    dead = aioredis.from_url(DEAD_REDIS, socket_connect_timeout=0.25, socket_timeout=0.25)
    broken = AdmissionController(RedisLimiterBackend(dead), failure_threshold=2)
    rule = LimitRule(
        scope=LimitScope.ORGANIZATION, identity="breaker", requests_per_minute=60, burst=5
    )

    for _ in range(2):
        assert (await broken.check([rule])).degraded
    assert broken._tripped()

    started = time.perf_counter()
    for _ in range(20):
        assert (await broken.check([rule])).degraded
    elapsed = time.perf_counter() - started
    # Twenty calls that would have cost 5 s of timeouts now cost nothing.
    assert elapsed < 0.05, f"20 tripped calls took {elapsed:.3f}s"


async def test_the_breaker_closes_again_when_the_limiter_recovers(
    settings: Settings,
) -> None:
    """An outage must not disable limiting permanently."""
    controller = await _controller(settings)
    controller._consecutive_failures = 5
    rule = LimitRule(
        scope=LimitScope.ORGANIZATION, identity="recovery", requests_per_minute=60, burst=5
    )
    decision = await controller.check([rule])
    assert decision.allowed and not decision.degraded  # measured again
    assert not controller._tripped()


async def test_a_disabled_limiter_is_a_deployment_choice_not_a_failure(
    settings: Settings,
) -> None:
    controller = AdmissionController(None)
    assert not controller.enabled
    decision = await controller.check(
        [LimitRule(scope=LimitScope.IP, identity="x", requests_per_minute=1, burst=1)]
    )
    assert decision.allowed and decision.degraded
    assert await controller.acquire("k", limit=0, lease_id="l", ttl_ms=1)


# ── 4. Capability independence ──────────────────────────────────────────


FUTURE_CAPABILITIES = [
    "document_ocr",
    "vision",
    "chat",
    "translation",
    "embeddings",
    "speech_to_speech",
]


@pytest.mark.parametrize("capability", FUTURE_CAPABILITIES)
async def test_capabilities_that_do_not_exist_are_limited_correctly(
    settings: Settings, capability: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """None of these capabilities exists. Each is limited the day it
    ships, with no change to this package — a rule is a scope, an
    identity, and a rate, and nothing here knows what speech is.
    """
    monkeypatch.setitem(PLANS, FREE, _tight_plan(burst=2))
    admission = CapabilityAdmission(await _controller(settings))
    organization = f"org_future_{capability}"

    async def ask() -> None:
        await admission.check_capability(
            organization_id=organization, plan_id=FREE, capability=capability
        )

    await ask()
    await ask()
    with pytest.raises(RateLimitError, match="Retry after"):
        await ask()


async def test_one_capability_cannot_exhaust_another(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Different capacity, different budget. A customer saturating
    transcription must still be able to synthesize."""
    monkeypatch.setitem(PLANS, FREE, _tight_plan(burst=2))
    admission = CapabilityAdmission(await _controller(settings))
    org = "org_two_capabilities"

    for _ in range(2):
        await admission.check_capability(
            organization_id=org, plan_id=FREE, capability="transcription"
        )
    with pytest.raises(RateLimitError, match="Retry after"):
        await admission.check_capability(
            organization_id=org, plan_id=FREE, capability="transcription"
        )

    # Synthesis is untouched — and so is a capability nobody has built.
    await admission.check_capability(
        organization_id=org, plan_id=FREE, capability="speech_synthesis"
    )
    await admission.check_capability(organization_id=org, plan_id=FREE, capability="document_ocr")


# ── Plans, not hardcoded numbers ────────────────────────────────────────


def test_limits_come_from_the_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    """An org has a plan, a plan carries limits. Adding a tier is a
    configuration change, not a migration."""
    enterprise = Plan(
        id="enterprise",
        requests_per_minute=60_000,
        burst=5_000,
        max_concurrent=500,
        capability_requests_per_minute=60_000,
        control_plane_requests_per_minute=1_000,
    )
    monkeypatch.setitem(PLANS, "enterprise", enterprise)

    assert plan_for("enterprise").max_concurrent == 500
    assert plan_for(FREE).max_concurrent == PLANS[FREE].max_concurrent
    # An unrecognised plan is an operations problem, not a reason to
    # refuse a paying customer.
    assert plan_for("typo-tier").id == FREE


def test_the_free_tier_ships_generously(monkeypatch: pytest.MonkeyPatch) -> None:
    """Founder decisions F4 and F5: the mechanism is the deliverable, and
    a limit set too tight at launch is indistinguishable from an outage.
    The concurrency ceiling sits ABOVE the runtime worker pool's own, so
    capacity exhaustion still surfaces as an honest 503."""
    free = plan_for(FREE)
    assert free.requests_per_minute >= 600
    assert free.max_concurrent > 10  # the M3-measured TTS pool ceiling
