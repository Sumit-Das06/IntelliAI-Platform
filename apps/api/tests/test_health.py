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
    assert body["version"] == "0.1.0"
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
