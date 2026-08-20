"""Two artifacts, one process — the M5 step 2 proof, with no model weights.

Both hosted artifacts here are the deterministic reference engine wearing
different identities. That is the point: multi-artifact hosting is proven
by the architecture, not by the models, so CI needs no weights and a
future Hindi or Arabic engine changes configuration rather than code.

Synthesis adds one law transcription does not have: voices are per-slot,
resolved only after the slot has been selected. The catalog is keyed by
the loaded engine, so that ordering is structural rather than
conventional — there is no global voice map left to reach for.
"""

import json
from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

from intelliai_runtime_contract import RuntimeErrorResponse, RuntimeErrorType, RuntimeResponse
from intelliai_runtime_contract import SpeechSynthesisResult as Result
from intelliai_tts_runtime.api.binding import HEADER_RUNTIME_ENVELOPE, ROUTE_SYNTHESIZE
from intelliai_tts_runtime.config import Settings
from intelliai_tts_runtime.main import create_app
from intelliai_tts_runtime.voices import REFERENCE_VOICES, VoiceCatalog

HOSTED = ("reference", "future-hi-v1")


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(
        Settings(
            console_logs=True,
            max_concurrency=2,
            max_queue=2,
            slots="reference,reference:future-hi-v1",
        )
    )
    with TestClient(app) as test_client:
        yield test_client


def envelope_of(response: httpx.Response) -> RuntimeResponse[Result]:
    envelope = json.loads(response.headers[HEADER_RUNTIME_ENVELOPE])
    return RuntimeResponse[Result].model_validate(envelope)


class TestCoexistence:
    def test_both_artifacts_are_loaded_and_reported(self, client: TestClient) -> None:
        models = client.get("/info").json()["models"]
        assert [m["artifact"] for m in models] == list(HOSTED)
        assert [m["slot"] for m in models] == ["default", "future-hi-v1"]
        for model in models:
            assert model["load_ms"] >= 0
            assert model["warmup_ms"] >= 0  # every slot was warmed before traffic

    def test_readiness_covers_every_slot(self, client: TestClient) -> None:
        assert client.get("/health/ready").json() == {"status": "ready"}
        assert len(client.get("/info").json()["models"]) == len(HOSTED)

    def test_info_reports_voices_per_artifact_and_as_a_union(self, client: TestClient) -> None:
        info = client.get("/info").json()
        for model in info["models"]:
            assert model["voices"] == [
                "english-female",
                "english-male",
                "reference-alto",
                "reference-bass",
            ]
        # The union is what this deployment can render at all — de-duplicated
        # across slots, so a shared voice is not reported twice.
        assert info["voices"] == [
            "english-female",
            "english-male",
            "reference-alto",
            "reference-bass",
        ]


class TestSlotSelection:
    @pytest.mark.parametrize("artifact", HOSTED)
    def test_the_pinned_artifact_selects_the_slot_that_serves_it(
        self, client: TestClient, artifact: str
    ) -> None:
        response = client.post(ROUTE_SYNTHESIZE, json={"text": "hello", "model": artifact})
        assert response.status_code == 200
        assert envelope_of(response).model == artifact

    def test_an_unpinned_request_takes_the_default_slot(self, client: TestClient) -> None:
        response = client.post(ROUTE_SYNTHESIZE, json={"text": "hello"})
        assert envelope_of(response).model == "reference"

    def test_an_artifact_this_deployment_does_not_host_is_still_refused(
        self, client: TestClient
    ) -> None:
        response = client.post(ROUTE_SYNTHESIZE, json={"text": "hello", "model": "future-ar-v1"})
        assert response.status_code == 400
        error = RuntimeErrorResponse.model_validate_json(response.text)
        assert error.type is RuntimeErrorType.INVALID_INPUT
        assert error.param == "model"


class TestPerSlotVoices:
    @pytest.mark.parametrize("artifact", HOSTED)
    def test_every_slot_resolves_voices_through_its_own_bindings(
        self, client: TestClient, artifact: str
    ) -> None:
        response = client.post(
            ROUTE_SYNTHESIZE, json={"text": "hello", "model": artifact, "voice": "reference-bass"}
        )
        assert response.status_code == 200
        envelope = envelope_of(response)
        assert envelope.model == artifact
        assert envelope.output.voice == "reference-bass"

    def test_each_loaded_engine_was_bound_at_load_time(self, client: TestClient) -> None:
        catalog: VoiceCatalog = client.app.state.voices  # type: ignore[attr-defined]
        manager = client.app.state.manager  # type: ignore[attr-defined]
        loaded = manager.loaded_models()
        assert len(loaded) == len(HOSTED)
        for model in loaded:
            assert catalog.voices_for(model.engine) is REFERENCE_VOICES

    def test_there_is_no_global_voice_map_left_to_reach_for(self, client: TestClient) -> None:
        # The ordering law made structural: the runtime's voice state is a
        # catalog keyed by engine, so a voice cannot be resolved before a
        # slot has been selected.
        catalog = client.app.state.voices  # type: ignore[attr-defined]
        assert isinstance(catalog, VoiceCatalog)
        assert not hasattr(catalog, "resolve")

    def test_an_unknown_voice_is_still_invalid_input(self, client: TestClient) -> None:
        response = client.post(
            ROUTE_SYNTHESIZE,
            json={"text": "hello", "model": "future-hi-v1", "voice": "af_heart"},
        )
        assert response.status_code == 400
        error = RuntimeErrorResponse.model_validate_json(response.text)
        assert error.type is RuntimeErrorType.INVALID_INPUT
        assert error.param == "voice"
