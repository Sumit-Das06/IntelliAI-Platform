"""Health endpoint tests using fake checkers — no real infrastructure needed."""

import asyncio

from fastapi.testclient import TestClient

from intelliai_api.core.config import Settings
from intelliai_api.core.health import HealthService
from intelliai_api.main import create_app


class _PassingCheck:
    def __init__(self, name: str, critical: bool) -> None:
        self.name = name
        self.critical = critical

    async def check(self) -> None:
        return None


class _FailingCheck(_PassingCheck):
    async def check(self) -> None:
        raise ConnectionError("connection refused")


class _HangingCheck(_PassingCheck):
    async def check(self) -> None:
        await asyncio.sleep(60)


def _client(settings: Settings, service: HealthService) -> TestClient:
    app = create_app(settings)
    app.state.health = service
    return TestClient(app)


def test_liveness_is_instant_and_standard_shaped(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "intelliai-api"
    assert body["version"] == "0.6.0"
    assert "timestamp" in body
    assert body["checks"] == {}


def test_all_dependencies_up_reports_healthy(settings: Settings) -> None:
    service = HealthService([_PassingCheck("database", True), _PassingCheck("redis", False)])
    with _client(settings, service) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["checks"]["database"]["status"] == "healthy"
    assert body["checks"]["database"]["latency_ms"] >= 0


def test_noncritical_failure_reports_degraded_but_serves(
    settings: Settings,
) -> None:
    service = HealthService([_PassingCheck("database", True), _FailingCheck("redis", False)])
    with _client(settings, service) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200  # still in rotation
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["redis"]["status"] == "unhealthy"
    assert "connection refused" in body["checks"]["redis"]["error"]


def test_critical_failure_reports_unhealthy_503(settings: Settings) -> None:
    service = HealthService([_FailingCheck("database", True), _PassingCheck("redis", False)])
    with _client(settings, service) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"


def test_hanging_dependency_times_out_instead_of_blocking(
    settings: Settings,
) -> None:
    service = HealthService([_HangingCheck("database", True)], timeout_s=0.05)
    with _client(settings, service) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    report = response.json()["checks"]["database"]
    assert report["status"] == "unhealthy"
    assert "timed out" in report["error"]


# ── 14B: the STT runtime joins the readiness roster ─────────────────────


def test_the_default_roster_probes_database_redis_storage_and_stt(
    settings: Settings,
) -> None:
    # The roster is the production readiness contract: database is the
    # one critical dependency; redis, storage, and the STT runtime
    # degrade the report without taking the gateway out of rotation.
    # TTS is ABSENT unless the deployment declares it (M42): a stack
    # that keeps synthesis behind its compose profile must not report a
    # permanently-degraded check that trains operators to ignore the
    # signal.
    from intelliai_api.core.health import default_checks
    from intelliai_api.db.engine import create_engine

    checks = default_checks(settings, create_engine(settings))
    roster = {check.name: check.critical for check in checks}
    assert roster == {
        "database": True,
        "redis": False,
        "storage": False,
        "stt-runtime": False,
    }


def test_a_deployment_that_serves_tts_answers_for_it_in_readiness(
    settings: Settings,
) -> None:
    # M42: the production overlay and the production-shaped local stack
    # START tts-runtime, so the gateway must probe it — green may never
    # mean "everything except the service you just promoted".
    from intelliai_api.core.health import default_checks
    from intelliai_api.db.engine import create_engine

    serving = settings.model_copy(
        update={"runtimes": settings.runtimes.model_copy(update={"tts_enabled": True})}
    )
    checks = default_checks(serving, create_engine(serving))
    roster = {check.name: check.critical for check in checks}
    assert roster == {
        "database": True,
        "redis": False,
        "storage": False,
        "stt-runtime": False,
        # Degrades the report, never takes the gateway out of rotation —
        # the same weight every runtime dependency carries.
        "tts-runtime": False,
    }


def test_the_runtime_check_reads_the_runtimes_own_readiness() -> None:
    # "ready" passes; 503 fails; and — the M31 lesson — a 200 that says
    # "degraded" ALSO fails: a multi-slot runtime with a dead specialist
    # slot must never look healthy to the gateway or the uptime monitor.
    import httpx
    import pytest as _pytest

    from intelliai_api.core.health import RuntimeHealthCheck

    def ready(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "ready", "slots": {"whisper-small": "ready"}})

    def degraded(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "degraded",
                "slots": {"whisper-small": "ready", "qwen3-asr-0.6b-hi-ft-e3": "failed"},
            },
        )

    def loading(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    check_up = RuntimeHealthCheck(
        "stt-runtime", "http://runtime/health/ready", transport=httpx.MockTransport(ready)
    )
    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(check_up.check())

    check_degraded = RuntimeHealthCheck(
        "stt-runtime", "http://runtime/health/ready", transport=httpx.MockTransport(degraded)
    )
    loop = asyncio.get_event_loop_policy().new_event_loop()
    with _pytest.raises(RuntimeError, match="degraded"):
        loop.run_until_complete(check_degraded.check())

    check_down = RuntimeHealthCheck(
        "stt-runtime", "http://runtime/health/ready", transport=httpx.MockTransport(loading)
    )
    loop = asyncio.get_event_loop_policy().new_event_loop()
    with _pytest.raises(httpx.HTTPStatusError):
        loop.run_until_complete(check_down.check())


def test_stt_runtime_down_degrades_but_gateway_still_serves(settings: Settings) -> None:
    service = HealthService(
        [
            _PassingCheck("database", True),
            _PassingCheck("redis", False),
            _PassingCheck("storage", False),
            _FailingCheck("stt-runtime", False),
        ]
    )
    with _client(settings, service) as client:
        response = client.get("/health/ready")

    # HTTP 200 — the control plane serves; the WORD says degraded, which
    # is what an uptime monitor must match on (runbook: keyword
    # "healthy", never the status code alone).
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["checks"]["stt-runtime"]["status"] == "unhealthy"
