"""The HTTP binding, end to end over a lifespan-managed app."""

import json

import httpx
from fastapi.testclient import TestClient

from helpers import wav_bytes
from intelliai_runtime_contract import (
    CONTRACT_VERSION,
    RuntimeErrorResponse,
    RuntimeErrorType,
    RuntimeResponse,
    TranscriptionResult,
    UsageUnit,
)
from intelliai_stt_runtime.api.binding import (
    HEADER_CONTRACT_VERSION,
    HEADER_REQUEST_ID,
    PART_FILE,
    PART_PARAMS,
    ROUTE_TRANSCRIBE,
)


def post_audio(
    client: TestClient,
    audio: bytes,
    params: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    files = {PART_FILE: ("clip.wav", audio, "audio/wav")}
    data = {PART_PARAMS: json.dumps(params)} if params is not None else {}
    response: httpx.Response = client.post(
        ROUTE_TRANSCRIBE, files=files, data=data, headers=headers or {}
    )
    return response


def envelope_of(response: httpx.Response) -> RuntimeResponse[TranscriptionResult]:
    return RuntimeResponse[TranscriptionResult].model_validate_json(response.text)


def error_of(response: httpx.Response) -> RuntimeErrorResponse:
    return RuntimeErrorResponse.model_validate_json(response.text)


class TestTranscribe:
    def test_returns_the_contract_envelope(self, client: TestClient) -> None:
        response = post_audio(client, wav_bytes(duration_seconds=0.5))
        assert response.status_code == 200
        assert response.headers[HEADER_CONTRACT_VERSION] == str(CONTRACT_VERSION)
        envelope = envelope_of(response)
        assert envelope.model == "reference"
        assert envelope.output.text != ""
        assert envelope.runtime.service == "stt-runtime"
        assert envelope.runtime.contract_version == CONTRACT_VERSION
        (usage,) = envelope.usage
        assert usage.unit is UsageUnit.AUDIO_SECONDS
        assert abs(usage.amount - 0.5) < 0.01
        assert set(envelope.timing.stages) == {
            "validate",
            "detect",
            "decode",
            "normalize",
            "vad",
            "inference",
        }
        assert envelope.timing.total_ms >= 0

    def test_silence_short_circuits_to_an_empty_transcript(self, client: TestClient) -> None:
        # VAD finds no speech -> no engine runs, yet usage is still billed:
        # the audio WAS processed, and silence has a correct answer.
        response = post_audio(client, wav_bytes(duration_seconds=1.0, tone_hz=None))
        envelope = envelope_of(response)
        assert envelope.output.text == ""
        assert envelope.output.language == "zxx"
        (usage,) = envelope.usage
        assert abs(usage.amount - 1.0) < 0.01

    def test_language_param_reaches_the_engine(self, client: TestClient) -> None:
        response = post_audio(client, wav_bytes(), params={"language": "hi"})
        assert envelope_of(response).output.language == "hi"

    def test_deterministic_over_the_wire(self, client: TestClient) -> None:
        # The OUTPUT is deterministic; timing legitimately varies per request.
        audio = wav_bytes(duration_seconds=0.3)
        first = envelope_of(post_audio(client, audio))
        second = envelope_of(post_audio(client, audio))
        assert first.output == second.output
        assert first.usage == second.usage
        assert first.model == second.model

    def test_request_id_round_trips(self, client: TestClient) -> None:
        response = post_audio(client, wav_bytes(), headers={HEADER_REQUEST_ID: "req_test123"})
        assert response.headers[HEADER_REQUEST_ID] == "req_test123"


class TestErrorBinding:
    def test_malformed_params_is_invalid_input(self, client: TestClient) -> None:
        files = {PART_FILE: ("clip.wav", wav_bytes(), "audio/wav")}
        response = client.post(ROUTE_TRANSCRIBE, files=files, data={PART_PARAMS: "not json"})
        assert response.status_code == 400
        error = error_of(response)
        assert error.type is RuntimeErrorType.INVALID_INPUT
        assert error.param == "params"
        assert error.runtime.service == "stt-runtime"

    def test_non_wav_audio_is_invalid_input(self, client: TestClient) -> None:
        response = post_audio(client, b"\x00\x01\x02 definitely not audio")
        assert response.status_code == 400
        assert error_of(response).param == "file"

    def test_unknown_artifact_is_invalid_input(self, client: TestClient) -> None:
        response = post_audio(client, wav_bytes(), params={"model": "whisper-small"})
        assert response.status_code == 400
        error = error_of(response)
        assert error.type is RuntimeErrorType.INVALID_INPUT
        assert error.param == "model"

    def test_missing_file_part_is_invalid_input(self, client: TestClient) -> None:
        response = client.post(ROUTE_TRANSCRIBE, data={PART_PARAMS: "{}"})
        assert response.status_code == 400
        assert error_of(response).type is RuntimeErrorType.INVALID_INPUT


class TestOperationalSurface:
    def test_liveness(self, client: TestClient) -> None:
        assert client.get("/health/live").json() == {"status": "alive"}

    def test_readiness_after_lifespan_startup(self, client: TestClient) -> None:
        assert client.get("/health/ready").json() == {"status": "ready"}

    def test_info_is_operational_identity_only(self, client: TestClient) -> None:
        info = client.get("/info").json()
        assert info["service"] == "stt-runtime"
        assert info["contract_version"] == CONTRACT_VERSION
        assert info["capability"] == "transcription"
        (model,) = info["models"]
        assert model["slot"] == "default"
        assert model["artifact"] == "reference"
        assert model["load_ms"] >= 0  # startup economics are measured facts
        assert model["warmup_ms"] >= 0
        assert info["pool"] == {"admitted": 0, "max_concurrency": 2, "max_queue": 2}
