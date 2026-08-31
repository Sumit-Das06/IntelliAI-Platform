"""Realtime STT sessions (Milestone 53) — the M52/M52H architecture,
productized behind a flag that defaults OFF everywhere.

One WebSocket session = one microphone stream:

    client → {"event": "start", "language": "en"}
    client → binary frames: PCM16 mono 16 kHz (100 ms framing preferred)
    client → {"event": "end"}
    server → session.started {session_id}
    server → transcript.partial {session_id, sequence, text, is_final: false}
    server → transcript.final   {session_id, sequence, text, raw_text,
                                 language, duration_seconds, is_final: true}
    server → session.completed  {session_id, audio_seconds}
    server → session.degraded / session.error (loud, never silent)

The measured laws this module encodes:

* every decode is VAD-gated (M52: the bare models hallucinate on
  silence; EnergyVad suppresses it) — silence costs zero inference;
* rolling window with VAD-ALIGNED commits (M52H: seam WER penalty
  0/+0.7/+2.1 pt on 2/5/10 min real speech) — commit decodes run OFF
  the hot path on their own executor;
* skip-to-latest scheduling (M52H): the hot loop always decodes the
  NEWEST window; stale intermediate windows are never processed;
* ``is_final`` is captured at decode start — a partial can never be
  mislabeled final by an ``end`` arriving mid-decode (M52 race, fixed);
* partials are EPHEMERAL: nothing here persists anything; the gateway
  owns collection/consent for exactly ONE final sample, like batch.

Authentication note: this endpoint carries the same posture as
``/v1/transcribe`` — the runtime is an internal, loopback/compose-network
service and the GATEWAY is the authentication boundary. The public
WebSocket lives on the gateway, which authenticates BEFORE opening a
runtime session (see the apps/api realtime route).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import secrets
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

import numpy as np
import structlog

from intelliai_runtime_contract import TranscriptionResult, TranscriptionSegment
from intelliai_stt_runtime.engines.realtime_backends import (
    SAMPLE_RATE,
    QwenRealtime,
    RealtimeEngine,
    WhisperRealtime,
)
from intelliai_stt_runtime.pipeline.audio import DecodedAudio
from intelliai_stt_runtime.pipeline.vad import EnergyVad, SpeechAnalysis

if TYPE_CHECKING:
    from pathlib import Path

    from fastapi import WebSocket

    from intelliai_stt_runtime.engines.punctuation import PunctuationRestorer
    from intelliai_stt_runtime.engines.punctuation_en import EnPunctuationRestorer

logger = structlog.get_logger(__name__)

#: WebSocket close codes: session-protocol outcomes.
CLOSE_UNAVAILABLE: Final = 4404  # realtime disabled / backend not configured
CLOSE_BAD_REQUEST: Final = 4400  # protocol or language violation

_ENGLISH: Final = frozenset({"en", "en-us", "en-in"})
_HINDI: Final = frozenset({"hi", "hi-in"})


@dataclass(frozen=True)
class RealtimeConfig:
    languages: frozenset[str]
    min_step_seconds: float = 0.5
    #: M54: the FIRST decode may run on less audio than the steady-state
    #: step — first-partial time is user-perceived responsiveness, and a
    #: 0.3 s opening window is cheap.
    first_step_seconds: float = 0.3
    max_window_seconds: float = 25.0
    commit_margin_seconds: float = 5.0
    max_buffer_seconds: float = 60.0
    max_session_seconds: float = 900.0
    #: M54 finalization fast path: when the audio after the last hot
    #: decode is silence, the final reuses that decode instead of
    #: re-decoding the whole window. Independently rollback-able.
    final_fast_path: bool = True


# ── repetition guard (M54) ───────────────────────────────────────────────


@dataclass(frozen=True)
class RepetitionDiagnosis:
    """Verdict on one decoded span: pathological decoder repetition vs
    legitimate repeated speech ("हाँ हाँ, बिल्कुल" is a run of 2 and
    NEVER trips this)."""

    pathological: bool
    ngram: int = 0
    run_length: int = 0
    trimmed_text: str = ""
    removed_words: int = 0
    #: The repeated block itself (space-joined) — merge seams collapse
    #: further runs of THIS block so trimmed spans can't re-assemble a
    #: loop across commit boundaries.
    block: str = ""


#: A block repeated this many times consecutively is decoder pathology —
#: real speech repeats words 2-3 times; loops repeat dozens.
_REPEAT_RUN_LIMIT: Final = 6
#: Real Hindi/English speech in our corpora runs ~2-4 words/second; a
#: span decoding to more than this is loop-shaped even at shorter runs.
_SUSPECT_WORDS_PER_SECOND: Final = 6.0
_SUSPECT_RUN_LIMIT: Final = 4


def diagnose_repetition(text: str, span_seconds: float) -> RepetitionDiagnosis:
    """Detect runaway decoder repetition in one span's text.

    Checks consecutive identical n-gram blocks (n=1..4). Trimming keeps
    the FIRST TWO occurrences of the runaway block and everything
    around it — legitimate text is never deleted."""
    words = text.split()
    if len(words) < _SUSPECT_RUN_LIMIT:
        return RepetitionDiagnosis(pathological=False)
    dense = len(words) / max(span_seconds, 0.1) > _SUSPECT_WORDS_PER_SECOND
    best_n, best_run, best_at = 0, 1, 0
    for n in (1, 2, 3, 4):
        run, run_start = 1, 0
        for i in range(n, len(words) - n + 1, n):
            if words[i : i + n] == words[i - n : i]:
                run += 1
            else:
                if run > best_run:
                    best_n, best_run, best_at = n, run, run_start
                run, run_start = 1, i
        if run > best_run:
            best_n, best_run, best_at = n, run, run_start
    limit = _SUSPECT_RUN_LIMIT if dense else _REPEAT_RUN_LIMIT
    if best_run < limit:
        return RepetitionDiagnosis(pathological=False)
    keep_until = best_at + 2 * best_n
    resume_from = best_at + best_run * best_n
    trimmed = words[:keep_until] + words[resume_from:]
    return RepetitionDiagnosis(
        pathological=True,
        ngram=best_n,
        run_length=best_run,
        trimmed_text=" ".join(trimmed),
        removed_words=len(words) - len(trimmed),
        block=" ".join(words[best_at : best_at + best_n]),
    )


def collapse_block_runs(text: str, block: str, *, keep: int = 2) -> str:
    """Collapse consecutive repeats of one known-pathological block to
    ``keep`` occurrences — the seam half of the guard: two trimmed spans
    ("बस बस" + "बस बस") must not re-assemble a longer loop."""
    block_words = block.split()
    if not block_words:
        return text
    words = text.split()
    n = len(block_words)
    out: list[str] = []
    run = 0
    i = 0
    while i < len(words):
        if words[i : i + n] == block_words:
            run += 1
            if run <= keep:
                out.extend(block_words)
            i += n
        else:
            run = 0
            out.append(words[i])
            i += 1
    return " ".join(out)


class RealtimeService:
    """Process-wide realtime state: engines load once, sessions are cheap."""

    def __init__(
        self,
        *,
        config: RealtimeConfig,
        whisper: RealtimeEngine | None,
        qwen: RealtimeEngine | None,
    ) -> None:
        self.config = config
        self._whisper = whisper
        self._qwen = qwen
        # Hot path and commit path are SEPARATE single workers: commits
        # must never delay the next partial (the M52H scheduling law),
        # and one decode at a time per lane keeps GPU behavior
        # predictable under concurrent sessions.
        self.hot_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rt-hot")
        self.commit_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rt-commit")
        self._probe_at = -1e9
        self._probe_verdict = "ready"

    def health(self) -> str:
        """``ready`` | ``degraded`` — degraded when a configured NETWORK
        backend stopped answering (the in-process engine cannot vanish
        silently). Probes are cached so readiness stays cheap."""
        qwen = self._qwen
        probe = getattr(qwen, "probe", None)
        if probe is None:
            return "ready"
        now = time.monotonic()
        if now - self._probe_at < 15.0:
            return self._probe_verdict
        self._probe_at = now
        try:
            probe()
            self._probe_verdict = "ready"
        except Exception:
            logger.warning("realtime_backend_degraded")
            self._probe_verdict = "degraded"
        return self._probe_verdict

    def engine_for(self, language: str) -> RealtimeEngine | None:
        tag = language.strip().casefold()
        if tag in _ENGLISH:
            return self._whisper
        if tag in _HINDI:
            return self._qwen
        return None

    def supports(self, language: str) -> bool:
        return language.strip().casefold() in self.config.languages

    def close(self) -> None:
        self.hot_executor.shutdown(wait=False, cancel_futures=True)
        self.commit_executor.shutdown(wait=False, cancel_futures=True)
        for engine in (self._whisper, self._qwen):
            if engine is not None:
                engine.close()


def build_realtime_service(settings: object, model_dir: Path) -> RealtimeService:
    """Build from runtime Settings. Heavy engine imports happen only here,
    only when the flag is ON — a disabled deployment pays nothing."""
    languages = frozenset(
        tag.strip().casefold()
        for tag in str(getattr(settings, "realtime_languages", "")).split(",")
        if tag.strip()
    )
    whisper: RealtimeEngine | None = None
    if languages & _ENGLISH:
        from intelliai_runtime_core import ArtifactStore
        from intelliai_stt_runtime.engines.whisper import WHISPER_SMALL_FILES

        local_dir = ArtifactStore(model_dir).ensure(WHISPER_SMALL_FILES)
        whisper = WhisperRealtime(
            local_dir,
            device=str(getattr(settings, "realtime_whisper_device", "cpu")),
            compute_type=str(getattr(settings, "realtime_whisper_compute_type", "")),
        )
        # Warm-up decode at STARTUP (the ADR-0019 law): a misconfigured
        # device fails the deploy loudly here, never a customer session.
        whisper.decode(np.zeros(SAMPLE_RATE // 2, dtype=np.float32), final=False)
    qwen: RealtimeEngine | None = None
    qwen_url = str(getattr(settings, "realtime_qwen_url", "")).strip()
    if (languages & _HINDI) and qwen_url:
        backend = QwenRealtime(qwen_url)
        backend.probe()  # enabled + unreachable = refuse startup, loudly
        qwen = backend
    config = RealtimeConfig(
        languages=languages,
        min_step_seconds=float(getattr(settings, "realtime_min_step_seconds", 0.5)),
        first_step_seconds=float(getattr(settings, "realtime_first_step_seconds", 0.3)),
        max_window_seconds=float(getattr(settings, "realtime_max_window_seconds", 25.0)),
        commit_margin_seconds=float(getattr(settings, "realtime_commit_margin_seconds", 5.0)),
        max_buffer_seconds=float(getattr(settings, "realtime_max_buffer_seconds", 60.0)),
        max_session_seconds=float(getattr(settings, "realtime_max_session_seconds", 900.0)),
        final_fast_path=bool(getattr(settings, "realtime_final_fast_path", True)),
    )
    return RealtimeService(config=config, whisper=whisper, qwen=qwen)


# ── the session ──────────────────────────────────────────────────────────


@dataclass
class _SessionState:
    chunks: list[np.ndarray] = field(default_factory=list)
    committed: str = ""
    window_start: float = 0.0
    decoded_to: float = 0.0
    sequence: int = 0
    ended: bool = False
    gone: bool = False
    degraded: bool = False
    commit_pending: bool = False
    #: Last successful hot decode: (window_start it ran from, audio
    #: position it covered, decoded text) — the finalization fast path.
    last_hot: tuple[float, float, str] | None = None


@dataclass
class _SessionMetrics:
    """Internal-only per-session telemetry (M54 observability). Logged
    as a structured summary at completion; never sent to clients."""

    hot_queue_ms: list[float] = field(default_factory=list)
    hot_decode_ms: list[float] = field(default_factory=list)
    commit_count: int = 0
    repetition_detected: int = 0
    repetition_retries: int = 0
    trimmed_words: int = 0
    fast_path_final: bool = False
    punctuation_ms: float = 0.0

    def summary(self) -> dict[str, object]:
        def stats(values: list[float]) -> dict[str, float]:
            if not values:
                return {}
            ordered = sorted(values)
            return {
                "p50_ms": round(statistics.median(ordered), 1),
                "p95_ms": round(ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))], 1),
                "max_ms": round(ordered[-1], 1),
            }

        return {
            "hot_queue": stats(self.hot_queue_ms),
            "hot_decode": stats(self.hot_decode_ms),
            "commit_count": self.commit_count,
            "repetition_detected": self.repetition_detected,
            "repetition_retries": self.repetition_retries,
            "trimmed_words": self.trimmed_words,
            "fast_path_final": self.fast_path_final,
            "punctuation_ms": round(self.punctuation_ms, 1),
        }


class RealtimeSession:
    """One connection's state machine. See the module docstring for laws."""

    def __init__(
        self,
        websocket: WebSocket,
        service: RealtimeService,
        *,
        language: str,
        punctuator: PunctuationRestorer | None,
        punctuator_en: EnPunctuationRestorer | None,
        vad: EnergyVad | None = None,
    ) -> None:
        self.ws = websocket
        self.service = service
        self.language = language
        self.session_id = secrets.token_hex(8)
        self._vad = vad or EnergyVad()
        self._punctuator = punctuator
        self._punctuator_en = punctuator_en
        self._state = _SessionState()
        self._metrics = _SessionMetrics()
        self._engine = service.engine_for(language)
        #: Once a loop block is flagged, every text assembly collapses
        #: runs of that block — trimmed spans must not re-assemble a
        #: loop across seams.
        self._guard_block = ""

    # -- helpers -----------------------------------------------------------

    async def _emit(self, event: str, **fields: object) -> None:
        await self.ws.send_text(
            json.dumps(
                {"event": event, "session_id": self.session_id, **fields}, ensure_ascii=False
            )
        )

    def _buffer(self) -> np.ndarray:
        state = self._state
        return np.concatenate(state.chunks) if state.chunks else np.zeros(0, dtype=np.float32)

    def _analysis(self, audio: np.ndarray) -> SpeechAnalysis:
        pcm = (audio * 32768.0).clip(-32768, 32767).astype("int16").tobytes()
        return self._vad.analyze(
            DecodedAudio(
                pcm=pcm,
                sample_rate_hz=SAMPLE_RATE,
                duration_seconds=len(audio) / SAMPLE_RATE,
                channels=1,
                sample_width_bytes=2,
            )
        )

    def _finalize_text(self, raw: str, duration_seconds: float) -> tuple[str, str]:
        """The EXISTING punctuation stages, final-only (the M53 law):
        returns (served_text, raw_text) with batch-identical semantics —
        including the M51 engine-already-punctuated stand-down."""
        if not raw:
            return "", ""
        result = TranscriptionResult(
            text=raw,
            language=self.language.split("-")[0].casefold() or "und",
            duration_seconds=max(duration_seconds, 0.0),
            segments=(
                TranscriptionSegment(
                    start_seconds=0.0, end_seconds=max(duration_seconds, 0.01), text=raw
                ),
            ),
        )
        punct_started = time.perf_counter()
        for stage in (self._punctuator, self._punctuator_en):
            if stage is None:
                continue
            outcome = stage.restore_safely(result, self.language)
            result = outcome.result
        self._metrics.punctuation_ms = (time.perf_counter() - punct_started) * 1000.0
        return result.text, result.raw_text if result.raw_text is not None else raw

    async def _emit_final(self, raw: str, available: float) -> None:
        state = self._state
        state.sequence += 1
        served, raw_text = await asyncio.to_thread(self._finalize_text, raw, available)
        await self._emit(
            "transcript.final",
            sequence=state.sequence,
            text=served,
            raw_text=raw_text,
            language=self.language,
            duration_seconds=round(available, 3),
            is_final=True,
        )

    async def _land_commit(
        self, landed: tuple[str, float], loop: asyncio.AbstractEventLoop
    ) -> None:
        """Merge one finished commit decode — with the M54 repetition
        guard: detect → retry once (the service path CAN be
        nondeterministic under load) → trim the runaway run to two
        occurrences. Legitimate repeated speech is never touched, and
        nothing is ever removed silently."""
        state, metrics = self._state, self._metrics
        committed_text, cut = landed
        span_seconds = max(cut - state.window_start, 0.1)
        diagnosis = diagnose_repetition(committed_text, span_seconds)
        if diagnosis.pathological:
            metrics.repetition_detected += 1
            logger.warning(
                "realtime_repetition_detected",
                lane="commit",
                session=self.session_id,
                ngram=diagnosis.ngram,
                run_length=diagnosis.run_length,
                words=len(committed_text.split()),
                span_seconds=round(span_seconds, 1),
            )
            engine = self._engine
            span = self._buffer()[int(state.window_start * SAMPLE_RATE) : int(cut * SAMPLE_RATE)]
            retried: str | None = None
            if engine is not None and len(span):
                metrics.repetition_retries += 1

                def retry_decode(a: np.ndarray = span) -> str:
                    return engine.decode(a, final=True)

                with contextlib.suppress(Exception):
                    retried = await loop.run_in_executor(self.service.commit_executor, retry_decode)
            if retried is not None:
                rediagnosis = diagnose_repetition(retried, span_seconds)
                if rediagnosis.pathological:
                    metrics.trimmed_words += rediagnosis.removed_words
                    logger.warning(
                        "realtime_repetition_trimmed",
                        session=self.session_id,
                        removed_words=rediagnosis.removed_words,
                    )
                    committed_text = rediagnosis.trimmed_text
                    self._guard_block = rediagnosis.block
                else:
                    committed_text = retried
            else:
                metrics.trimmed_words += diagnosis.removed_words
                logger.warning(
                    "realtime_repetition_trimmed",
                    session=self.session_id,
                    removed_words=diagnosis.removed_words,
                )
                committed_text = diagnosis.trimmed_text
                self._guard_block = diagnosis.block
        merged = (state.committed + " " + committed_text).strip()
        if self._guard_block:
            merged = collapse_block_runs(merged, self._guard_block)
        state.committed = merged
        state.window_start = cut
        state.commit_pending = False
        metrics.commit_count += 1

    # -- the loop ----------------------------------------------------------

    async def run(self) -> None:
        state = self._state
        config = self.service.config
        loop = asyncio.get_running_loop()
        engine = self._engine
        await self._emit("session.started")

        async def receiver() -> None:
            try:
                while not state.ended:
                    message = await self.ws.receive()
                    if message.get("type") == "websocket.disconnect":
                        state.gone = True
                        return
                    if (data := message.get("bytes")) is not None:
                        frame = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                        state.chunks.append(frame)
                    elif (text := message.get("text")) is not None:
                        with contextlib.suppress(json.JSONDecodeError):
                            if json.loads(text).get("event") == "end":
                                state.ended = True
            except Exception:
                state.gone = True

        receiver_task = asyncio.create_task(receiver())
        commit_future: asyncio.Future[tuple[str, float]] | None = None
        decode_failures = 0
        try:
            while True:
                if state.gone:
                    return  # client vanished: the session dies with it
                buffer = self._buffer()
                available = len(buffer) / SAMPLE_RATE

                if available > config.max_session_seconds:
                    await self._emit(
                        "session.error",
                        code="session_too_long",
                        message="This realtime session reached its maximum length.",
                    )
                    await self.ws.close(code=CLOSE_BAD_REQUEST)
                    return
                if available - state.decoded_to > config.max_buffer_seconds and not state.degraded:
                    state.degraded = True
                    await self._emit(
                        "session.degraded",
                        reason="audio is arriving faster than realtime processing; "
                        "transcription continues, lagged",
                    )

                # Land a finished off-path commit before the next decode.
                if commit_future is not None and commit_future.done():
                    await self._land_commit(commit_future.result(), loop)
                    commit_future = None

                # `ended` can flip DURING a decode (the executor await
                # yields to the receiver): finality is captured NOW.
                is_final_pass = state.ended
                if is_final_pass and commit_future is not None:
                    # An in-flight commit is already computing on the GPU.
                    # Discarding it forced the final to re-decode that whole
                    # span again — the measured EN ~4 s finalization outlier
                    # (M53). Land it, then final-decode only the remainder.
                    with contextlib.suppress(Exception):
                        await asyncio.wait_for(asyncio.shield(commit_future), timeout=30.0)
                    if commit_future.done() and commit_future.exception() is None:
                        await self._land_commit(commit_future.result(), loop)
                    commit_future = None
                    buffer = self._buffer()
                    available = len(buffer) / SAMPLE_RATE
                # M54 MEASURED: the Hindi backend produces words from a
                # 300 ms opening window (client FPT 0.33-0.41 s vs
                # 0.64-1.06 s baseline); whisper-small returns EMPTY on
                # windows that short, so an early first decode only
                # wastes the lane and WORSENS English FPT. The early
                # first step is therefore Hindi-only.
                first_step = (
                    min(config.first_step_seconds, config.min_step_seconds)
                    if self.language.strip().casefold() in _HINDI
                    else config.min_step_seconds
                )
                step = config.min_step_seconds if state.decoded_to > 0 else first_step
                if is_final_pass or (available - state.decoded_to >= step):
                    window = buffer[int(state.window_start * SAMPLE_RATE) :]
                    # Skip-to-latest: whatever arrived while the previous
                    # decode ran is covered by THIS window; stale
                    # intermediate windows are never processed.
                    state.decoded_to = available
                    analysis = self._analysis(window) if len(window) else None
                    has_speech = analysis is not None and analysis.has_speech
                    if has_speech and engine is not None and analysis is not None:
                        # M54 finalization fast path: when nothing but
                        # silence arrived after the last hot decode, that
                        # decode IS the final's raw text — no re-decode.
                        fast_text: str | None = None
                        if (
                            is_final_pass
                            and config.final_fast_path
                            and state.last_hot is not None
                            and state.last_hot[0] == state.window_start
                            and not state.commit_pending
                        ):
                            covered = state.last_hot[1]
                            tail = buffer[int(covered * SAMPLE_RATE) :]
                            if len(tail) == 0 or not self._analysis(tail).has_speech:
                                fast_text = state.last_hot[2]
                                self._metrics.fast_path_final = True
                                logger.info(
                                    "realtime_final_fast_path",
                                    session=self.session_id,
                                    tail_seconds=round(len(tail) / SAMPLE_RATE, 2),
                                )

                        def hot_decode(w: np.ndarray = window, f: bool = is_final_pass) -> str:
                            return engine.decode(w, final=f)

                        try:
                            if fast_text is not None:
                                text = fast_text
                            else:
                                submitted = time.perf_counter()

                                def timed_decode() -> tuple[str, float, float]:
                                    began = time.perf_counter()
                                    out = hot_decode()
                                    return out, began, time.perf_counter()

                                text, began, done_at = await loop.run_in_executor(
                                    self.service.hot_executor, timed_decode
                                )
                                self._metrics.hot_queue_ms.append((began - submitted) * 1000.0)
                                self._metrics.hot_decode_ms.append((done_at - began) * 1000.0)
                        except Exception as exc:
                            decode_failures += 1
                            logger.warning(
                                "realtime_decode_failed",
                                failures=decode_failures,
                                final=is_final_pass,
                                reason=type(exc).__name__,
                            )
                            if is_final_pass or decode_failures >= 5:
                                await self._emit(
                                    "session.error",
                                    code="transcription_unavailable",
                                    message="Transcription is temporarily unavailable.",
                                )
                                await self.ws.close(code=1011)
                                return
                            await asyncio.sleep(0.05)
                            continue
                        span_seconds = max(available - state.window_start, 0.1)
                        diagnosis = diagnose_repetition(text, span_seconds)
                        if diagnosis.pathological:
                            # Hot-lane runaway: trim for display/final; the
                            # commit lane owns retry (it persists text).
                            self._metrics.repetition_detected += 1
                            self._metrics.trimmed_words += diagnosis.removed_words
                            logger.warning(
                                "realtime_repetition_detected",
                                lane="hot",
                                session=self.session_id,
                                ngram=diagnosis.ngram,
                                run_length=diagnosis.run_length,
                                removed_words=diagnosis.removed_words,
                            )
                            text = diagnosis.trimmed_text
                            self._guard_block = diagnosis.block
                        state.last_hot = (state.window_start, available, text)
                        partial = (state.committed + " " + text).strip()
                        if self._guard_block:
                            partial = collapse_block_runs(partial, self._guard_block)
                        if is_final_pass:
                            await self._emit_final(partial, available)
                        else:
                            state.sequence += 1
                            await self._emit(
                                "transcript.partial",
                                sequence=state.sequence,
                                text=partial,
                                is_final=False,
                            )
                            # VAD-aligned commit, scheduled OFF the hot path.
                            window_seconds = available - state.window_start
                            if (
                                window_seconds > config.max_window_seconds
                                and not state.commit_pending
                            ):
                                cut_local = next(
                                    (
                                        region.end_seconds
                                        for region in reversed(analysis.regions)
                                        if region.end_seconds
                                        <= window_seconds - config.commit_margin_seconds
                                    ),
                                    window_seconds - config.commit_margin_seconds,
                                )
                                cut = state.window_start + cut_local
                                span = buffer[
                                    int(state.window_start * SAMPLE_RATE) : int(cut * SAMPLE_RATE)
                                ]

                                def commit_decode(
                                    a: np.ndarray = span, c: float = cut
                                ) -> tuple[str, float]:
                                    return engine.decode(a, final=True), c

                                state.commit_pending = True
                                commit_future = loop.run_in_executor(
                                    self.service.commit_executor, commit_decode
                                )
                    elif is_final_pass:
                        # Silence-only tail (or whole session): committed
                        # text IS the final; empty stays empty, no model
                        # call — the M52 silence law.
                        await self._emit_final(state.committed, available)
                if is_final_pass:
                    logger.info(
                        "realtime_session_completed",
                        session=self.session_id,
                        audio_seconds=round(available, 3),
                        sequences=state.sequence,
                        metrics=self._metrics.summary(),
                    )
                    await self._emit("session.completed", audio_seconds=round(available, 3))
                    # Ordered shutdown: the CLIENT closes after it has the
                    # completed event; closing here raced the transport
                    # flush and could drop the last frame on the wire
                    # (M53 browser-E2E finding). Bounded grace, then close.
                    for _ in range(40):
                        if state.gone:
                            break
                        await asyncio.sleep(0.05)
                    with contextlib.suppress(Exception):
                        await self.ws.close()
                    return
                await asyncio.sleep(0.05)
        except Exception:
            logger.warning("realtime_session_failed", session=self.session_id)
            with contextlib.suppress(Exception):
                await self._emit(
                    "session.error",
                    code="internal",
                    message="The realtime session ended unexpectedly.",
                )
                await self.ws.close(code=1011)
        finally:
            receiver_task.cancel()


