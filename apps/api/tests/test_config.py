"""Configuration behavior tests: fail-fast, secret masking, injection."""

import pytest
from pydantic import ValidationError

from intelliai_api.core.config import DatabaseSettings, Environment, Settings
from intelliai_api.main import create_app


def test_missing_required_variable_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INTELLIAI_DATABASE_URL", raising=False)

    with pytest.raises(ValidationError) as excinfo:
        DatabaseSettings(_env_file=None)

    assert "url" in str(excinfo.value)


def test_secrets_never_appear_in_repr(settings: Settings) -> None:
    exposed = repr(settings) + str(settings)
    assert "test-password" not in exposed
    assert "test-secret" not in exposed


def test_secret_value_is_explicitly_retrievable(settings: Settings) -> None:
    url = settings.database.url.get_secret_value()
    assert url.startswith("postgresql+asyncpg://")


def test_settings_are_immutable(settings: Settings) -> None:
    with pytest.raises(ValidationError):
        settings.env = Environment.PROD


def test_factory_uses_injected_settings(settings: Settings) -> None:
    app = create_app(settings)
    assert app.state.settings is settings
    assert app.state.settings.env is Environment.TEST


def test_invalid_environment_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, env="staging")
