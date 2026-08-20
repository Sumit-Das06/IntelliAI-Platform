"""M36 streaming laws, proven with the deterministic reference engine:
progressive delivery is the SAME audio, earlier — never different audio.
"""

import struct
import wave
from collections.abc import Iterator
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from intelliai_runtime_contract import RuntimeResponse, SpeechSynthesisResult
from intelliai_tts_runtime.api.binding import HEADER_RUNTIME_ENVELOPE, ROUTE_SYNTHESIZE
from intelliai_tts_runtime.api.wav import streaming_wav_header
from intelliai_tts_runtime.config import Settings
from intelliai_tts_runtime.engines.kokoro import _stream_chunks
from intelliai_tts_runtime.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(Settings(slots="reference", max_concurrency=2, max_queue=2))
    with TestClient(app) as test_client:
        yield test_client


def parse_envelope(header: str) -> RuntimeResponse[SpeechSynthesisResult]:
    return RuntimeResponse[SpeechSynthesisResult].model_validate_json(header)


class TestStreamingWavHeader:
    def test_44_bytes_with_exact_format_facts_and_placeholder_sizes(self) -> None:
        header = streaming_wav_header(24_000)
        assert len(header) == 44
        assert header[:4] == b"RIFF" and header[8:12] == b"WAVE"
        assert struct.unpack("<I", header[4:8])[0] == 0xFFFFFFFF
        assert struct.unpack("<I", header[40:44])[0] == 0xFFFFFFFF
        # fmt facts are exact: PCM, mono, 24 kHz, 16-bit.
        fmt = struct.unpack("<IHHIIHH", header[16:36])
        assert fmt == (16, 1, 1, 24_000, 48_000, 2, 16)


class TestStreamingRoute:
    def test_streamed_pcm_equals_the_whole_body_audio(self, client: TestClient) -> None:
        # The reference engine is deterministic, so the law is exact:
        # header + concatenated stream chunks == the non-stream WAV's
        # audio, byte for byte. Streaming changes WHEN, never WHAT.
        whole = client.post(ROUTE_SYNTHESIZE, json={"text": "same words"})
        with wave.open(BytesIO(whole.content), "rb") as reader:
            whole_pcm = reader.readframes(reader.getnframes())

        with client.stream(
            "POST", ROUTE_SYNTHESIZE, json={"text": "same words", "stream": True}
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("audio/wav")
            body = b"".join(response.iter_bytes())
        assert body[:44] == streaming_wav_header(24_000)
        assert body[44:] == whole_pcm

    def test_streaming_envelope_is_preflight_identity(self, client: TestClient) -> None:
        text = "envelope facts"
        with client.stream(
            "POST", ROUTE_SYNTHESIZE, json={"text": text, "stream": True}
        ) as response:
            envelope = parse_envelope(response.headers[HEADER_RUNTIME_ENVELOPE])
            body = b"".join(response.iter_bytes())
        assert envelope.output.characters == len(text)
        assert envelope.output.voice == "english-female"
        assert envelope.output.duration_seconds == 0.0  # by contract: unknowable up front
        assert envelope.output.sample_rate_hz == 24_000
        assert "first_chunk" in envelope.timing.stages
        assert len(body) > 44

    def test_invalid_input_stays_an_ordinary_json_error(self, client: TestClient) -> None:
        response = client.post(ROUTE_SYNTHESIZE, json={"text": "x" * 5000, "stream": True})
        assert response.status_code == 400
        assert response.json()["param"] == "text"  # RuntimeErrorResponse shape
        assert HEADER_RUNTIME_ENVELOPE not in response.headers

    def test_unknown_voice_stays_an_ordinary_json_error(self, client: TestClient) -> None:
        response = client.post(
            ROUTE_SYNTHESIZE, json={"text": "hi", "voice": "nope", "stream": True}
        )
        assert response.status_code == 400
        assert response.json()["param"] == "voice"  # RuntimeErrorResponse shape

    def test_default_remains_whole_body(self, client: TestClient) -> None:
        response = client.post(ROUTE_SYNTHESIZE, json={"text": "no stream field"})
        # A complete, well-formed WAV with true sizes — not the streaming
        # placeholder header.
        with wave.open(BytesIO(response.content), "rb") as reader:
            assert reader.getnframes() > 0


class TestStreamChunkPlan:
    def test_first_chunk_is_small_rest_rides_the_merge_budget(self) -> None:
        text = ("First sentence here. " * 2 + "Filler sentence follows. " * 20).strip()
        chunks = list(_stream_chunks(text, first_budget=60))
        assert len(chunks) >= 2
        assert len(chunks[0]) <= 60
        # No text lost, no text duplicated, order preserved.
        assert " ".join(chunks).split() == text.split()

    def test_single_short_sentence_is_one_chunk(self) -> None:
        assert list(_stream_chunks("Hello there.", first_budget=90)) == ["Hello there."]

    def test_giant_first_sentence_word_wraps_to_the_budget(self) -> None:
        text = "word " * 100
        chunks = list(_stream_chunks(text.strip(), first_budget=50))
        assert len(chunks[0]) <= 50
        assert " ".join(chunks).split() == text.split()


class TestStreamSettings:
    def test_streaming_defaults_are_pinned(self) -> None:
        settings = Settings(slots="reference")
        assert settings.stream_first_chunk_chars == 90
        assert settings.stream_buffer_chunks == 4
