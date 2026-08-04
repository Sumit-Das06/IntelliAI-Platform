"""Deployment topology: the map the gateway keys its runtime clients by.

One capability service is a set of deployments (ADR-0026). The gateway
holds a name → URL map; the registry decides which name a route uses.
Everything here is startup-time, because a topology mistake must abort a
deploy rather than surface as a 500 on the one route that needed it.
"""

import pytest

from intelliai_api.core.config import ENGINE_VOCABULARY, RuntimeSettings, Settings
from intelliai_api.main import create_app


def runtimes(**over: object) -> RuntimeSettings:
    return RuntimeSettings.model_validate({"stt_url": "http://stt:8001", **over})


class TestDefaultTopology:
    def test_each_capability_has_a_default_deployment_named_for_its_service(self) -> None:
        # Today's topology is the degenerate case: one deployment per
        # capability, so it needs no configuration at all.
        assert runtimes().deployment_urls() == {
            "stt-runtime": "http://stt:8001",
            "tts-runtime": "http://localhost:8002",
        }

    def test_the_app_keys_its_clients_by_deployment(self, settings: Settings) -> None:
        app = create_app(settings)
        assert set(app.state.runtime_clients) == {"stt-runtime", "tts-runtime"}


class TestAdditionalDeployments:
    def test_a_second_deployment_of_one_capability_joins_the_map(self) -> None:
        urls = runtimes(deployments="stt-runtime-indic=http://stt-indic:8001").deployment_urls()
        assert urls["stt-runtime-indic"] == "http://stt-indic:8001"
        assert urls["stt-runtime"] == "http://stt:8001"  # the default is untouched

    def test_several_deployments_and_whitespace_are_tolerated(self) -> None:
        urls = runtimes(
            deployments=" stt-runtime-indic=http://a:8001 , tts-runtime-indic=http://b:8002 ,"
        ).deployment_urls()
        assert {"stt-runtime-indic", "tts-runtime-indic"} <= set(urls)

    def test_the_app_builds_a_client_per_deployment(self, settings: Settings) -> None:
        configured = settings.model_copy(
            update={
                "runtimes": runtimes(deployments="stt-runtime-indic=http://stt-indic:8001"),
            }
        )
        app = create_app(configured)
        assert "stt-runtime-indic" in app.state.runtime_clients


class TestRefusals:
    """A topology mistake aborts the deploy; it never waits for a request."""

    @pytest.mark.parametrize(
        "declaration",
        ["stt-runtime-indic", "=http://x:1", "stt-runtime-indic=", "a=b=c"],
    )
    def test_a_malformed_entry_cannot_start(self, declaration: str) -> None:
        with pytest.raises(ValueError, match=r"is not 'name=url'|not an HTTP"):
            runtimes(deployments=declaration).deployment_urls()

    def test_a_non_http_url_cannot_start(self) -> None:
        with pytest.raises(ValueError, match="not an HTTP"):
            runtimes(deployments="stt-runtime-indic=stt-indic:8001").deployment_urls()

    def test_redeclaring_the_default_deployment_cannot_start(self) -> None:
        # Two ways to set one thing is how the two drift apart.
        with pytest.raises(ValueError, match="declared twice"):
            runtimes(deployments="stt-runtime=http://other:8001").deployment_urls()

    def test_a_duplicate_deployment_cannot_start(self) -> None:
        with pytest.raises(ValueError, match="declared twice"):
            runtimes(
                deployments="stt-runtime-indic=http://a:1,stt-runtime-indic=http://b:2"
            ).deployment_urls()


class TestNamingLaw:
    """ADR-0026: deployment names use capabilities and languages, never engines.

    A language-named deployment is safe because languages are promises
    kept regardless of what serves them. An engine-named one breaks
    exactly when the engine changes — the moment nothing should have to.
    """

    @pytest.mark.parametrize(
        "name",
        ["stt-runtime-whisper", "kokoro-runtime", "tts-runtime-piper", "stt-openai"],
    )
    def test_an_engine_named_deployment_cannot_start(self, name: str) -> None:
        with pytest.raises(ValueError, match="references an engine"):
            runtimes(deployments=f"{name}=http://x:8001").deployment_urls()

    @pytest.mark.parametrize(
        "name",
        ["stt-runtime-indic", "tts-runtime-hi", "stt-runtime-ar", "stt-runtime-eu-west"],
    )
    def test_capability_and_language_names_are_lawful(self, name: str) -> None:
        assert name in runtimes(deployments=f"{name}=http://x:8001").deployment_urls()

    def test_the_denylist_covers_every_engine_the_platform_has_adopted(self) -> None:
        # It grows with each adoption, exactly like the runtimes' own
        # isolation denylist. These two are in service today.
        assert {"whisper", "kokoro"} <= set(ENGINE_VOCABULARY)