async def run_realtime_endpoint(
    websocket: WebSocket,
    *,
    service: RealtimeService | None,
    punctuator: PunctuationRestorer | None,
    punctuator_en: EnPunctuationRestorer | None,
    start_timeout_seconds: float = 10.0,
) -> None:
    """The WS route body: handshake → session. Kept out of routes.py so
    the protocol is unit-testable without HTTP plumbing."""
    if service is None:
        await websocket.close(code=CLOSE_UNAVAILABLE)
        return
    await websocket.accept()
    try:
        first = await asyncio.wait_for(websocket.receive_text(), timeout=start_timeout_seconds)
        start = json.loads(first)
    except Exception:
        await websocket.close(code=CLOSE_BAD_REQUEST)
        return
    language = str(start.get("language", "")).strip()
    if start.get("event") != "start" or not service.supports(language):
        await websocket.close(code=CLOSE_BAD_REQUEST)
        return
    if service.engine_for(language) is None:
        # Language allowed by policy but no backend configured on this
        # deployment (e.g. hindi without a GPU llama-server URL): an
        # honest refusal, never a silently wrong model.
        await websocket.close(code=CLOSE_UNAVAILABLE)
        return
    session = RealtimeSession(
        websocket,
        service,
        language=language,
        punctuator=punctuator,
        punctuator_en=punctuator_en,
    )
    await session.run()
