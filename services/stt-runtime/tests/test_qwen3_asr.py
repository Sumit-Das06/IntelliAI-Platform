"""Qwen3-ASR adapter guarantees — all offline, no model, no binary.

The engine's seam-facing behavior (parsing, language resolution, WAV
transport, artifact identity, slot admission, error shaping, timeouts)
is provable against a loopback HTTP stub. What needs the real model —
accuracy, RTF, RSS — lives in the evaluation ledger, never in CI.
"""

from __future__ import annotations

import json
import struct
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

import pytest

from intelliai_runtime_contract import TranscriptionRequest
from intelliai_runtime_core import RuntimeServiceError
from intelliai_stt_runtime.config import Settings
from intelliai_stt_runtime.engines import qwen3_asr
from intelliai_stt_runtime.engines.qwen3_asr import (
    ARTIFACT_ID,
    ASR_MARKER,
    ASR_PROMPT,
    QWEN3_ASR_0_6B_FILES,
    Qwen3AsrEngine,
    parse_asr_output,
    resolve_language,
    wav_bytes,
)
from intelliai_stt_runtime.pipeline import DecodedAudio
from intelliai_stt_runtime.slots import CATALOG, build_slot_specs


def _audio(seconds: float = 1.0) -> DecodedAudio:
    frames = int(16000 * seconds)
    return DecodedAudio(
        pcm=b"\x01\x00" * frames,
        sample_rate_hz=16000,
        channels=1,
        sample_width_bytes=2,
        duration_seconds=seconds,
    )


class TestOutputParsing:
    def test_the_documented_shape_parses(self) -> None:
        emitted, text = parse_asr_output(f"language Hindi{ASR_MARKER}नमस्ते दुनिया")
        assert emitted == "Hindi"
        assert text == "नमस्ते दुनिया"

    def test_marker_without_language_header(self) -> None:
        emitted, text = parse_asr_output(f"{ASR_MARKER}hello world")
        assert emitted is None
        assert text == "hello world"

    def test_no_marker_means_the_whole_output_is_transcript(self) -> None:
        emitted, text = parse_asr_output("  raw output  ")
        assert emitted is None
        assert text == "raw output"

    def test_empty_output_stays_empty(self) -> None:
        # The correct transcription of silence is nothing (contract rule);
        # the parser must not invent text for it.
        assert parse_asr_output(f"language None{ASR_MARKER}") == ("None", "")

    def test_language_resolution_prefers_the_mapped_detection(self) -> None:
        assert resolve_language("Hindi", None) == "hi"
        assert resolve_language("Chinese", "hi") == "zh"
        assert resolve_language("English", None) == "en"
        # Unmapped detection falls back to the caller's hint, then "und" —
        # the adapter never guesses a code it cannot stand behind.
        assert resolve_language("Klingon", "ta") == "ta"
        assert resolve_language(None, None) == "und"


class TestWavTransport:
    def test_header_describes_the_canonical_pcm_exactly(self) -> None:
        audio = _audio(0.25)
        blob = wav_bytes(audio)
        assert blob[:4] == b"RIFF"
        assert blob[8:12] == b"WAVE"
        assert blob[12:16] == b"fmt "
        fmt, channels, rate, byte_rate, block_align, bits = struct.unpack("<HHIIHH", blob[20:36])
        assert (fmt, channels, rate, bits) == (1, 1, 16000, 16)
        assert byte_rate == 16000 * 2
        assert block_align == 2
        assert blob[36:40] == b"data"
        assert struct.unpack("<I", blob[40:44])[0] == len(audio.pcm)
        assert blob[44:] == audio.pcm


class TestArtifactIdentity:
    def test_the_pins_are_the_official_ggml_org_conversion(self) -> None:
        # Research artifact with PUBLIC distribution: unlike the .invalid
        # fine-tunes, these URLs are real because the publisher really
        # hosts these bytes. The revision is pinned in the URL itself.
        assert QWEN3_ASR_0_6B_FILES.artifact == ARTIFACT_ID == "qwen3-asr-0.6b"
        assert QWEN3_ASR_0_6B_FILES.version == 1
        names = {f.filename for f in QWEN3_ASR_0_6B_FILES.files}
        assert names == {"Qwen3-ASR-0.6B-Q8_0.gguf", "mmproj-Qwen3-ASR-0.6B-Q8_0.gguf"}
        for file in QWEN3_ASR_0_6B_FILES.files:
            assert file.url.startswith(
                "https://huggingface.co/ggml-org/Qwen3-ASR-0.6B-GGUF/resolve/928ab958"
            )
            assert len(file.sha256) == 64
            assert set(file.sha256) <= set("0123456789abcdef")

    def test_catalog_hosts_the_family_as_weightful(self) -> None:
        binding = CATALOG["qwen3-asr"]
        assert binding.artifact == ARTIFACT_ID
        assert binding.weightless is False
        assert binding.registered == qwen3_asr.ARTIFACT_SPECS
        assert ARTIFACT_ID in binding.registered

    def test_a_deployment_can_declare_it(self) -> None:
        specs = build_slot_specs(Settings(slots="qwen3-asr"))
        assert len(specs) == 1
        assert specs[0].artifact == ARTIFACT_ID
        assert specs[0].files is QWEN3_ASR_0_6B_FILES

    def test_it_cannot_be_relabelled(self) -> None:
        # Weightful law: identity comes from pins, never from declarations.
        with pytest.raises(ValueError, match="determined by them"):
            build_slot_specs(Settings(slots="qwen3-asr:some-other-name"))


