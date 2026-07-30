"""Modular health checking.

Every dependency implements the ``HealthCheck`` protocol; ``HealthService``
fans the checks out concurrently, applies a per-check timeout, and aggregates
into one platform-standard report:

- ``healthy``   — every check passed.
- ``degraded``  — a non-critical dependency failed. The service keeps taking
  traffic (HTTP 200) but monitors should alarm.
- ``unhealthy`` — a critical dependency failed. The service cannot do its
  job; readiness returns HTTP 503 so routers take it out of rotation.

Adding a dependency (STT/TTS/LLM/OCR services, …) means writing one checker
class and registering it in ``default_checks`` — the service, the endpoints,
and the response format never change.
"""

import asyncio
import time
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

import httpx
import redis.asyncio as aioredis
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from intelliai_api import __version__
from intelliai_api.core.config import SERVICE_NAME, Settings
from intelliai_api.core.time import utc_now

DEFAULT_CHECK_TIMEOUT_S = 2.0
_MAX_ERROR_LENGTH = 200


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class CheckReport(BaseModel):
    status: HealthStatus
    latency_ms: float
    error: str | None = None


class HealthReport(BaseModel):
    """Platform-standard health response shape (PRD/API conventions)."""

    status: HealthStatus
    service: str = SERVICE_NAME
    version: str = __version__
    timestamp: datetime
    checks: dict[str, CheckReport]


@runtime_checkable
class HealthCheck(Protocol):
    """One dependency's health probe.

    ``critical=True`` means the platform cannot serve without it (failure →
    unhealthy); ``critical=False`` means service continues impaired
    (failure → degraded).
    """

    name: str
    critical: bool

    async def check(self) -> None:
        """Return on success; raise any exception on failure."""


class DatabaseHealthCheck:
    """Round-trip ``SELECT 1`` through the application's connection pool.

    Using the pool (not a fresh connection) makes this probe honest: it
    verifies the exact path real requests will use, and costs milliseconds
    because the connection is already open.
    """

    name = "database"
    critical = True  # system of record: nothing works without it

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def check(self) -> None:
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))


class RedisHealthCheck:
    """PING round-trip."""

    name = "redis"
    critical = False  # rate limiting/caching impaired, core API still serves

    def __init__(self, url: str) -> None:
        self._url = url

    async def check(self) -> None:
        client = aioredis.from_url(self._url)
        try:
            await client.ping()
        finally:
            await client.aclose()


class StorageHealthCheck:
    """S3-endpoint reachability.

    Vendor-neutral by design: any HTTP response (200, 403, …) proves the
    endpoint is up; only connection errors/timeouts fail the check.
    """

    name = "storage"
    critical = False  # audio persistence impaired, control plane still serves

    def __init__(self, endpoint_url: str) -> None:
        self._endpoint_url = endpoint_url

    async def check(self) -> None:
        async with httpx.AsyncClient() as client:
            await client.get(self._endpoint_url)


class HealthService:
    """Runs registered checks concurrently and aggregates a report."""

    def __init__(
        self,
        checks: list[HealthCheck],
        timeout_s: float = DEFAULT_CHECK_TIMEOUT_S,
    ) -> None:
        self._checks = checks
        self._timeout_s = timeout_s

    def liveness(self) -> HealthReport:
        """Process-is-alive: instant, no dependency I/O by design."""
        return HealthReport(
            status=HealthStatus.HEALTHY,
            timestamp=utc_now(),
            checks={},
        )

    async def readiness(self) -> HealthReport:
        reports = await asyncio.gather(*(self._run(check) for check in self._checks))
        by_name = {check.name: report for check, report in zip(self._checks, reports, strict=True)}

        status = HealthStatus.HEALTHY
        for check, report in zip(self._checks, reports, strict=True):
            if report.status is HealthStatus.HEALTHY:
                continue
            if check.critical:
                status = HealthStatus.UNHEALTHY
                break
            status = HealthStatus.DEGRADED

        return HealthReport(status=status, timestamp=utc_now(), checks=by_name)

    async def _run(self, check: HealthCheck) -> CheckReport:
        start = time.perf_counter()
        try:
            async with asyncio.timeout(self._timeout_s):
                await check.check()
        except TimeoutError:
            return CheckReport(
                status=HealthStatus.UNHEALTHY,
                latency_ms=self._latency(start),
                error=f"timed out after {self._timeout_s}s",
            )
        except Exception as exc:
            return CheckReport(
                status=HealthStatus.UNHEALTHY,
                latency_ms=self._latency(start),
                error=f"{type(exc).__name__}: {exc}"[:_MAX_ERROR_LENGTH],
            )
        return CheckReport(status=HealthStatus.HEALTHY, latency_ms=self._latency(start))

    @staticmethod
    def _latency(start: float) -> float:
        return round((time.perf_counter() - start) * 1000, 2)


def default_checks(settings: Settings, engine: AsyncEngine) -> list[HealthCheck]:
    """The gateway's dependency roster. Future inference services register here."""
    return [
        DatabaseHealthCheck(engine),
        RedisHealthCheck(settings.redis.url.get_secret_value()),
        StorageHealthCheck(settings.storage.endpoint_url),
    ]
