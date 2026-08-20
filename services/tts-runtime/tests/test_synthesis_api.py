"""The binary binding, end to end: ADR-0020 proven with no model.

Success responses are raw WAV bytes (parsed here with the stdlib reader —
if `wave` can read it, any client can) with the envelope riding
``X-Runtime-Envelope``. Errors are ALWAYS JSON. The full lifespan runs in
every test: engines load before the first request, unload after the last.
"""

import io
import json
import wave
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from intelliai_runtime_contract import (
    RuntimeErrorResponse,
    RuntimeErrorType,
    RuntimeResponse,
    SpeechSynthesisResult,
    UsageUnit,
)
from intelliai_tts_runtime.api.binding import (
    HEADER_CONTRACT_VERSION,
    HEADER_REQUEST_ID,
    HEADER_RUNTIME_ENVELOPE,
    MAX_ENVELOPE_HEADER_BYTES,
    ROUTE_SYNTHESIZE,
)
from intelliai_tts_runtime.config import Settings
from intelliai_tts_runtime.engines.reference import SAMPLE_RATE_HZ
from intelliai_tts_runtime.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(
        Settings(console_logs=True, max_concurrency=2, max_queue=2, max_text_chars=200)
    )
    # The context manager runs the lifespan: engines load before the first
    # request and unload after the last — exactly like production.
    with TestClient(app) as test_client:
        yield test_client


def parse_envelope(header_value: str) -> RuntimeResponse[SpeechSynthesisResult]:
    return RuntimeResponse[SpeechSynthesisResult].model_validate_json(header_value)


class TestBinaryResponse:
    def test_body_is_playable_wav_and_envelope_rides_the_header(self, client: TestClient) -> None:
        response = client.post(ROUTE_SYNTHESIZE, json={"text": "hello world"})
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"

        # The body is directly playable bytes — no JSON wrapper, no base64.
        with wave.open(io.BytesIO(response.content), "rb") as reader:
            assert reader.getnchannels() == 1
            assert reader.getsampwidth() == 2
            assert reader.getframerate() == SAMPLE_RATE_HZ
            frames = reader.getnframes()
            assert frames > 0

        envelope = parse_envelope(response.headers[HEADER_RUNTIME_ENVELOPE])
        assert envelope.model == "reference"
        assert envelope.output.characters == len("hello world")
        assert envelope.output.sample_rate_hz == SAMPLE_RATE_HZ
        assert envelope.output.duration_seconds == pytest.approx(frames / SAMPLE_RATE_HZ)
        assert response.headers[HEADER_CONTRACT_VERSION] == "1"

    def test_deterministic_end_to_end(self, client: TestClient) -> None:
        first = client.post(ROUTE_SYNTHESIZE, json={"text": "determinism", "speed": 1.5})
        second = client.post(ROUTE_SYNTHESIZE, json={"text": "determinism", "speed": 1.5})
        assert first.content == second.content  # byte-identical audio

    def test_usage_bills_characters(self, client: TestClient) -> None:
        text = "count these characters"
        response = client.post(ROUTE_SYNTHESIZE, json={"text": text})
        envelope = parse_envelope(response.headers[HEADER_RUNTIME_ENVELOPE])
        assert len(envelope.usage) == 1
        assert envelope.usage[0].unit is UsageUnit.CHARACTERS
        assert envelope.usage[0].amount == len(text)

    def test_envelope_is_operational_metadata_only_and_bounded(self, client: TestClient) -> None:
        response = client.post(ROUTE_SYNTHESIZE, json={"text": "bounded"})
        header = response.headers[HEADER_RUNTIME_ENVELOPE]
        assert len(header.encode("ascii")) <= MAX_ENVELOPE_HEADER_BYTES  # ascii-safe AND bounded
        # Nothing generated may ride the header: no audio, no text echo.
        payload = json.loads(header)
        assert "bounded" not in header
        assert set(payload) == {"output", "model", "usage", "timing", "runtime"}

    def test_timing_covers_every_pipeline_stage(self, client: TestClient) -> None:
        response = client.post(ROUTE_SYNTHESIZE, json={"text": "stages"})
        envelope = parse_envelope(response.headers[HEADER_RUNTIME_ENVELOPE])
        assert set(envelope.timing.stages) == {
            "voice_resolution",
            "validate",
            "normalize",
            "synthesis",
            "encode",
        }
        assert envelope.timing.total_ms > 0


