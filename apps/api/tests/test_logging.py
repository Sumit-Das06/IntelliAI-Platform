"""Logging behavior tests: correlation IDs, standard fields, redaction."""

import json

import pytest
import structlog
from fastapi.testclient import TestClient

from intelliai_api.core.config import Settings
from intelliai_api.core.logging import configure_logging
from intelliai_api.main import create_app


def _json_lines(raw: str) -> list[dict]:
    return [
        json.loads(line)
        for line in raw.strip().splitlines()
        if line.startswith("{")
    ]


def test_response_carries_generated_request_id(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.get("/openapi.json")

    assert response.headers["X-Request-ID"].startswith("req_")


def test_client_supplied_request_id_is_echoed(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.get(
            "/openapi.json", headers={"X-Request-ID": "req_client_supplied"}
        )

    assert response.headers["X-Request-ID"] == "req_client_supplied"


def test_access_log_is_json_with_standard_fields(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    with TestClient(create_app(settings)) as client:
        client.get("/openapi.json", headers={"X-Request-ID": "req_correlation"})

    events = _json_lines(capsys.readouterr().out)
    completed = [e for e in events if e.get("event") == "request_completed"][-1]

    assert completed["request_id"] == "req_correlation"
    assert completed["status_code"] == 200
    assert completed["method"] == "GET"
    assert completed["path"] == "/openapi.json"
    assert completed["service"] == "intelliai-api"
    assert completed["environment"] == "test"
    assert completed["level"] == "info"
    assert "timestamp" in completed
    assert isinstance(completed["latency_ms"], float)


def test_sensitive_keys_are_redacted(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging(settings)

    structlog.get_logger().info(
        "config_loaded",
        password="hunter2",
        api_key="ik_live_abc123",
        authorization="Bearer xyz",
        database_url="postgresql://u:p@h/db",  # not a marked key: stays
        detail="plain-value",
    )

    out = capsys.readouterr().out
    assert "hunter2" not in out
    assert "ik_live_abc123" not in out
    assert "Bearer xyz" not in out
    assert "[REDACTED]" in out
    assert "plain-value" in out