class _StubHandler(BaseHTTPRequestHandler):
    """Configurable llama-server stand-in for one test at a time."""

    mode = "ok"
    content = f"language Hindi{ASR_MARKER}नमस्ते"
    last_payload: dict[str, Any] | None = None

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        type(self).last_payload = json.loads(self.rfile.read(length) or b"{}")
        if self.command == "POST" and self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        if type(self).mode == "slow":
            time.sleep(1.5)
        if type(self).mode == "malformed":
            body = b"not json at all"
        else:
            body = json.dumps({"choices": [{"message": {"content": type(self).content}}]}).encode(
                "utf-8"
            )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        del format, args  # silence test output


@pytest.fixture
def stub_server() -> Any:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _StubHandler.mode = "ok"
    _StubHandler.last_payload = None
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


def _engine(base_url: str, *, timeout: float = 5.0) -> Qwen3AsrEngine:
    fake_process = cast(subprocess.Popen[bytes], _FakeProcess())
    return Qwen3AsrEngine(fake_process, base_url, context_tokens=4096, timeout_seconds=timeout)


class _FakeProcess:
    def __init__(self) -> None:
        self.terminated = False

    def poll(self) -> int | None:
        return 0 if self.terminated else None

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        return 0

    def kill(self) -> None:
        self.terminated = True


class TestTranscription:
    def test_hindi_result_is_contract_shaped(self, stub_server: str) -> None:
        engine = _engine(stub_server)
        result = engine.transcribe(_audio(2.0), TranscriptionRequest(language="hi"))
        assert result.text == "नमस्ते"
        assert result.language == "hi"
        assert result.duration_seconds == 2.0
        # No timestamps exist in this lineage: one utterance-spanning segment.
        assert len(result.segments) == 1
        assert result.segments[0].start_seconds == 0.0
        assert result.segments[0].end_seconds == 2.0

    def test_the_request_carries_greedy_decode_and_the_fixed_prompt(self, stub_server: str) -> None:
        engine = _engine(stub_server)
        engine.transcribe(_audio(0.5), TranscriptionRequest())
        payload = _StubHandler.last_payload
        assert payload is not None
        assert payload["temperature"] == 0.0
        parts = payload["messages"][0]["content"]
        assert parts[0]["type"] == "input_audio"
        assert parts[0]["input_audio"]["format"] == "wav"
        assert parts[1] == {"type": "text", "text": ASR_PROMPT}

    def test_detected_language_beats_the_hint(self, stub_server: str) -> None:
        _StubHandler.content = f"language Chinese{ASR_MARKER}你好"
        result = _engine(stub_server).transcribe(_audio(), TranscriptionRequest(language="hi"))
        assert result.language == "zh"

    def test_empty_transcript_is_a_result_not_an_error(self, stub_server: str) -> None:
        # Silence/tone probes legitimately produce nothing; an adapter
        # that errored on emptiness would fake a hallucination gate.
        _StubHandler.content = f"language None{ASR_MARKER}"
        result = _engine(stub_server).transcribe(_audio(), TranscriptionRequest(language="hi"))
        assert result.text == ""
        assert result.segments == ()
        assert result.language == "hi"

    def test_malformed_upstream_is_a_contract_error(self, stub_server: str) -> None:
        _StubHandler.mode = "malformed"
        with pytest.raises(RuntimeServiceError) as excinfo:
            _engine(stub_server).transcribe(_audio(), TranscriptionRequest())
        assert excinfo.value.error_type.value == "internal"

    def test_timeout_is_a_contract_error_not_a_hang(self, stub_server: str) -> None:
        _StubHandler.mode = "slow"
        with pytest.raises(RuntimeServiceError) as excinfo:
            _engine(stub_server, timeout=0.3).transcribe(_audio(), TranscriptionRequest())
        assert excinfo.value.error_type.value == "internal"

    def test_close_terminates_the_child(self, stub_server: str) -> None:
        fake = _FakeProcess()
        engine = Qwen3AsrEngine(
            cast(subprocess.Popen[bytes], fake),
            stub_server,
            context_tokens=4096,
            timeout_seconds=5.0,
        )
        engine.close()
        assert fake.terminated


class TestDescription:
    def test_it_reports_the_decode_policy_actually_sent(self) -> None:
        description = _engine("http://127.0.0.1:9").describe()
        assert description.compute_type == "q8_0"
        assert description.emitted_unit == "word"
        params = description.decode_params
        assert params["temperature"] == "0.0"
        assert params["timestamps"] == "false"
        assert params["prompt"] == ASR_PROMPT
        assert params["context_tokens"] == "4096"

    def test_no_local_path_leaks_through_the_description(self) -> None:
        # /info is runtime-internal, but descriptions still travel into
        # committed evidence records — machine paths do not belong there.
        params = _engine("http://127.0.0.1:9").describe().decode_params
        for value in params.values():
            assert "\\" not in value
            assert ":/" not in value and ":\\" not in value


class TestLoaderRefusals:
    def test_missing_artifact_directory_is_refused(self) -> None:
        with pytest.raises(ValueError, match="verified artifact directory"):
            qwen3_asr.load_qwen3_asr(None, server_binary=Path("llama-server.exe"))

    def test_missing_server_binary_is_an_actionable_error(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="INTELLIAI_STT_QWEN3_SERVER_BINARY"):
            qwen3_asr.load_qwen3_asr(tmp_path, server_binary=tmp_path / "does-not-exist.exe")
