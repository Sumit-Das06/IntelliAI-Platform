"""M53 realtime sessions: the protocol laws, provable without models.

Fake engines and a fake WebSocket drive the REAL session state machine:
event ordering, monotonic sequences, VAD gating (silence never decodes),
skip-to-latest scheduling, VAD-aligned off-path commits, the
finality-capture race, degraded/error paths, and idempotent stop. Real
engines are exercised by the M53 staging battery, not by unit tests.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING, Any, cast

import numpy as np
import pytest

from intelliai_runtime_contract import TranscriptionResult
from intelliai_stt_runtime.config import Settings

if TYPE_CHECKING:
    from fastapi import WebSocket

from intelliai_stt_runtime.realtime import (
    CLOSE_BAD_REQUEST,
    CLOSE_UNAVAILABLE,
    RealtimeConfig,
    RealtimeService,
    RealtimeSession,
    run_realtime_endpoint,
)

SAMPLE_RATE = 16_000


def _pcm_frames(seconds: float, *, speech: bool, frame_ms: int = 100) -> list[bytes]:
    total = int(seconds * SAMPLE_RATE)
    if speech:
        t = np.arange(total, dtype=np.float32)
        wave = (0.3 * np.sin(2 * np.pi * 220.0 * t / SAMPLE_RATE)).astype(np.float32)
    else:
        wave = np.zeros(total, dtype=np.float32)
    pcm = (wave * 32767.0).astype(np.int16).tobytes()
    step = SAMPLE_RATE * 2 * frame_ms // 1000
    return [pcm[i : i + step] for i in range(0, len(pcm), step)]


class FakeWS:
    """Just enough Starlette WebSocket surface for the session."""

    def __init__(self, script: list[Any]) -> None:
        self.queue: asyncio.Queue[Any] = asyncio.Queue()
        for item in script:
            self.queue.put_nowait(item)
        self.sent: list[dict[str, Any]] = []
        self.closed: int | None = None
        self.accepted = False

    def feed(self, item: Any) -> None:
        self.queue.put_nowait(item)

    async def accept(self) -> None:
        self.accepted = True

    async def receive_text(self) -> str:
        message = await self.queue.get()
        return str(message["text"])

    async def receive(self) -> dict[str, Any]:
        return dict(await self.queue.get())

    async def send_text(self, payload: str) -> None:
        self.sent.append(json.loads(payload))

    async def close(self, code: int = 1000) -> None:
        self.closed = code

    def events(self, name: str) -> list[dict[str, Any]]:
        return [event for event in self.sent if event["event"] == name]


class FakeEngine:
    """Deterministic decode: N words for N half-seconds of audio."""

    def __init__(self, *, delay: float = 0.0, fail: bool = False) -> None:
        self.calls: list[dict[str, Any]] = []
        self.delay = delay
        self.fail = fail

    def decode(self, audio: np.ndarray, *, final: bool) -> str:
        self.calls.append({"seconds": len(audio) / SAMPLE_RATE, "final": final})
        if self.delay:
            time.sleep(self.delay)
        if self.fail:
            msg = "backend down"
            raise RuntimeError(msg)
        words = max(1, int(len(audio) / SAMPLE_RATE * 2))
        return " ".join(f"w{i}" for i in range(words))

    def close(self) -> None:
        pass


def _service(engine: FakeEngine | None, **config: float) -> RealtimeService:
    return RealtimeService(
        config=RealtimeConfig(
            languages=frozenset({"en", "en-us", "en-in", "hi", "hi-in"}),
            **config,
        ),
        whisper=engine,
        qwen=None,
    )


def _script(seconds: float, *, speech: bool, end: bool = True) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = [
        {"type": "websocket.receive", "bytes": frame}
        for frame in _pcm_frames(seconds, speech=speech)
    ]
    if end:
        frames.append({"type": "websocket.receive", "text": json.dumps({"event": "end"})})
    return frames


def _run(ws: FakeWS, service: RealtimeService, language: str = "en") -> None:
    session = RealtimeSession(
        cast("WebSocket", ws), service, language=language, punctuator=None, punctuator_en=None
    )
    asyncio.run(asyncio.wait_for(session.run(), timeout=20))


def _run_paced(
    frames: list[dict[str, Any]],
    service: RealtimeService,
    *,
    interval: float = 0.03,
    language: str = "en",
) -> FakeWS:
    """Feed messages at a mic-like pace so partial passes actually happen
    (a pre-loaded queue is drained whole before the first decode)."""
    ws = FakeWS([])

    async def scenario() -> None:
        session = RealtimeSession(
            cast("WebSocket", ws), service, language=language, punctuator=None, punctuator_en=None
        )
        task = asyncio.create_task(session.run())

        async def feeder() -> None:
            for frame in frames:
                ws.feed(frame)
                await asyncio.sleep(interval)

        await feeder()
        await asyncio.wait_for(task, timeout=30)

    asyncio.run(scenario())
    return ws


# ── configuration ────────────────────────────────────────────────────────


class TestConfiguration:
    def test_the_flag_defaults_off(self) -> None:
        settings = Settings()
        assert settings.realtime_enabled is False
        assert settings.realtime_qwen_url == ""
        assert settings.realtime_whisper_device == "cpu"

    def test_off_means_no_service_and_disabled_readiness(self) -> None:
        from fastapi.testclient import TestClient

        from intelliai_stt_runtime.main import create_app

        app = create_app(Settings(console_logs=True, max_concurrency=1, max_queue=1))
        with TestClient(app) as client:
            assert app.state.realtime is None
            assert client.get("/health/ready").json()["realtime"] == "disabled"


# ── handshake ────────────────────────────────────────────────────────────


class TestHandshake:
    def test_disabled_service_refuses_before_accepting_audio(self) -> None:
        ws = FakeWS([])
        asyncio.run(
            run_realtime_endpoint(
                cast("WebSocket", ws), service=None, punctuator=None, punctuator_en=None
            )
        )
        assert ws.closed == CLOSE_UNAVAILABLE
        assert ws.sent == []

    def test_bad_start_and_unsupported_language_refuse(self) -> None:
        for first in (
            {"text": "not json"},
            {"text": json.dumps({"event": "start", "language": "fr"})},
            {"text": json.dumps({"event": "hello", "language": "en"})},
        ):
            ws = FakeWS([first])
            asyncio.run(
                run_realtime_endpoint(
                    cast("WebSocket", ws),
                    service=_service(FakeEngine()),
                    punctuator=None,
                    punctuator_en=None,
                )
            )
            assert ws.closed == CLOSE_BAD_REQUEST

    def test_language_without_backend_refuses_honestly(self) -> None:
        # hi is policy-allowed but this deployment has no qwen backend:
        # refuse — never silently route Hindi to the English model.
        ws = FakeWS([{"text": json.dumps({"event": "start", "language": "hi"})}])
        asyncio.run(
            run_realtime_endpoint(
                cast("WebSocket", ws),
                service=_service(FakeEngine()),
                punctuator=None,
                punctuator_en=None,
            )
        )
        assert ws.closed == CLOSE_UNAVAILABLE


# ── the session laws ─────────────────────────────────────────────────────


class TestSession:
    def test_full_session_orders_events_and_sequences(self) -> None:
        engine = FakeEngine()
        ws = _run_paced(_script(2.0, speech=True), _service(engine))
        names = [event["event"] for event in ws.sent]
        assert names[0] == "session.started"
        assert names[-2:] == ["transcript.final", "session.completed"]
        partials = ws.events("transcript.partial")
        final = ws.events("transcript.final")[0]
        assert partials, "expected at least one partial"
        sequences = [event["sequence"] for event in [*partials, final]]
        assert sequences == sorted(sequences)
        assert len(set(sequences)) == len(sequences)
        assert final["is_final"] is True
        assert final["language"] == "en"
        assert final["duration_seconds"] == pytest.approx(2.0, abs=0.2)
        assert all(event["session_id"] == final["session_id"] for event in ws.sent)
        assert ws.closed is not None

    def test_silence_never_reaches_the_engine(self) -> None:
        engine = FakeEngine()
        ws = FakeWS(_script(2.0, speech=False))
        _run(ws, _service(engine))
        assert engine.calls == []  # the M52 silence law: zero inference
        final = ws.events("transcript.final")[0]
        assert final["text"] == ""
        assert ws.events("session.completed")

    def test_skip_to_latest_never_decodes_stale_windows(self) -> None:
        # A slow engine with 6 s of audio: naive per-step decoding would
        # run ~12 decodes; skip-to-latest coalesces the backlog and the
        # LAST decode must still cover the full buffer.
        engine = FakeEngine(delay=0.3)
        ws = FakeWS(_script(6.0, speech=True))
        _run(ws, _service(engine))
        assert len(engine.calls) <= 6
        assert engine.calls[-1]["seconds"] == pytest.approx(6.0, abs=0.1)
        assert engine.calls[-1]["final"] is True

    def test_finality_is_captured_at_decode_start(self) -> None:
        # The M52 race: `end` lands while a partial decode is in flight.
        # That in-flight decode must stay a PARTIAL; the final decode
        # afterwards covers the complete buffer.
        engine = FakeEngine(delay=0.2)
        ws = FakeWS(_script(1.5, speech=True, end=False))

        async def scenario() -> None:
            session = RealtimeSession(
                cast("WebSocket", ws),
                _service(engine),
                language="en",
                punctuator=None,
                punctuator_en=None,
            )
            task = asyncio.create_task(session.run())
            await asyncio.sleep(0.6)  # a partial decode is now in flight
            ws.feed({"type": "websocket.receive", "text": json.dumps({"event": "end"})})
            await asyncio.wait_for(task, timeout=20)

        asyncio.run(scenario())
        finals = ws.events("transcript.final")
        assert len(finals) == 1
        assert finals[0]["duration_seconds"] == pytest.approx(1.5, abs=0.2)
        final_calls = [call for call in engine.calls if call["final"]]
        assert len(final_calls) == 1

    def test_vad_aligned_commit_runs_off_the_hot_path(self) -> None:
        # 5 s window cap + speech with a silent gap: the session must
        # commit at a VAD boundary via a final-quality decode of ONLY the
        # committed span, then keep partials flowing from the cut.
        engine = FakeEngine()
        frames = [
            {"type": "websocket.receive", "bytes": frame}
            for frame in (
                _pcm_frames(4.0, speech=True)
                + _pcm_frames(1.0, speech=False)
                + _pcm_frames(4.0, speech=True)
            )
        ]
        frames.append({"type": "websocket.receive", "text": json.dumps({"event": "end"})})
        ws = _run_paced(
            frames,
            _service(engine, max_window_seconds=5.0, commit_margin_seconds=1.0),
            interval=0.02,
        )
        commit_calls = [call for call in engine.calls if call["final"] and call["seconds"] < 8.0]
        assert commit_calls, "expected an off-path commit decode of a partial span"
        # The commit span must end INSIDE the silent gap (4.0-5.0 s):
        assert 3.5 <= commit_calls[0]["seconds"] <= 5.2
        final = ws.events("transcript.final")[0]
        assert final["duration_seconds"] == pytest.approx(9.0, abs=0.3)

    def test_backpressure_degrades_loudly_never_silently(self) -> None:
        engine = FakeEngine(delay=0.4)
        ws = FakeWS(_script(4.0, speech=True))
        _run(ws, _service(engine, max_buffer_seconds=1.0))
        assert len(ws.events("session.degraded")) == 1
        assert ws.events("session.completed"), "the session still finishes completely"

    def test_session_length_is_bounded(self) -> None:
        engine = FakeEngine()
        ws = FakeWS(_script(3.0, speech=True, end=False))
        _run(ws, _service(engine, max_session_seconds=2.0))
        errors = ws.events("session.error")
        assert errors and errors[0]["code"] == "session_too_long"
        assert ws.closed == CLOSE_BAD_REQUEST

    def test_engine_failure_is_an_explicit_error_never_a_fake_final(self) -> None:
        engine = FakeEngine(fail=True)
        ws = FakeWS(_script(3.5, speech=True))
        _run(ws, _service(engine))
        errors = ws.events("session.error")
        assert errors and errors[0]["code"] == "transcription_unavailable"
        assert not ws.events("transcript.final")
        assert ws.closed == 1011

    def test_stop_is_idempotent(self) -> None:
        engine = FakeEngine()
        frames = _script(1.0, speech=True)
        frames.append({"type": "websocket.receive", "text": json.dumps({"event": "end"})})
        ws = FakeWS(frames)
        _run(ws, _service(engine))
        assert len(ws.events("transcript.final")) == 1
        assert len(ws.events("session.completed")) == 1

    def test_disconnect_kills_the_session_without_stale_output(self) -> None:
        engine = FakeEngine()
        frames = [
            {"type": "websocket.receive", "bytes": frame} for frame in _pcm_frames(1.0, speech=True)
        ]
        frames.append({"type": "websocket.disconnect"})
        ws = FakeWS(frames)
        _run(ws, _service(engine))
        assert not ws.events("transcript.final")
        assert not ws.events("session.completed")

    def test_two_sessions_never_share_identity(self) -> None:
        engine = FakeEngine()
        ids = []
        for _ in range(2):
            ws = FakeWS(_script(1.0, speech=True))
            _run(ws, _service(engine))
            ids.append(ws.sent[0]["session_id"])
        assert ids[0] != ids[1]


# ── finalization through the EXISTING punctuation stages ────────────────


class _StubStage:
    """restore_safely-compatible stub: appends a period, preserves raw."""

    def __init__(self) -> None:
        self.calls = 0

    def restore_safely(self, result: TranscriptionResult, language: str | None) -> Any:
        self.calls += 1
        del language
        from types import SimpleNamespace

        return SimpleNamespace(
            result=TranscriptionResult(
                text=result.text + ".",
                language=result.language,
                duration_seconds=result.duration_seconds,
                segments=result.segments,
                raw_text=result.text,
            )
        )


class TestFinalization:
    def test_punctuation_runs_on_the_final_only(self) -> None:
        engine = FakeEngine()
        stage = _StubStage()
        ws = FakeWS(_script(2.0, speech=True))
        session = RealtimeSession(
            cast("WebSocket", ws),
            _service(engine),
            language="en",
            punctuator=None,
            punctuator_en=cast(Any, stage),
        )
        asyncio.run(asyncio.wait_for(session.run(), timeout=20))
        final = ws.events("transcript.final")[0]
        assert stage.calls == 1  # never per-partial
        assert final["text"].endswith(".")
        assert final["raw_text"] == final["text"][:-1]
        for partial in ws.events("transcript.partial"):
            assert not partial["text"].endswith(".")


# ── routing ──────────────────────────────────────────────────────────────


class TestRouting:
    def test_language_to_engine_mapping(self) -> None:
        whisper, qwen = FakeEngine(), FakeEngine()
        service = RealtimeService(
            config=RealtimeConfig(languages=frozenset({"en", "hi"})),
            whisper=whisper,
            qwen=qwen,
        )
        assert service.engine_for("en") is whisper
        assert service.engine_for("en-US") is whisper
        assert service.engine_for("en-IN") is whisper
        assert service.engine_for("hi") is qwen
        assert service.engine_for("hi-IN") is qwen
        assert service.engine_for("auto") is None
        assert service.engine_for("ar") is None
        service.close()
