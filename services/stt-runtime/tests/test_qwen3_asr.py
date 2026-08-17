"""Qwen3-ASR adapter guarantees — all offline, no model, no binary.

The engine's seam-facing behavior (parsing, language resolution, WAV
transport, artifact identity, slot admission, error shaping, timeouts)
is provable against a loopback HTTP stub. What needs the real model —
accuracy, RTF, RSS — lives in the evaluation ledger, never in CI.
"""

from __future__ import annotations

import itertools
import json
import struct
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar, cast

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

    def test_the_hi_ft_e1_candidate_is_registered_research_only(self) -> None:
        # M21: the fine-tune is ADMITTED (a pinned entry, selectable via
        # the registered-artifact declaration) and nothing more — its
        # model URL uses the RFC-reserved .invalid TLD so it can never
        # resolve, and its mmproj IS the official pinned artifact
        # byte-for-byte (the audio tower was frozen in training).
        spec = qwen3_asr.ARTIFACT_SPECS["qwen3-asr-0.6b-hi-ft-e1"]
        by_name = {f.filename: f for f in spec.files}
        model_url = by_name["Qwen3-ASR-0.6B-Q8_0.gguf"].url
        assert ".invalid/m21/qwen3-asr-0.6b-hi-ft-e1/" in model_url
        official = {f.filename: f for f in QWEN3_ASR_0_6B_FILES.files}
        assert (
            by_name["mmproj-Qwen3-ASR-0.6B-Q8_0.gguf"].sha256
            == official["mmproj-Qwen3-ASR-0.6B-Q8_0.gguf"].sha256
        )
        # And the text weights are NOT the incumbent's: a distinct model.
        assert (
            by_name["Qwen3-ASR-0.6B-Q8_0.gguf"].sha256
            != official["Qwen3-ASR-0.6B-Q8_0.gguf"].sha256
        )

    def test_the_candidate_is_selectable_through_the_admission_law(self) -> None:
        specs = build_slot_specs(Settings(slots="qwen3-asr:qwen3-asr-0.6b-hi-ft-e1"))
        assert specs[0].artifact == "qwen3-asr-0.6b-hi-ft-e1"
        assert specs[0].files is qwen3_asr.ARTIFACT_SPECS["qwen3-asr-0.6b-hi-ft-e1"]

    def test_the_e2_candidate_is_registered_research_only(self) -> None:
        # M22: same laws as E1 — .invalid model URL, the OFFICIAL mmproj
        # byte-for-byte (tower frozen), distinct text weights, and
        # distinct from E1 (a new experiment is a new identity).
        spec = qwen3_asr.ARTIFACT_SPECS["qwen3-asr-0.6b-hi-ft-e2"]
        by_name = {f.filename: f for f in spec.files}
        assert ".invalid/m22/qwen3-asr-0.6b-hi-ft-e2/" in by_name["Qwen3-ASR-0.6B-Q8_0.gguf"].url
        official = {f.filename: f for f in QWEN3_ASR_0_6B_FILES.files}
        e1 = {f.filename: f for f in qwen3_asr.ARTIFACT_SPECS["qwen3-asr-0.6b-hi-ft-e1"].files}
        assert (
            by_name["mmproj-Qwen3-ASR-0.6B-Q8_0.gguf"].sha256
            == official["mmproj-Qwen3-ASR-0.6B-Q8_0.gguf"].sha256
        )
        model_sha = by_name["Qwen3-ASR-0.6B-Q8_0.gguf"].sha256
        assert model_sha != official["Qwen3-ASR-0.6B-Q8_0.gguf"].sha256
        assert model_sha != e1["Qwen3-ASR-0.6B-Q8_0.gguf"].sha256
        specs = build_slot_specs(Settings(slots="qwen3-asr:qwen3-asr-0.6b-hi-ft-e2"))
        assert specs[0].artifact == "qwen3-asr-0.6b-hi-ft-e2"

    def test_the_chunking_settings_reach_the_loader(self) -> None:
        # M19: the long-audio shape is deployment configuration — every
        # knob a canary overlay sets must actually arrive at the loader,
        # or a raised ceiling would silently serve the built-in defaults.
        specs = build_slot_specs(
            Settings(
                slots="qwen3-asr",
                qwen3_max_audio_seconds=600.0,
                qwen3_direct_audio_seconds=110.0,
                qwen3_chunk_window_seconds=90.0,
                qwen3_chunk_overlap_seconds=4.0,
                qwen3_chunk_snap_radius_seconds=6.0,
            )
        )
        keywords = cast(Any, specs[0].load).keywords
        assert keywords["max_audio_seconds"] == 600.0
        assert keywords["direct_audio_seconds"] == 110.0
        assert keywords["chunk_window_seconds"] == 90.0
        assert keywords["chunk_overlap_seconds"] == 4.0
        assert keywords["chunk_snap_radius_seconds"] == 6.0


