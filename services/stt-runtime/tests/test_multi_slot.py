"""Two artifacts, one process — the M5 step 2 proof, with no model weights.

Both hosted artifacts here are the deterministic reference engine wearing
different identities. That is the point: multi-artifact hosting is proven
by the architecture, not by the models, so CI needs no weights and a
future Hindi or Arabic engine changes configuration rather than code.

The runtime still performs no routing. It selects the slot the request
pinned and refuses anything it does not host.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from helpers import wav_bytes
from intelliai_runtime_contract import RuntimeErrorType
from intelliai_stt_runtime.config import Settings
from intelliai_stt_runtime.main import create_app
from test_api import envelope_of, error_of, post_audio

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


class TestCoexistence:
    def test_both_artifacts_are_loaded_and_reported(self, client: TestClient) -> None:
        models = client.get("/info").json()["models"]
        assert [m["artifact"] for m in models] == list(HOSTED)
        assert [m["slot"] for m in models] == ["default", "future-hi-v1"]
        for model in models:
            assert model["load_ms"] >= 0
            assert model["warmup_ms"] >= 0  # every slot was warmed before traffic

    def test_readiness_covers_every_slot(self, client: TestClient) -> None:
        # `ready` is reported only after the last slot finished warming.
        assert client.get("/health/ready").json() == {"status": "ready"}
        assert len(client.get("/info").json()["models"]) == len(HOSTED)


class TestSlotSelection:
    @pytest.mark.parametrize("artifact", HOSTED)
    def test_the_pinned_artifact_selects_the_slot_that_serves_it(
        self, client: TestClient, artifact: str
    ) -> None:
        response = post_audio(client, wav_bytes(), {"model": artifact})
        assert response.status_code == 200
        assert envelope_of(response).model == artifact

    def test_an_unpinned_request_takes_the_default_slot(self, client: TestClient) -> None:
        assert envelope_of(post_audio(client, wav_bytes(), {})).model == "reference"

    def test_an_artifact_this_deployment_does_not_host_is_still_refused(
        self, client: TestClient
    ) -> None:
        # Unchanged from M3 in meaning: registry/topology drift is loud.
        response = post_audio(client, wav_bytes(), {"model": "future-ar-v1"})
        assert response.status_code == 400
        error = error_of(response)
        assert error.type is RuntimeErrorType.INVALID_INPUT
        assert error.param == "model"

    def test_selection_is_by_artifact_never_by_anything_in_the_request(
        self, client: TestClient
    ) -> None:
        # The runtime never routes: language is carried through to the
        # result, and has no influence whatsoever on which slot serves.
        for language in ("hi", "ar", "en"):
            response = post_audio(client, wav_bytes(), {"model": "reference", "language": language})
            assert envelope_of(response).model == "reference"
