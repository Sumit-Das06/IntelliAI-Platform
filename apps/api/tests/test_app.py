"""Application factory tests."""

from fastapi.testclient import TestClient

from intelliai_api import __version__
from intelliai_api.main import create_app


def test_factory_builds_independent_instances() -> None:
    first, second = create_app(), create_app()
    assert first is not second


def test_openapi_document_is_served() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    info = response.json()["info"]
    assert info["title"] == "IntelliAI Platform"
    assert info["version"] == __version__