class _StubHandler(BaseHTTPRequestHandler):
    """Configurable llama-server stand-in for one test at a time.

    ``content`` answers every request identically; ``script`` (when
    non-empty) answers each request with the NEXT entry instead — the
    chunked path's per-window sequencing needs ordered answers. The
    sentinel ``"@fail"`` answers one request with a 500, which the
    engine maps like any transport failure.
    """

    mode = "ok"
    content = f"language Hindi{ASR_MARKER}नमस्ते"
    script: ClassVar[list[str]] = []
    last_payload: dict[str, Any] | None = None

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        type(self).last_payload = json.loads(self.rfile.read(length) or b"{}")
        if self.command == "POST" and self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        if type(self).mode == "slow":
            time.sleep(1.5)
        answer = type(self).content
        if type(self).script:
            answer = type(self).script.pop(0)
        if answer == "@fail":
            self.send_error(500)
            return
        if answer == "@truncate":
            # A child dying MID-RESPONSE: headers promise more body than
            # ever arrives, then the connection closes. The client's
            # read() raises http.client.IncompleteRead — the raw shape
            # the M19 kill-mid-window staging drill surfaced.
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", "1000")
            self.end_headers()
            self.wfile.write(b'{"choices": [')
            self.wfile.flush()
            self.connection.close()
            return
        if type(self).mode == "malformed":
            body = b"not json at all"
        else:
            body = json.dumps({"choices": [{"message": {"content": answer}}]}).encode("utf-8")
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
    _StubHandler.content = f"language Hindi{ASR_MARKER}नमस्ते"
    _StubHandler.script = []
    _StubHandler.last_payload = None
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


def _engine(base_url: str, *, timeout: float = 5.0) -> Qwen3AsrEngine:
    fake_process = cast(subprocess.Popen[bytes], _FakeProcess())
    return Qwen3AsrEngine(fake_process, base_url, context_tokens=4096, timeout_seconds=timeout)


def test_a_shared_closed_event_aborts_in_flight_spawns() -> None:
    # Milestone 17 orphan fix: the loader hands its cancel event to the
    # engine, and the spawn closure watches the SAME event — so close()
    # reaches work the engine object cannot see (a spawn mid-health-wait).
    shared = threading.Event()
    engine = Qwen3AsrEngine(
        cast(subprocess.Popen[bytes], _FakeProcess()),
        "http://127.0.0.1:9",
        context_tokens=4096,
        timeout_seconds=1.0,
        closed_event=shared,
    )
    assert not shared.is_set()
    engine.close()
    assert shared.is_set()


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
        self._assert_message_names_nothing_internal(excinfo.value.message)

    def test_timeout_is_a_contract_error_not_a_hang(self, stub_server: str) -> None:
        _StubHandler.mode = "slow"
        with pytest.raises(RuntimeServiceError) as excinfo:
            _engine(stub_server, timeout=0.3).transcribe(_audio(), TranscriptionRequest())
        assert excinfo.value.error_type.value == "internal"
        self._assert_message_names_nothing_internal(excinfo.value.message)

    @staticmethod
    def _assert_message_names_nothing_internal(message: str) -> None:
        # Milestone 16 drill finding: envelope messages travel further
        # than the runtime, so they name no engine, model, or library.
        lowered = message.lower()
        for marker in ("qwen", "llama", "gguf", "ggml", "whisper"):
            assert marker not in lowered, message

    def test_audio_beyond_the_product_ceiling_is_refused_loudly(self) -> None:
        # M17 Phase 6 finding: beyond what the serving shape can decode,
        # a single pass silently truncates while returning 200 — silent
        # data loss is the one failure a customer cannot detect. Since
        # M19 Phase 18 the DEFAULT ceiling is 600 s (chunked above the
        # 120 s direct limit); beyond it the loud refusal remains.
        engine = _engine("http://127.0.0.1:9")
        long_audio = DecodedAudio(
            pcm=b"\x01\x00" * 16000,  # 1 s of frames; duration says otherwise
            sample_rate_hz=16000,
            channels=1,
            sample_width_bytes=2,
            duration_seconds=601.0,
        )
        with pytest.raises(RuntimeServiceError) as excinfo:
            engine.transcribe(long_audio, TranscriptionRequest(language="hi"))
        assert excinfo.value.error_type.value == "invalid_input"
        assert excinfo.value.param == "file"
        assert "600 seconds" in excinfo.value.message
        for marker in ("qwen", "llama", "ctx", "context"):
            assert marker not in excinfo.value.message.lower()

    def test_audio_at_the_ceiling_is_served(self, stub_server: str) -> None:
        engine = _engine(stub_server)
        at_limit = DecodedAudio(
            pcm=b"\x01\x00" * 16000,
            sample_rate_hz=16000,
            channels=1,
            sample_width_bytes=2,
            duration_seconds=120.0,
        )
        result = engine.transcribe(at_limit, TranscriptionRequest(language="hi"))
        assert result.text == "नमस्ते"

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
        # M19: the chunking shape is decode configuration — evidence
        # records must say which long-audio geometry produced a result.
        assert params["direct_audio_seconds"] == "120.0"
        assert params["chunk_window_seconds"] == "100.0"
        assert params["chunk_overlap_seconds"] == "5.0"
        assert params["chunk_snap_radius_seconds"] == "8.0"

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