class TestVoicePlumbing:
    def test_default_voice_resolution_is_visible_in_the_envelope(self, client: TestClient) -> None:
        response = client.post(ROUTE_SYNTHESIZE, json={"text": "hi"})
        envelope = parse_envelope(response.headers[HEADER_RUNTIME_ENVELOPE])
        assert envelope.output.voice == "english-female"  # served voice, always named

    def test_selected_voice_changes_audio_and_is_reported(self, client: TestClient) -> None:
        alto = client.post(ROUTE_SYNTHESIZE, json={"text": "hi"})
        bass = client.post(ROUTE_SYNTHESIZE, json={"text": "hi", "voice": "reference-bass"})
        assert alto.content != bass.content
        envelope = parse_envelope(bass.headers[HEADER_RUNTIME_ENVELOPE])
        assert envelope.output.voice == "reference-bass"


class TestErrorsAreAlwaysJson:
    def assert_json_error(
        self, response: object, status: int, error_type: RuntimeErrorType, param: str | None
    ) -> None:
        from httpx import Response as HttpxResponse

        assert isinstance(response, HttpxResponse)
        assert response.status_code == status
        assert response.headers["content-type"].startswith("application/json")
        body = RuntimeErrorResponse.model_validate(response.json())
        assert body.type is error_type
        assert body.param == param
        assert HEADER_RUNTIME_ENVELOPE not in response.headers  # errors never carry envelopes

    def test_unknown_voice(self, client: TestClient) -> None:
        response = client.post(ROUTE_SYNTHESIZE, json={"text": "hi", "voice": "nope"})
        self.assert_json_error(response, 400, RuntimeErrorType.INVALID_INPUT, "voice")

    def test_unknown_artifact(self, client: TestClient) -> None:
        response = client.post(ROUTE_SYNTHESIZE, json={"text": "hi", "model": "kokoro-82m"})
        self.assert_json_error(response, 400, RuntimeErrorType.INVALID_INPUT, "model")

    def test_empty_text_rejected_by_the_contract_schema(self, client: TestClient) -> None:
        response = client.post(ROUTE_SYNTHESIZE, json={"text": ""})
        self.assert_json_error(response, 400, RuntimeErrorType.INVALID_INPUT, None)

    def test_over_limit_text(self, client: TestClient) -> None:
        response = client.post(ROUTE_SYNTHESIZE, json={"text": "x" * 201})
        self.assert_json_error(response, 400, RuntimeErrorType.INVALID_INPUT, "text")

    def test_non_json_body(self, client: TestClient) -> None:
        response = client.post(ROUTE_SYNTHESIZE, content=b"RIFF not json")
        self.assert_json_error(response, 400, RuntimeErrorType.INVALID_INPUT, None)


class TestOperationalSurface:
    def test_ready_after_lifespan_startup(self, client: TestClient) -> None:
        assert client.get("/health/ready").json() == {"status": "ready"}
        assert client.get("/health/live").json() == {"status": "alive"}

    def test_info_is_operational_identity_only(self, client: TestClient) -> None:
        info = client.get("/info").json()
        assert info["service"] == "tts-runtime"
        assert info["capability"] == "speech_synthesis"
        assert info["voices"] == [
            "english-female",
            "english-male",
            "reference-alto",
            "reference-bass",
        ]
        assert info["pool"] == {"admitted": 0, "max_concurrency": 2, "max_queue": 2}
        model = info["models"][0]
        assert model["artifact"] == "reference"
        assert model["load_ms"] >= 0
        assert model["warmup_ms"] >= 0  # warm-up ran, measured, before traffic

    def test_request_id_is_echoed(self, client: TestClient) -> None:
        response = client.post(
            ROUTE_SYNTHESIZE, json={"text": "hi"}, headers={HEADER_REQUEST_ID: "req-123"}
        )
        assert response.headers[HEADER_REQUEST_ID] == "req-123"
