"""Error envelope tests: one shape for every failure the API can produce."""

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from intelliai_api.core.config import Settings
from intelliai_api.core.errors import RateLimitError, ResourceNotFoundError
from intelliai_api.main import create_app


def _app_with_probe_routes(settings: Settings) -> FastAPI:
    app = create_app(settings)

    @app.get("/_test/typed")
    async def typed(count: int) -> dict[str, int]:
        return {"count": count}

    @app.get("/_test/missing-voice")
    async def missing_voice() -> None:
        raise ResourceNotFoundError(
            "No voice named 'aria' exists.", code="voice_not_found", param="voice"
        )

    @app.get("/_test/limited")
    async def limited() -> None:
        raise RateLimitError("Rate limit exceeded.", code="rate_limit_exceeded", retry_after=7)

    @app.get("/_test/boom")
    async def boom() -> None:
        raise ValueError("secret internal detail")

    return app


def _error(body: dict[str, Any]) -> dict[str, Any]:
    assert set(body) == {"error"}, "envelope must have exactly one top-level key"
    err = body["error"]
    assert set(err) == {"type", "code", "message", "param", "request_id"}
    return dict(err)


def test_unknown_route_is_enveloped_404(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.get("/no/such/path")

    assert response.status_code == 404
    err = _error(response.json())
    assert err["type"] == "resource_not_found_error"
    assert err["request_id"] == response.headers["X-Request-ID"]


def test_validation_failure_is_enveloped_400_with_param(settings: Settings) -> None:
    with TestClient(_app_with_probe_routes(settings)) as client:
        response = client.get("/_test/typed", params={"count": "not-a-number"})

    assert response.status_code == 400  # never FastAPI's default 422 shape
    err = _error(response.json())
    assert err["type"] == "invalid_request_error"
    assert err["code"] == "validation_error"
    assert err["param"] == "count"


def test_platform_error_carries_code_and_param(settings: Settings) -> None:
    with TestClient(_app_with_probe_routes(settings)) as client:
        response = client.get("/_test/missing-voice")

    assert response.status_code == 404
    err = _error(response.json())
    assert err["type"] == "resource_not_found_error"
    assert err["code"] == "voice_not_found"
    assert err["param"] == "voice"


def test_rate_limit_error_sets_retry_after_header(settings: Settings) -> None:
    with TestClient(_app_with_probe_routes(settings)) as client:
        response = client.get("/_test/limited")

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "7"
    assert _error(response.json())["type"] == "rate_limit_error"


def test_unexpected_exception_never_leaks_details(settings: Settings) -> None:
    client = TestClient(_app_with_probe_routes(settings), raise_server_exceptions=False)
    with client:
        response = client.get("/_test/boom")

    assert response.status_code == 500
    err = _error(response.json())
    assert err["type"] == "internal_error"
    assert "secret internal detail" not in response.text
    assert err["request_id"] is not None


def test_health_keeps_its_own_shape(settings: Settings) -> None:
    """Deliberate contract exception: probes expect the health report shape."""
    with TestClient(create_app(settings)) as client:
        response = client.get("/health/live")

    assert "error" not in response.json()
    assert response.json()["status"] == "healthy"