class TestRuntimeSupplyChain:
    """Milestone 16: the decoder build is pinned like the weights."""

    def test_the_pin_tables_cover_the_load_bearing_files(self) -> None:
        # The server executable and every library that executes model
        # bytes, PER PLATFORM. A pin table that lost one of these would
        # verify a shell around an unverified core.
        required = {
            "win32": {"llama-server.exe", "llama-server-impl.dll", "llama.dll", "mtmd.dll"},
            "linux": {"llama-server", "libllama-server-impl.so", "libllama.so", "libmtmd.so"},
        }
        for platform, needed in required.items():
            table = qwen3_asr._RUNTIME_BINARY_PINS_BY_PLATFORM[platform]
            assert needed <= set(table), platform
            for digest in table.values():
                assert len(digest) == 64
                assert set(digest) <= set("0123456789abcdef")
        # And the platform this test runs on must itself be pinned — CI
        # (linux) and the dev machine (win32) both exercise a real table.
        assert qwen3_asr.RUNTIME_BINARY_PINS

    def test_an_unpinned_binary_is_refused(self, tmp_path: Path) -> None:
        # A directory with the right filenames but wrong bytes: the exact
        # shape of a silent build swap.
        for filename in qwen3_asr.RUNTIME_BINARY_PINS:
            (tmp_path / filename).write_bytes(b"not the pinned build")
        with pytest.raises(ValueError, match="unpinned build"):
            qwen3_asr.verify_runtime_binaries(tmp_path / "llama-server.exe")

    def test_a_missing_runtime_file_is_refused_not_skipped(self, tmp_path: Path) -> None:
        # An empty directory: nothing to hash is the same refusal as a
        # wrong hash — an unverifiable runtime is an unpinned runtime.
        with pytest.raises(ValueError, match="missing beside"):
            qwen3_asr.verify_runtime_binaries(tmp_path / "llama-server.exe")

    def test_load_verifies_before_spawning(self, tmp_path: Path) -> None:
        # An existing-but-unpinned binary must be refused by load itself,
        # before any process is spawned.
        server = tmp_path / "llama-server.exe"
        server.write_bytes(b"impostor")
        with pytest.raises(ValueError, match="pinned"):
            qwen3_asr.load_qwen3_asr(tmp_path, server_binary=server)

    def test_description_names_the_pinned_build(self) -> None:
        params = _engine("http://127.0.0.1:9").describe().decode_params
        assert params["server_build"] == qwen3_asr.RUNTIME_BUILD
        assert "b10344" in params["server_build"]

    def test_every_pinned_platform_names_the_same_tag(self) -> None:
        # Windows and Linux are separate measured systems with separate
        # tables, but they must pin the SAME upstream release: a version
        # skew between platforms would make cross-platform evidence
        # incomparable without anyone having decided that.
        for platform, build in qwen3_asr._RUNTIME_BUILDS.items():
            assert "b10344" in build, (platform, build)


def _wait_until(predicate: Any, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not reached in time")


class _RestartableProcess:
    """A fake child whose death the test controls."""

    def __init__(self) -> None:
        self.dead: int | None = None
        self.terminated = False

    def poll(self) -> int | None:
        return self.dead

    def terminate(self) -> None:
        self.terminated = True
        self.dead = -15

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        return self.dead or 0

    def kill(self) -> None:
        self.terminated = True
        self.dead = -9


def _supervised(
    spawn_results: list[Any], *, backoff: tuple[float, ...] = (0.0, 0.0, 0.0)
) -> tuple[Qwen3AsrEngine, _RestartableProcess, list[float], list[Any]]:
    """An engine under supervision with a scripted spawn outcome list."""
    first = _RestartableProcess()
    slept: list[float] = []
    spawned: list[Any] = []

    def spawn() -> tuple[subprocess.Popen[bytes], str]:
        outcome = spawn_results.pop(0) if spawn_results else RuntimeError("exhausted")
        if isinstance(outcome, Exception):
            raise outcome
        spawned.append(outcome)
        return cast(subprocess.Popen[bytes], outcome), "http://127.0.0.1:9"

    engine = Qwen3AsrEngine(
        cast(subprocess.Popen[bytes], first),
        "http://127.0.0.1:9",
        context_tokens=4096,
        timeout_seconds=5.0,
        spawn=spawn,
        restart_backoff_seconds=backoff,
        monitor_interval_seconds=0.01,
        sleep=slept.append,
    )
    return engine, first, slept, spawned


class TestSupervisedRestart:
    """Milestone 17 Phase 3: bounded recovery, truthful states, no orphans."""

    def test_child_alive_means_ready(self) -> None:
        engine, first, _, _ = _supervised([])
        try:
            assert engine.slot_state() == "ready"
            assert engine.slot_stats() == {"restarts_completed": 0, "restart_attempts": 0}
        finally:
            engine.close()
        assert first.terminated  # close leaves no orphan

    def test_death_flips_readiness_then_restart_restores_it(self) -> None:
        replacement = _RestartableProcess()
        engine, first, slept, spawned = _supervised([replacement], backoff=(0.0,))
        try:
            first.dead = 1
            _wait_until(lambda: engine.slot_state() == "ready" and spawned)
            assert engine.slot_stats()["restarts_completed"] == 1
            assert slept == [0.0]  # backoff observed before the attempt
        finally:
            engine.close()
        assert replacement.terminated  # the ADOPTED child is what close kills

    def test_repeated_failures_stop_at_the_configured_bound(self) -> None:
        engine, first, _, _ = _supervised(
            [RuntimeError("down"), RuntimeError("still down"), RuntimeError("dead")],
            backoff=(0.0, 0.0, 0.0),
        )
        try:
            first.dead = 1
            _wait_until(lambda: engine.slot_state() == "failed")
            # Exactly as many attempts as the schedule has entries — and
            # the state is terminal: no hidden retry after failed.
            assert engine.slot_stats()["restart_attempts"] == 3
            time.sleep(0.05)
            assert engine.slot_stats()["restart_attempts"] == 3
            assert engine.slot_state() == "failed"
        finally:
            engine.close()

    def test_requests_are_refused_truthfully_while_not_ready(self) -> None:
        engine, first, _, _ = _supervised([RuntimeError("x")], backoff=(0.0,))
        try:
            first.dead = 1
            _wait_until(lambda: engine.slot_state() == "failed")
            with pytest.raises(RuntimeServiceError) as excinfo:
                engine.transcribe(_audio(), TranscriptionRequest())
            assert excinfo.value.error_type.value == "not_ready"
            lowered = excinfo.value.message.lower()
            for marker in ("qwen", "llama", "gguf"):
                assert marker not in lowered
        finally:
            engine.close()

    def test_dead_child_midflight_reads_as_not_ready_not_internal(self) -> None:
        # A connection error WITH a dead child is an outage, not a bug:
        # the envelope should say not_ready so callers back off correctly.
        dead = _RestartableProcess()
        dead.dead = 1
        engine = Qwen3AsrEngine(
            cast(subprocess.Popen[bytes], dead),
            "http://127.0.0.1:1",  # nothing listens: connection refused
            context_tokens=4096,
            timeout_seconds=0.5,
        )
        with pytest.raises(RuntimeServiceError) as excinfo:
            engine.transcribe(_audio(), TranscriptionRequest())
        assert excinfo.value.error_type.value == "not_ready"

    def test_close_during_restart_never_adopts_a_new_child(self) -> None:
        # The interleaving is FORCED, not raced: spawn blocks until the
        # test has observed that close() marked the engine closed, so the
        # spawn provably returns after close began.
        adopted = _RestartableProcess()
        spawn_entered = threading.Event()
        release = threading.Event()

        def blocking_spawn() -> tuple[subprocess.Popen[bytes], str]:
            spawn_entered.set()
            release.wait(10.0)
            return cast(subprocess.Popen[bytes], adopted), "http://127.0.0.1:9"

        first = _RestartableProcess()
        engine = Qwen3AsrEngine(
            cast(subprocess.Popen[bytes], first),
            "http://127.0.0.1:9",
            context_tokens=4096,
            timeout_seconds=5.0,
            spawn=blocking_spawn,
            restart_backoff_seconds=(0.0,),
            monitor_interval_seconds=0.01,
            sleep=lambda _: None,
        )
        first.dead = 1
        assert spawn_entered.wait(5.0)
        assert engine.slot_state() == "restarting"
        closer = threading.Thread(target=engine.close)
        closer.start()
        _wait_until(engine._closed.is_set)  # private by design: the ordering under test
        release.set()
        closer.join(timeout=15.0)
        assert not closer.is_alive()
        # The child spawned after close must be terminated, not adopted.
        _wait_until(lambda: adopted.terminated)


class TestWindowPlanning:
    """M19 Phase 3: deterministic, bounded chunk arithmetic."""

    def _plan(self, duration: float) -> list[tuple[float, float]]:
        from intelliai_stt_runtime.engines.qwen3_asr import plan_windows

        return plan_windows(duration, window_seconds=100.0, overlap_seconds=5.0)

    def test_at_or_below_one_window_is_a_single_window(self) -> None:
        assert self._plan(100.0) == [(0.0, 100.0)]
        assert self._plan(42.0) == [(0.0, 42.0)]

    def test_just_over_a_window_splits_with_overlap(self) -> None:
        windows = self._plan(120.1)
        assert windows == [(0.0, 100.0), (95.0, 120.1)]

    @pytest.mark.parametrize(
        ("duration", "count"),
        [(200.0, 3), (300.0, 4), (600.0, 7)],
    )
    def test_window_counts_match_the_researched_shapes(self, duration: float, count: int) -> None:
        windows = self._plan(duration)
        assert len(windows) == count
        # Full coverage, ordered, overlapping by exactly the overlap.
        assert windows[0][0] == 0.0
        assert windows[-1][1] == duration
        for (a_start, a_end), (b_start, _) in itertools.pairwise(windows):
            assert b_start == a_end - 5.0
            assert a_start < b_start

    def test_a_sliver_tail_is_absorbed_not_decoded(self) -> None:
        # 195 + tiny: the remainder after the second window start (95)
        # would be <= overlap — extend the last window instead.
        windows = self._plan(197.0)
        assert windows == [(0.0, 100.0), (95.0, 197.0)]

    def test_overlap_must_be_smaller_than_the_window(self) -> None:
        from intelliai_stt_runtime.engines.qwen3_asr import plan_windows

        with pytest.raises(ValueError, match="longer than the overlap"):
            plan_windows(300.0, window_seconds=5.0, overlap_seconds=5.0)


class TestAudioSlicing:
    """M19 Phase 3: frame-exact PCM slices, no re-decode, no disk."""

    def test_slices_preserve_format_and_duration(self) -> None:
        from intelliai_stt_runtime.engines.qwen3_asr import slice_audio

        audio = _audio(10.0)
        piece = slice_audio(audio, 2.0, 7.5)
        assert piece.sample_rate_hz == audio.sample_rate_hz
        assert piece.channels == audio.channels
        assert piece.sample_width_bytes == audio.sample_width_bytes
        assert piece.duration_seconds == pytest.approx(5.5)
        assert len(piece.pcm) == int(5.5 * 16000) * 2

    def test_adjacent_slices_reassemble_exactly(self) -> None:
        from intelliai_stt_runtime.engines.qwen3_asr import slice_audio

        audio = _audio(3.0)
        first = slice_audio(audio, 0.0, 1.7)
        second = slice_audio(audio, 1.7, 3.0)
        assert first.pcm + second.pcm == audio.pcm


class TestBoundarySnap:
    """M19 Phase 4: a deterministic energy argmin near the seam."""

    @staticmethod
    def _audio_with_gap(gap_at: float, total: float = 30.0) -> DecodedAudio:
        rate = 16000
        loud = (1000).to_bytes(2, "little", signed=True)
        quiet = (0).to_bytes(2, "little", signed=True)
        frames = bytearray()
        gap_start = int(gap_at * rate)
        gap_end = int((gap_at + 0.4) * rate)
        for i in range(int(total * rate)):
            frames += quiet if gap_start <= i < gap_end else loud
        return DecodedAudio(
            pcm=bytes(frames),
            sample_rate_hz=rate,
            channels=1,
            sample_width_bytes=2,
            duration_seconds=total,
        )

    def test_snaps_into_a_nearby_silence(self) -> None:
        from intelliai_stt_runtime.engines.qwen3_asr import quietest_moment

        audio = self._audio_with_gap(gap_at=17.0)
        snapped = quietest_moment(audio, target_seconds=15.0, radius_seconds=8.0)
        assert 16.8 <= snapped <= 17.6

    def test_uniform_audio_keeps_a_stable_deterministic_choice(self) -> None:
        from intelliai_stt_runtime.engines.qwen3_asr import quietest_moment

        audio = _audio(30.0)
        first = quietest_moment(audio, 15.0, 8.0)
        second = quietest_moment(audio, 15.0, 8.0)
        assert first == second  # ties break deterministically

    def test_zero_radius_disables_snapping(self) -> None:
        from intelliai_stt_runtime.engines.qwen3_asr import quietest_moment

        audio = self._audio_with_gap(gap_at=17.0)
        assert quietest_moment(audio, 15.0, 0.0) == 15.0


class TestOverlapMerge:
    """M19 Phase 6: deterministic dedup on normalized words."""

    @staticmethod
    def _merge(previous: str, nxt: str) -> str:
        from intelliai_stt_runtime.engines.qwen3_asr import merge_chunk_text

        words = previous.split()
        return " ".join(words + merge_chunk_text(words, nxt))

    def test_exact_overlap_is_deduplicated(self) -> None:
        assert (
            self._merge("मेरा विद्यालय बहुत अच्छा है", "बहुत अच्छा है यह शहर में")
            == "मेरा विद्यालय बहुत अच्छा है यह शहर में"
        )

    def test_punctuation_and_case_do_not_defeat_the_match(self) -> None:
        assert (
            self._merge("Learning good MANNERS,", "manners doesn't come easy")
            == "Learning good MANNERS, doesn't come easy"
        )

    def test_no_overlap_appends_everything(self) -> None:
        assert self._merge("पहला हिस्सा", "दूसरा हिस्सा") == "पहला हिस्सा दूसरा हिस्सा"

    def test_repeated_speech_is_not_over_deduplicated(self) -> None:
        # Genuine repetition inside the NEW text (beyond the overlap
        # window) must survive — dedup only eats the seam.
        merged = self._merge("ठीक है ठीक है", "ठीक है फिर ठीक है चलो")
        assert merged == "ठीक है ठीक है फिर ठीक है चलो"

    def test_empty_chunk_output_adds_nothing(self) -> None:
        assert self._merge("कुछ शब्द", "") == "कुछ शब्द"

    def test_first_chunk_seeds_the_transcript(self) -> None:
        assert self._merge("", "पहली खिड़की का पाठ") == "पहली खिड़की का पाठ"

    def test_pure_punctuation_words_never_anchor_a_match(self) -> None:
        # A '-' normalizes to empty; matching on it would let unrelated
        # texts glue together at punctuation.
        assert self._merge("एक दो -", "- तीन चार") == "एक दो - - तीन चार"


class TestChunkedTranscription:
    """M19 Phases 5+7+19: the request-level laws, deterministically."""

    @staticmethod
    def _chunked_engine(
        stub_url: str, *, scripted: list[str], sleeps: list[float]
    ) -> Qwen3AsrEngine:
        _StubHandler.script = list(scripted)
        return Qwen3AsrEngine(
            cast(subprocess.Popen[bytes], _FakeProcess()),
            stub_url,
            context_tokens=4096,
            timeout_seconds=5.0,
            max_audio_seconds=600.0,
            direct_audio_seconds=120.0,
            chunk_window_seconds=100.0,
            chunk_overlap_seconds=5.0,
            chunk_snap_radius_seconds=0.0,  # fixed boundaries: deterministic windows
            sleep=sleeps.append,
        )

    def test_direct_path_is_untouched_at_the_boundary(self, stub_server: str) -> None:
        _StubHandler.script = [f"language Hindi{ASR_MARKER}सीधा रास्ता"]
        engine = self._chunked_engine(stub_server, scripted=[], sleeps=[])
        _StubHandler.script = [f"language Hindi{ASR_MARKER}सीधा रास्ता"]
        result = engine.transcribe(_audio(120.0), TranscriptionRequest(language="hi"))
        assert result.text == "सीधा रास्ता"
        assert len(result.segments) == 1
        assert result.segments[0].end_seconds == 120.0

    def test_three_window_request_merges_into_one_result(self, stub_server: str) -> None:
        sleeps: list[float] = []
        engine = self._chunked_engine(
            stub_server,
            scripted=[
                f"language Hindi{ASR_MARKER}पहली खिड़की का पाठ यहाँ समाप्त",
                f"language Hindi{ASR_MARKER}यहाँ समाप्त दूसरी खिड़की जारी",
                f"language Hindi{ASR_MARKER}जारी तीसरी खिड़की का अंत",
            ],
            sleeps=sleeps,
        )
        result = engine.transcribe(_audio(210.0), TranscriptionRequest(language="hi"))
        assert result.text == ("पहली खिड़की का पाठ यहाँ समाप्त दूसरी खिड़की जारी तीसरी खिड़की का अंत")
        # One request, one result; segments carry REAL window offsets and
        # their texts concatenate to exactly the final text (Phase 7 law).
        assert [(s.start_seconds, s.end_seconds) for s in result.segments] == [
            (0.0, 100.0),
            (95.0, 195.0),
            (190.0, 210.0),
        ]
        assert " ".join(s.text for s in result.segments) == result.text
        assert result.duration_seconds == 210.0
        assert sleeps == []  # no retries were needed

    def test_a_failing_chunk_is_retried_once_then_succeeds(self, stub_server: str) -> None:
        sleeps: list[float] = []
        engine = self._chunked_engine(
            stub_server,
            scripted=[
                f"language Hindi{ASR_MARKER}एक",
                "@fail",  # chunk 2, first attempt
                f"language Hindi{ASR_MARKER}दो",  # chunk 2, retry
                f"language Hindi{ASR_MARKER}तीन",
            ],
            sleeps=sleeps,
        )
        result = engine.transcribe(_audio(210.0), TranscriptionRequest(language="hi"))
        assert result.text == "एक दो तीन"
        assert sleeps == [qwen3_asr.CHUNK_RETRY_DELAY_SECONDS]

    def test_a_chunk_failing_twice_fails_the_whole_request(self, stub_server: str) -> None:
        sleeps: list[float] = []
        engine = self._chunked_engine(
            stub_server,
            scripted=[f"language Hindi{ASR_MARKER}एक", "@fail", "@fail"],
            sleeps=sleeps,
        )
        with pytest.raises(RuntimeServiceError) as excinfo:
            engine.transcribe(_audio(210.0), TranscriptionRequest(language="hi"))
        # The failure is the REQUEST's failure: no partial transcript
        # exists anywhere in the raised error, and the message names
        # neither chunks nor engines.
        assert "एक" not in excinfo.value.message
        lowered = excinfo.value.message.lower()
        for marker in ("chunk", "qwen", "llama", "window"):
            assert marker not in lowered
        assert "could not be completed" in excinfo.value.message

    def test_silent_windows_produce_no_empty_segments(self, stub_server: str) -> None:
        engine = self._chunked_engine(
            stub_server,
            scripted=[
                f"language Hindi{ASR_MARKER}बोला गया हिस्सा",
                f"language None{ASR_MARKER}",  # silent middle window
                f"language Hindi{ASR_MARKER}आख़िरी हिस्सा",
            ],
            sleeps=[],
        )
        result = engine.transcribe(_audio(210.0), TranscriptionRequest(language="hi"))
        assert result.text == "बोला गया हिस्सा आख़िरी हिस्सा"
        assert len(result.segments) == 2
        assert " ".join(s.text for s in result.segments) == result.text

    def test_over_ceiling_is_still_refused(self, stub_server: str) -> None:
        engine = self._chunked_engine(stub_server, scripted=[], sleeps=[])
        with pytest.raises(RuntimeServiceError) as excinfo:
            engine.transcribe(_audio(601.0), TranscriptionRequest(language="hi"))
        assert excinfo.value.error_type.value == "invalid_input"
        assert "600 seconds" in excinfo.value.message

    def test_the_final_window_failing_twice_fails_the_whole_request(self, stub_server: str) -> None:
        # Failure matrix case 6: the LAST window is not special — its
        # double failure voids the whole request exactly like any other
        # window's, and none of the earlier windows' text escapes.
        sleeps: list[float] = []
        engine = self._chunked_engine(
            stub_server,
            scripted=[
                f"language Hindi{ASR_MARKER}एक",
                f"language Hindi{ASR_MARKER}दो",
                "@fail",  # final window, first attempt
                "@fail",  # final window, retry
            ],
            sleeps=sleeps,
        )
        with pytest.raises(RuntimeServiceError) as excinfo:
            engine.transcribe(_audio(210.0), TranscriptionRequest(language="hi"))
        assert "एक" not in excinfo.value.message
        assert "दो" not in excinfo.value.message
        assert sleeps == [qwen3_asr.CHUNK_RETRY_DELAY_SECONDS]

    def test_a_mid_response_disconnect_stays_inside_the_retry_contract(
        self, stub_server: str
    ) -> None:
        # M19 staging drill finding: a child killed MID-RESPONSE raises a
        # RAW IncompleteRead/ConnectionResetError from response.read(),
        # which urllib does not wrap in URLError. Before the fix this
        # escaped the engine as a non-RuntimeServiceError and bypassed
        # the one-retry path entirely.
        sleeps: list[float] = []
        engine = self._chunked_engine(
            stub_server,
            scripted=[
                f"language Hindi{ASR_MARKER}एक",
                "@truncate",  # chunk 2 dies mid-body
                f"language Hindi{ASR_MARKER}दो",  # retry succeeds
                f"language Hindi{ASR_MARKER}तीन",
            ],
            sleeps=sleeps,
        )
        result = engine.transcribe(_audio(210.0), TranscriptionRequest(language="hi"))
        assert result.text == "एक दो तीन"
        assert sleeps == [qwen3_asr.CHUNK_RETRY_DELAY_SECONDS]

    def test_a_mid_response_disconnect_on_the_direct_path_is_a_clean_error(
        self, stub_server: str
    ) -> None:
        _StubHandler.script = ["@truncate"]
        with pytest.raises(RuntimeServiceError) as excinfo:
            _engine(stub_server).transcribe(_audio(2.0), TranscriptionRequest(language="hi"))
        assert excinfo.value.error_type.value == "internal"
        # The clean generic message — never the raw exception text.
        assert "did not answer" in excinfo.value.message


class TestSlotTruthfulReadiness:
    """Milestone 17 Phase 2: /health/ready tells per-slot truth."""

    @pytest.fixture
    def client(self) -> Any:
        from fastapi.testclient import TestClient

        from intelliai_stt_runtime.config import Settings
        from intelliai_stt_runtime.main import create_app

        # Two weightless slots: `default` (the deployment's core promise)
        # and a named specialist — the exact shape of the canary topology.
        app = create_app(Settings(slots="reference,reference:specialist-b"))
        with TestClient(app) as test_client:
            yield test_client

    @staticmethod
    def _engine_of(client: Any, slot: str) -> Any:
        manager = client.app.state.manager
        for loaded in manager.loaded_models():
            if loaded.slot == slot:
                return loaded.engine
        raise AssertionError(f"slot {slot!r} not loaded")

    def test_both_healthy_reads_ready(self, client: Any) -> None:
        response = client.get("/health/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        assert set(body["slots"].values()) == {"ready"}

    def test_dead_specialist_degrades_but_never_kills_the_service(self, client: Any) -> None:
        engine = self._engine_of(client, "specialist-b")
        engine.slot_state = lambda: "restarting"
        response = client.get("/health/ready")
        # 200: an orchestrator polling this must NOT restart a process
        # that is still serving its default slot.
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "degraded"
        assert body["slots"]["specialist-b"] == "restarting"

    def test_failed_specialist_is_visible_by_name(self, client: Any) -> None:
        engine = self._engine_of(client, "specialist-b")
        engine.slot_state = lambda: "failed"
        body = client.get("/health/ready").json()
        assert body["status"] == "degraded"
        assert body["slots"]["specialist-b"] == "failed"

    def test_dead_default_slot_makes_the_service_not_ready(self, client: Any) -> None:
        engine = self._engine_of(client, "default")
        engine.slot_state = lambda: "failed"
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"

    def test_unstarted_manager_is_not_ready(self) -> None:
        from fastapi.testclient import TestClient

        from intelliai_stt_runtime.config import Settings
        from intelliai_stt_runtime.main import create_app

        app = create_app(Settings(slots="reference"))
        # No lifespan entered: models never loaded.
        client = TestClient(app)
        assert client.get("/health/ready").status_code == 503
