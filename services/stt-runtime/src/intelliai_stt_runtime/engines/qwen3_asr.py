"""Qwen3AsrEngine — the first non-Whisper lineage behind the engine seam.

RESEARCH-ONLY (Milestone 15E): no production route resolves to this
artifact, the gateway's catalog has never heard its name, and the only
manifest that can reach it is ml/evaluation/manifests/research.json.
Promotion is a founder decision recorded in the ledger, never a code
change here.

Serving shape: one pinned llama.cpp `llama-server` child process per
loaded slot, spoken to over loopback HTTP. That is deliberate — the
model is an audio-LLM with no CTranslate2/faster-whisper path, and the
llama.cpp CPU build is the only measured way to run it in our serving
class (15B spike; Q8_0, ctx-bounded). The child is part of the engine:
spawned at load, killed at close, never shared, never exposed beyond
127.0.0.1.

Identity: the GGUF pins below are the OFFICIAL ggml-org conversion of
Qwen/Qwen3-ASR-0.6B (apache-2.0, verified at source 2026-08-12; not
gated; no remote code). Local bytes were re-verified against the HF LFS
object metadata at pin time — the URLs are real and downloadable, unlike
the .invalid research fine-tunes, because these weights are publicly
distributed by their publisher.

Decode policy: greedy (temperature 0) — a deliberate divergence from the
15B spike's CLI-default sampling, chosen so identical requests decode
identically (replicate stability is part of the evaluation contract).
The model emits `language <Name><asr_text><transcript>` and no
timestamps (timestamps are a separate aligner model in this lineage), so
results carry a single utterance-spanning segment.
"""

from __future__ import annotations

import base64
import contextlib
import http.client
import json
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Final

import structlog

from intelliai_runtime_contract import (
    RuntimeErrorType,
    TranscriptionRequest,
    TranscriptionResult,
    TranscriptionSegment,
)
from intelliai_runtime_core import (
    ArtifactFile,
    ArtifactSpec,
    EngineDescription,
    RuntimeServiceError,
)
from intelliai_stt_runtime.pipeline import DecodedAudio

logger = structlog.get_logger(__name__)

ARTIFACT_ID: Final = "qwen3-asr-0.6b"

MODEL_FILENAME: Final = "Qwen3-ASR-0.6B-Q8_0.gguf"
MMPROJ_FILENAME: Final = "mmproj-Qwen3-ASR-0.6B-Q8_0.gguf"

#: Official ggml-org conversion of Qwen/Qwen3-ASR-0.6B, pinned to the
#: repo revision whose LFS records match these hashes (verified
#: 2026-08-12). Upstream model: Qwen/Qwen3-ASR-0.6B @ 5eb144179a02acc5
#: (apache-2.0, not gated, no custom code files).
_GGUF_BASE: Final = (
    "https://huggingface.co/ggml-org/Qwen3-ASR-0.6B-GGUF/resolve/"
    "928ab958557df9aa2ef1c93e0e83c7ad0933fae2"
)

QWEN3_ASR_0_6B_FILES: Final = ArtifactSpec(
    artifact=ARTIFACT_ID,
    version=1,
    files=(
        ArtifactFile(
            filename=MODEL_FILENAME,
            url=f"{_GGUF_BASE}/{MODEL_FILENAME}",
            sha256="bca259818b50ca7c4c05e9bdb35a5dc04fa039653a6d6f3f0f331f96f6aa1971",
        ),
        ArtifactFile(
            filename=MMPROJ_FILENAME,
            url=f"{_GGUF_BASE}/{MMPROJ_FILENAME}",
            sha256="41a342b5e4c514e968cb756de6cd1b7be39eff43c44c57a2ef5fc6522e36603d",
        ),
    ),
)

#: This family's admission table (same law as the whisper table): a new
#: checkpoint is a pinned entry here, never a declaration.
ARTIFACT_SPECS: Final[dict[str, ArtifactSpec]] = {ARTIFACT_ID: QWEN3_ASR_0_6B_FILES}

#: The serving RUNTIME is pinned exactly like the weights (Milestone 16,
#: supply-chain law): the llama.cpp build is part of the measured system,
#: so an unpinned binary must never silently become the thing a research
#: record describes. These are the load-bearing files of the b10344
#: win-cpu-x64 distribution (zip sha256 c0cec8825843957cae6620f927eb6eb9
#: f7f4680da3206910932ea9075f91b405; build `10344 (7a20b417f)`, Clang
#: 20.1.8, Windows x86_64), hashed 2026-08-12. Adopting a new build is a
#: reviewed edit to this table — never an environment variable.
#: One pinned build PER PLATFORM (Milestone 17): the Windows evidence
#: (15B spike through Milestone 16) and the Linux evidence are separate
#: measured systems and keep separate pin tables. A platform with no
#: table has no pinned runtime and is refused outright.
_RUNTIME_BUILDS: Final[dict[str, str]] = {
    "win32": "llama.cpp b10344 (7a20b417f) win-cpu-x64, Clang 20.1.8",
    "linux": "llama.cpp b10344 (7a20b417f) ubuntu-x64, GNU 11.4.0",
}

_RUNTIME_BINARY_PINS_BY_PLATFORM: Final[dict[str, dict[str, str]]] = {
    # Hashed 2026-08-12 from the official b10344 win-cpu-x64 zip
    # (sha256 c0cec8825843957cae6620f927eb6eb9f7f4680da3206910932ea9075f91b405).
    "win32": {
        "llama-server.exe": "b2ace4b8aed7c60e217fcaed8541850f4998539b8478880f1c3264387a0a8d97",
        "llama-server-impl.dll": "27eb413c373bad732533c3d8cde7d0841a0038be59485e2da6a4b0d323a9f8ad",
        "llama.dll": "b1e503807cf5811569eaa3cd867830ad73535f51efc4138b042b81284a90146f",
        "mtmd.dll": "cd0c5118f34ebabb706a1e4deb3a7a469ca030ef4501e14d91b0fcfeef294e45",
        "ggml.dll": "112c29c592a9b0f86bfc91aed9397d64bbd06552f68c9d503f3bbb1a545503ab",
        "ggml-base.dll": "58ef8ecf8e2a1935df8016739d7ffa2c27ab5957bade9da2273fa7ec8ed9a0b1",
    },
    # Hashed 2026-08-12 from the official b10344 ubuntu-x64 tar.gz
    # (sha256 01b90b0764821d0e53b985730eea3837e29a976ee00e783e18837937b93fc3f1)
    # — the SAME tag and commit as the Windows build, compiled GNU 11.4.0.
    # System dependency (outside this table, satisfied by the OS/container
    # layer): libgomp.so.1.
    "linux": {
        "llama-server": "9b7b699e2e9579184117834aeaef34d5cc711027fbbc67a2a38d66559c4f288e",
        "libllama-server-impl.so": (
            "2e5d35d03aefee87ff59482e098b081bc75251ff633a5bc381ce75200df2fefc"
        ),
        "libllama.so": "4b5095195b0cadb260ea2765cfab9d1e503f92bb6b82f15f971c489f6ce77007",
        "libmtmd.so": "d6a465f5346b4d5d89ce995f19cc67b21b3b9ea846995c8e043c0536087c64ae",
        "libggml.so": "ffd6a736ad58e2d9407ed427252520ffbd4bca8dd5de467ecb2bd446a7a3d75b",
        "libggml-base.so": "e486598626ec06c8cb23a4661ad0401f146a7744b0a136f092e6042597a21e4c",
    },
}

#: Backwards-compatible names: the current platform's build + table.
RUNTIME_BUILD: Final = _RUNTIME_BUILDS.get(sys.platform, f"UNPINNED PLATFORM {sys.platform}")
RUNTIME_BINARY_PINS: Final[dict[str, str]] = _RUNTIME_BINARY_PINS_BY_PLATFORM.get(sys.platform, {})


def verify_runtime_binaries(server_binary: Path) -> None:
    """Refuse to serve through a runtime build we did not pin.

    The GGUF weights are verified by the ArtifactStore at boot; this
    closes the OTHER half of the supply chain — the decoder executing
    them. Hash mismatch, missing file, and an unpinned PLATFORM are the
    same refusal: an unverifiable runtime is an unpinned runtime.
    """
    import hashlib

    if not RUNTIME_BINARY_PINS:
        msg = (
            f"no pinned llama.cpp runtime exists for platform {sys.platform!r}; "
            "serving requires a reviewed pin table for this platform"
        )
        raise ValueError(msg)
    directory = server_binary.parent
    for filename, expected in RUNTIME_BINARY_PINS.items():
        candidate = directory / filename
        if not candidate.exists():
            msg = (
                f"pinned runtime file {filename!r} is missing beside {server_binary}; "
                f"the qwen3-asr engine serves ONLY through the pinned build ({RUNTIME_BUILD})"
            )
            raise ValueError(msg)
        digest = hashlib.sha256()
        with candidate.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected:
            msg = (
                f"runtime file {filename!r} does not match its pin; refusing to serve "
                f"through an unpinned build. Expected the {RUNTIME_BUILD} distribution; "
                "adopting a new build is a reviewed edit to RUNTIME_BINARY_PINS, "
                "never a swap on disk"
            )
            raise ValueError(msg)


#: The fixed ASR prompt (matches the 15B spike and the model's intended
#: use). Language is NOT selectable through this model's request surface:
#: it auto-detects and self-reports via the output header, which the
#: adapter parses. A request's `language` hint therefore only fills the
#: result when the model emits no recognizable tag of its own.
ASR_PROMPT: Final = "Transcribe the audio."
ASR_MARKER: Final = "<asr_text>"

#: Model-emitted language names -> the ISO-639-1 codes our contract uses.
#: Only languages the lineage officially claims and IntelliAI targets are
#: mapped; anything else stays as detected-but-unmapped ("und" + hint).
EMITTED_LANGUAGE_TAGS: Final[dict[str, str]] = {
    "hindi": "hi",
    "english": "en",
    "chinese": "zh",
    "mandarin": "zh",
    "arabic": "ar",
    "urdu": "ur",
}

_HEALTH_POLL_SECONDS: Final = 0.5
_TERMINATE_GRACE_SECONDS: Final = 10.0


def parse_asr_output(raw: str) -> tuple[str | None, str]:
    """``language Hindi<asr_text>text`` -> ("Hindi", "text").

    Without the marker the whole (stripped) output is the transcript and
    the emitted language is unknown — the adapter never guesses.
    """
    if ASR_MARKER not in raw:
        return None, raw.strip()
    head, _, tail = raw.partition(ASR_MARKER)
    emitted: str | None = None
    if "language" in head:
        candidate = head.rsplit("language", 1)[-1].strip().strip(":").strip()
        emitted = candidate or None
    return emitted, tail.strip()


def resolve_language(emitted: str | None, requested: str | None) -> str:
    """Detected tag wins when we can map it; the hint fills the gaps."""
    if emitted is not None:
        mapped = EMITTED_LANGUAGE_TAGS.get(emitted.strip().lower())
        if mapped is not None:
            return mapped
    return requested or "und"


def plan_windows(
    duration_seconds: float,
    *,
    window_seconds: float,
    overlap_seconds: float,
) -> list[tuple[float, float]]:
    """Deterministic chunk windows: fixed stride, overlapping, bounded.

    Starts advance by ``window - overlap``; every window is ``window``
    long except the last, which ends exactly at ``duration``. A tail
    bringing less NEW audio than the overlap would be a near-duplicate
    sliver (the previous window already heard almost all of it), so it
    is absorbed by extending the last window instead of being decoded.
    At the 600 s product ceiling with the default 100/5 shape this
    yields exactly 7 windows.
    """
    if duration_seconds <= window_seconds:
        return [(0.0, duration_seconds)]
    step = window_seconds - overlap_seconds
    if step <= 0:
        msg = "chunk window must be longer than the overlap"
        raise ValueError(msg)
    windows: list[tuple[float, float]] = []
    start = 0.0
    while start + window_seconds < duration_seconds:
        windows.append((start, start + window_seconds))
        start += step
    new_audio = duration_seconds - windows[-1][1] if windows else duration_seconds
    if windows and new_audio < overlap_seconds:
        windows[-1] = (windows[-1][0], duration_seconds)
    else:
        windows.append((start, duration_seconds))
    return windows


def quietest_moment(audio: DecodedAudio, target_seconds: float, radius_seconds: float) -> float:
    """The center of the lowest-energy 200 ms block near ``target``.

    A deterministic argmin over mean |sample| per block — seam
    placement, not voice-activity detection. Ties break toward the
    earliest block, so identical audio always snaps identically.
    """
    import array

    if radius_seconds <= 0:
        return target_seconds
    frame_bytes = audio.channels * audio.sample_width_bytes
    rate = audio.sample_rate_hz
    lo = max(0.0, target_seconds - radius_seconds)
    hi = min(audio.duration_seconds, target_seconds + radius_seconds)
    block = 0.2
    if hi - lo < block * 2:
        return target_seconds
    samples = array.array("h")
    samples.frombytes(audio.pcm[int(lo * rate) * frame_bytes : int(hi * rate) * frame_bytes])
    per_block = max(1, int(block * rate) * audio.channels)
    best_energy: float | None = None
    best_center = target_seconds
    for index in range(0, len(samples) - per_block + 1, per_block):
        chunk = samples[index : index + per_block]
        energy = sum(abs(value) for value in chunk) / per_block
        if best_energy is None or energy < best_energy:
            best_energy = energy
            best_center = lo + (index + per_block / 2) / (rate * audio.channels)
    return best_center


def slice_audio(audio: DecodedAudio, start_seconds: float, end_seconds: float) -> DecodedAudio:
    """A frame-exact PCM byte-slice — no re-decode, no disk, no ffmpeg."""
    frame_bytes = audio.channels * audio.sample_width_bytes
    start_frame = round(start_seconds * audio.sample_rate_hz)
    end_frame = round(end_seconds * audio.sample_rate_hz)
    pcm = audio.pcm[start_frame * frame_bytes : end_frame * frame_bytes]
    return DecodedAudio(
        pcm=pcm,
        sample_rate_hz=audio.sample_rate_hz,
        channels=audio.channels,
        sample_width_bytes=audio.sample_width_bytes,
        duration_seconds=len(pcm) / (frame_bytes * audio.sample_rate_hz),
    )


def normalize_for_merge(word: str) -> str:
    """Engine-local matching normalization for overlap dedup ONLY.

    NFC + casefold + punctuation/format-character stripping. This never
    touches output text — it only decides how many overlap words to
    drop. The evaluation ruler is NOT imported here on purpose: the
    runtime does not depend on the evaluation plane (layering law); the
    sandbox proof checks seam quality with the real ruler instead.
    """
    import unicodedata

    normalized = unicodedata.normalize("NFC", word).casefold()
    return "".join(ch for ch in normalized if not unicodedata.category(ch).startswith(("P", "C")))


def merge_chunk_text(
    previous_words: list[str], chunk_text: str, overlap_window: int = 14
) -> list[str]:
    """The words `chunk_text` ADDS after overlap dedup (deterministic).

    Longest suffix(previous)/prefix(chunk) match on normalized words;
    empty-normalizing words (pure punctuation) are kept in the output
    but never participate in matching. No model, no heuristics beyond
    exact normalized equality.
    """
    chunk_words = chunk_text.split()
    if not previous_words:
        return chunk_words
    if not chunk_words:
        return []
    prev_norm = [normalize_for_merge(w) for w in previous_words[-overlap_window:]]
    next_norm = [normalize_for_merge(w) for w in chunk_words[: overlap_window * 2]]
    best = 0
    for k in range(min(len(prev_norm), len(next_norm)), 0, -1):
        if prev_norm[-k:] == next_norm[:k] and any(prev_norm[-k:]):
            best = k
            break
    return chunk_words[best:]


def wav_bytes(audio: DecodedAudio) -> bytes:
    """Wrap canonical PCM in a minimal RIFF/WAVE container (PCM fmt 1)."""
    byte_rate = audio.sample_rate_hz * audio.channels * audio.sample_width_bytes
    block_align = audio.channels * audio.sample_width_bytes
    header = b"RIFF" + struct.pack("<I", 36 + len(audio.pcm)) + b"WAVE"
    header += b"fmt " + struct.pack(
        "<IHHIIHH",
        16,
        1,
        audio.channels,
        audio.sample_rate_hz,
        byte_rate,
        block_align,
        audio.sample_width_bytes * 8,
    )
    header += b"data" + struct.pack("<I", len(audio.pcm))
    return header + audio.pcm


#: Slot readiness states this engine reports (Milestone 17). The strings
#: are API surface for /health/ready and therefore stable.
SLOT_READY: Final = "ready"
SLOT_RESTARTING: Final = "restarting"
SLOT_FAILED: Final = "failed"

#: The measured-safe DIRECT-decode ceiling at ctx=4096 (Milestone 17):
#: 120 s inputs transcribe completely in one pass; beyond it the token
#: budget silently truncates (M19 research: onset ~180 s, collapse at
#: 300 s, hard failure at 600 s). Audio longer than this goes through
#: the chunked path — it must NEVER reach a single-pass decode.
DEFAULT_DIRECT_AUDIO_SECONDS: Final = 120.0

#: The total request ceiling — raised 120 → 600 at Milestone 19
#: Phase 18, AFTER the full proof battery passed (sandbox through the
#: engine at 120/180/300/600 with repeats; staging product path incl.
#: kill-mid-window drills; Web; seam A/B on spontaneous speech;
#: concurrency regression). ≤120 s decodes in the proven single pass;
#: 120-600 s decodes through the chunked path; beyond 600 the loud
#: refusal remains, because the M17 silent-truncation incident is the
#: failure this constant exists to prevent.
DEFAULT_MAX_AUDIO_SECONDS: Final = 600.0

#: Chunked-path shape, from the measured M19 research (100 s windows +
#: 5 s overlap were complete at 300 s AND 600 s, CER 0.18-0.21, at the
#: product ctx 4096; the serving build RETAINS RSS across sequential
#: decodes — a capacity fact, recorded in the M19 implementation doc).
#: Window arithmetic lives in :func:`plan_windows`; these are the only
#: knobs.
DEFAULT_CHUNK_WINDOW_SECONDS: Final = 100.0
DEFAULT_CHUNK_OVERLAP_SECONDS: Final = 5.0

#: How far a chunk boundary may slide toward a quieter moment (0
#: disables snapping). The M19 research warned that fixed seams can cut
#: mid-word; the snap is a deterministic energy argmin near the seam —
#: NOT a second VAD (EnergyVad's regions are not plumbed to engines;
#: re-plumbing that seam was judged not worth it — recorded limitation).
DEFAULT_CHUNK_SNAP_RADIUS_SECONDS: Final = 8.0

#: Output budget per single inference. ~12 text-tokens per Hindi
#: speech-second (measured): a 120 s direct pass or a 100 s window both
#: stay far inside 2048; chunking keeps this constant SAFE by
#: construction, which is exactly why the window is 100 s.
MAX_TOKENS_PER_INFERENCE: Final = 2048

#: One bounded retry per chunk (Milestone 19 failure law): a chunk that
#: fails twice fails the WHOLE request — a partial transcript is never
#: returned. The delay before the retry gives the supervisor its
#: detect→restart window (M17 measured ~10 s total outage).
CHUNK_RETRY_DELAY_SECONDS: Final = 12.0

#: Backoff schedule between restart attempts. Bounded BY CONSTRUCTION:
#: the number of attempts equals the schedule's length — there is no
#: separate counter to drift out of sync, and no hidden retry after the
#: last entry. Exponential-ish, totals ~31 s before the slot is declared
#: failed.
DEFAULT_RESTART_BACKOFF_SECONDS: Final[tuple[float, ...]] = (1.0, 5.0, 25.0)


class Qwen3AsrEngine:
    """One supervised llama-server child, one loaded Qwen3-ASR artifact.

    Supervision (Milestone 17): a daemon monitor watches the child; on
    death the slot flips to `restarting` immediately (readiness truth
    precedes recovery), bounded backoff restarts run through the same
    spawn path the loader used, and exhausting the schedule parks the
    slot at `failed` — a terminal state until the PROCESS is restarted,
    because an engine that silently retries forever hides its outages.
    Requests during any non-ready state are refused with NOT_READY and
    a message that names nothing internal. The spawn and sleep hooks are
    injectable so every state transition is deterministically testable.
    """

    def __init__(
        self,
        process: subprocess.Popen[bytes],
        base_url: str,
        *,
        context_tokens: int,
        timeout_seconds: float,
        max_tokens: int = 2048,
        spawn: Callable[[], tuple[subprocess.Popen[bytes], str]] | None = None,
        restart_backoff_seconds: tuple[float, ...] = DEFAULT_RESTART_BACKOFF_SECONDS,
        monitor_interval_seconds: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
        closed_event: threading.Event | None = None,
        max_audio_seconds: float = DEFAULT_MAX_AUDIO_SECONDS,
        direct_audio_seconds: float = DEFAULT_DIRECT_AUDIO_SECONDS,
        chunk_window_seconds: float = DEFAULT_CHUNK_WINDOW_SECONDS,
        chunk_overlap_seconds: float = DEFAULT_CHUNK_OVERLAP_SECONDS,
        chunk_snap_radius_seconds: float = DEFAULT_CHUNK_SNAP_RADIUS_SECONDS,
    ) -> None:
        self._process = process
        self._base_url = base_url
        self._context_tokens = context_tokens
        self._timeout_seconds = timeout_seconds
        self._max_tokens = max_tokens
        self._spawn = spawn
        self._restart_backoff = restart_backoff_seconds
        self._monitor_interval = monitor_interval_seconds
        self._sleep = sleep
        self._max_audio_seconds = max_audio_seconds
        self._direct_audio_seconds = direct_audio_seconds
        self._chunk_window_seconds = chunk_window_seconds
        self._chunk_overlap_seconds = chunk_overlap_seconds
        self._chunk_snap_radius_seconds = chunk_snap_radius_seconds
        self._state = SLOT_READY
        self._restarts_completed = 0
        self._restart_attempts = 0
        self._lock = threading.Lock()
        # Shared with the loader's spawn closure (Milestone 17 orphan
        # fix): closing the engine aborts an IN-FLIGHT spawn's health
        # wait, which kills its own child — so no window exists in which
        # interpreter exit can strand a spawned-but-unadopted process.
        self._closed = closed_event if closed_event is not None else threading.Event()
        self._monitor: threading.Thread | None = None
        if spawn is not None:
            self._monitor = threading.Thread(
                target=self._monitor_loop, name="qwen3-asr-supervisor", daemon=True
            )
            self._monitor.start()

    # ── Supervision ────────────────────────────────────────────────────

    def slot_state(self) -> str:
        """`ready` | `restarting` | `failed` — the readiness truth."""
        return self._state

    def slot_stats(self) -> dict[str, int]:
        """Observability counters for monitors (never for /info)."""
        return {
            "restarts_completed": self._restarts_completed,
            "restart_attempts": self._restart_attempts,
        }

    def _monitor_loop(self) -> None:
        while not self._closed.wait(self._monitor_interval):
            with self._lock:
                if self._state != SLOT_READY:
                    continue
                process = self._process
            if process is not None and process.poll() is not None:
                self._restart()
            if self._state == SLOT_FAILED:
                return  # terminal: no hidden retry loop survives it

    def _restart(self) -> None:
        """Bounded, backoff-paced recovery through the loader's own path."""
        assert self._spawn is not None  # noqa: S101 — monitor exists only with spawn
        with self._lock:
            if self._state != SLOT_READY:  # pragma: no cover - already recovering
                return
            self._state = SLOT_RESTARTING
        logger.warning("qwen3_child_died", state=SLOT_RESTARTING)
        for attempt, delay in enumerate(self._restart_backoff, start=1):
            self._sleep(delay)
            if self._closed.is_set():
                return
            with self._lock:
                self._restart_attempts += 1
            try:
                process, base_url = self._spawn()
            except Exception as exc:  # every spawn failure is one bounded attempt
                logger.warning(
                    "qwen3_restart_attempt_failed",
                    attempt=attempt,
                    of=len(self._restart_backoff),
                    error=type(exc).__name__,
                )
                continue
            with self._lock:
                if self._closed.is_set():  # closed mid-spawn: don't adopt
                    with contextlib.suppress(OSError):
                        process.terminate()
                    return
                self._process = process
                self._base_url = base_url
                self._restarts_completed += 1
                self._state = SLOT_READY
            logger.info("qwen3_child_restarted", attempt=attempt)
            return
        with self._lock:
            self._state = SLOT_FAILED
        logger.error("qwen3_slot_failed", attempts=len(self._restart_backoff))

    def describe(self) -> EngineDescription:
        """The decode configuration actually sent on every request.

        There is no signature to introspect here — the decoder lives in
        the child process — so this reports exactly the parameters the
        adapter transmits plus the serving facts that bound them. All are
        constant for the engine's lifetime.
        """
        return EngineDescription(
            compute_type="q8_0",
            emitted_unit="word",
            decode_params={
                "temperature": "0.0",
                "max_tokens": str(self._max_tokens),
                "context_tokens": str(self._context_tokens),
                "prompt": ASR_PROMPT,
                "output_marker": ASR_MARKER,
                "timestamps": "false",  # this lineage's ASR models emit none
                "server_build": RUNTIME_BUILD,
                "audio_transport": "wav s16le via input_audio",
                "request_timeout_seconds": str(self._timeout_seconds),
                # Milestone 19 long-audio shape — constant for the
                # engine's lifetime, so it belongs in evidence records.
                "direct_audio_seconds": str(self._direct_audio_seconds),
                "chunk_window_seconds": str(self._chunk_window_seconds),
                "chunk_overlap_seconds": str(self._chunk_overlap_seconds),
                "chunk_snap_radius_seconds": str(self._chunk_snap_radius_seconds),
            },
        )

    def transcribe(self, audio: DecodedAudio, request: TranscriptionRequest) -> TranscriptionResult:
        if audio.duration_seconds > self._max_audio_seconds:
            # Loud refusal beats silent truncation: beyond the ceiling
            # a single-pass decode returns a fraction of the transcript
            # with a 200 — unacceptable data loss (M17 Phase 6 finding).
            raise RuntimeServiceError(
                RuntimeErrorType.INVALID_INPUT,
                (
                    f"audio longer than {self._max_audio_seconds:.0f} seconds is not "
                    "supported by the requested model"
                ),
                param="file",
            )
        if self._state != SLOT_READY:
            # Truthful refusal while the supervisor works (or has given
            # up): the request never waits on a backend known to be down.
            raise RuntimeServiceError(
                RuntimeErrorType.NOT_READY,
                "the requested model is temporarily unavailable",
            )
        if audio.duration_seconds <= self._direct_audio_seconds:
            # The proven short path, byte-for-byte the M15E-M18 behavior.
            emitted, text = self._decode_once(audio)
            segments: tuple[TranscriptionSegment, ...] = ()
            if text:
                # No timestamps exist in this lineage's ASR output; the
                # honest segmentation is one utterance-spanning segment.
                segments = (
                    TranscriptionSegment(
                        start_seconds=0.0,
                        end_seconds=audio.duration_seconds,
                        text=text,
                    ),
                )
            return TranscriptionResult(
                text=text,
                language=resolve_language(emitted, request.language),
                duration_seconds=audio.duration_seconds,
                segments=segments,
            )
        return self._transcribe_chunked(audio, request)

    def _transcribe_chunked(
        self, audio: DecodedAudio, request: TranscriptionRequest
    ) -> TranscriptionResult:
        """The Milestone 19 long-audio path: complete transcript or clean failure.

        The customer sees ONE result; internally the decoded PCM is
        byte-sliced into overlapping windows (boundaries snapped toward
        the quietest nearby moment), each window decoded through the
        same child with ONE bounded retry, and the texts merged by
        normalized overlap dedup. A window that fails twice fails the
        WHOLE request — a partial transcript is never returned.
        """
        windows = plan_windows(
            audio.duration_seconds,
            window_seconds=self._chunk_window_seconds,
            overlap_seconds=self._chunk_overlap_seconds,
        )
        if self._chunk_snap_radius_seconds > 0 and len(windows) > 1:
            snapped: list[tuple[float, float]] = [windows[0]]
            for start, end in windows[1:]:
                new_start = quietest_moment(audio, start, self._chunk_snap_radius_seconds)
                # The previous window must still overlap the (possibly
                # moved) boundary, or seam words could be heard by no one.
                previous_start = snapped[-1][0]
                new_start = max(new_start, previous_start + self._chunk_overlap_seconds)
                snapped[-1] = (previous_start, min(new_start + self._chunk_overlap_seconds, end))
                snapped.append((new_start, end))
            windows = snapped

        merged_words: list[str] = []
        contributions: list[tuple[float, float, str]] = []
        emitted_language: str | None = None
        for index, (start, end) in enumerate(windows):
            window_audio = slice_audio(audio, start, end)
            emitted, text = self._decode_window_with_retry(window_audio, index + 1, len(windows))
            emitted_language = emitted_language or emitted
            added = merge_chunk_text(merged_words, text)
            if added:
                merged_words.extend(added)
                contributions.append((start, min(end, audio.duration_seconds), " ".join(added)))
            logger.info(
                "qwen3_chunk_decoded",
                chunk=index + 1,
                of=len(windows),
                window_seconds=round(end - start, 1),
                added_words=len(added),
            )
        segments = tuple(
            TranscriptionSegment(start_seconds=start, end_seconds=end, text=text)
            for start, end, text in contributions
        )
        # The final text IS the join of segment contributions — the
        # verbose_json invariant (concatenated segments == text) holds by
        # construction, never by later reconciliation.
        return TranscriptionResult(
            text=" ".join(text for _, _, text in contributions),
            language=resolve_language(emitted_language, request.language),
            duration_seconds=audio.duration_seconds,
            segments=segments,
        )

    def _decode_window_with_retry(
        self, window_audio: DecodedAudio, chunk: int, of: int
    ) -> tuple[str | None, str]:
        """One window, at most ONE retry, then the whole request fails.

        The retry waits long enough for the supervisor's detect→restart
        cycle (M17: ~10 s), so a child that died mid-request gets exactly
        one chance to have recovered. Failure semantics are the request's
        failure semantics — no partial output survives this method.
        """
        try:
            return self._decode_once(window_audio)
        except RuntimeServiceError as first_error:
            logger.warning(
                "qwen3_chunk_retry",
                chunk=chunk,
                of=of,
                error=first_error.error_type.value,
            )
            self._sleep(CHUNK_RETRY_DELAY_SECONDS)
            if self._state != SLOT_READY:
                raise RuntimeServiceError(
                    RuntimeErrorType.NOT_READY,
                    "the requested model is temporarily unavailable",
                ) from first_error
            try:
                return self._decode_once(window_audio)
            except RuntimeServiceError as second_error:
                logger.error("qwen3_chunk_failed", chunk=chunk, of=of)
                raise RuntimeServiceError(
                    second_error.error_type,
                    "transcription of the full audio could not be completed",
                ) from second_error

    def _decode_once(self, audio: DecodedAudio) -> tuple[str | None, str]:
        """One inference through the child — the SINGLE decode call site."""
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": base64.b64encode(wav_bytes(audio)).decode("ascii"),
                                "format": "wav",
                            },
                        },
                        {"type": "text", "text": ASR_PROMPT},
                    ],
                }
            ],
            "temperature": 0.0,
            "max_tokens": self._max_tokens,
        }
        # S310 suppressed with evidence: the URL is loopback-only by
        # construction (the loader binds the child to 127.0.0.1 and this
        # class never receives a URL from a request), scheme is fixed http.
        http_request = urllib.request.Request(  # noqa: S310
            f"{self._base_url}/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(  # noqa: S310 — loopback-only, fixed scheme
                http_request, timeout=self._timeout_seconds
            ) as response:
                body = json.loads(response.read().decode("utf-8"))
            content = str(body["choices"][0]["message"]["content"])
        # Error messages carry NO engine or model names: the runtime's
        # envelope may be forwarded by layers that must never reveal what
        # serves a request (Milestone 16 drill finding).
        # OSError covers TimeoutError AND urllib's URLError — and, found
        # by the M19 kill-mid-window drill, the raw ConnectionResetError
        # that a child dying MID-RESPONSE raises from response.read(),
        # which urllib does not wrap. HTTPException covers the sibling
        # mid-stream shapes (RemoteDisconnected, IncompleteRead). An
        # exception escaping this clause escapes the retry contract.
        except (OSError, http.client.HTTPException) as exc:
            process = self._process
            if process is not None and process.poll() is not None:
                # The child is dead, not slow: say so truthfully. The
                # supervisor's monitor flips the slot within its interval.
                raise RuntimeServiceError(
                    RuntimeErrorType.NOT_READY,
                    "the requested model is temporarily unavailable",
                ) from exc
            raise RuntimeServiceError(
                RuntimeErrorType.INTERNAL,
                "the transcription backend did not answer in time",
            ) from exc
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeServiceError(
                RuntimeErrorType.INTERNAL,
                "the transcription backend returned an unreadable response",
            ) from exc
        return parse_asr_output(content)

    def close(self) -> None:
        # Supervisor first: after `_closed` is set no restart can adopt a
        # new child, so terminating the current one leaves no orphan.
        self._closed.set()
        if self._monitor is not None:
            self._monitor.join(timeout=_TERMINATE_GRACE_SECONDS)
        with self._lock:
            process, self._process = self._process, None  # type: ignore[assignment]
        if process is None:  # pragma: no cover - double close
            return
        with contextlib.suppress(OSError):
            process.terminate()
        try:
            process.wait(timeout=_TERMINATE_GRACE_SECONDS)
        except subprocess.TimeoutExpired:  # pragma: no cover - stuck child
            with contextlib.suppress(OSError):
                process.kill()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def load_qwen3_asr(
    local_dir: Path | None,
    *,
    server_binary: Path,
    context_tokens: int = 4096,
    timeout_seconds: float = 300.0,
    load_timeout_seconds: float = 180.0,
    restart_backoff_seconds: tuple[float, ...] = DEFAULT_RESTART_BACKOFF_SECONDS,
    max_audio_seconds: float = DEFAULT_MAX_AUDIO_SECONDS,
    direct_audio_seconds: float = DEFAULT_DIRECT_AUDIO_SECONDS,
    chunk_window_seconds: float = DEFAULT_CHUNK_WINDOW_SECONDS,
    chunk_overlap_seconds: float = DEFAULT_CHUNK_OVERLAP_SECONDS,
    chunk_snap_radius_seconds: float = DEFAULT_CHUNK_SNAP_RADIUS_SECONDS,
) -> Qwen3AsrEngine:
    """Slot loader: verified artifact directory -> a serving engine.

    Spawns the pinned llama-server on a loopback-only ephemeral port and
    refuses to return until it answers /health — a slot that loaded is a
    slot that serves, same as every other engine.
    """
    if local_dir is None:
        msg = "qwen3-asr requires a verified artifact directory"
        raise ValueError(msg)
    model = local_dir / MODEL_FILENAME
    mmproj = local_dir / MMPROJ_FILENAME
    if not server_binary.exists():
        msg = (
            f"llama-server binary not found at {server_binary}; this research "
            "engine serves through the pinned llama.cpp CPU build "
            "(b10344, zip sha256 c0cec882…) — set INTELLIAI_STT_QWEN3_SERVER_BINARY "
            "to its llama-server executable"
        )
        raise ValueError(msg)
    verify_runtime_binaries(server_binary)

    # Shared with the engine (Milestone 17 orphan fix): once the engine
    # closes, an in-flight spawn aborts its own health wait and kills its
    # own child — no interpreter-exit window can strand a process.
    closed = threading.Event()

    def spawn() -> tuple[subprocess.Popen[bytes], str]:
        """Spawn one loopback llama-server and wait for /health.

        Used for the initial load AND by the supervisor's restarts, so a
        recovered child is exactly as verified and health-gated as the
        first one.
        """
        port = _free_port()
        base_url = f"http://127.0.0.1:{port}"
        process = subprocess.Popen(  # noqa: S603 — fixed argv from verified store + settings
            [
                str(server_binary),
                "-m",
                str(model),
                "--mmproj",
                str(mmproj),
                "-c",
                str(context_tokens),
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + load_timeout_seconds
        while True:
            if closed.is_set():
                with contextlib.suppress(OSError):
                    process.kill()
                msg = "engine closed while its backend was starting"
                raise RuntimeError(msg)
            if process.poll() is not None:
                msg = f"llama-server exited with code {process.returncode} during load"
                raise RuntimeError(msg)
            try:
                with urllib.request.urlopen(  # noqa: S310 — loopback-only, fixed scheme
                    f"{base_url}/health", timeout=2
                ) as response:
                    if response.status == 200:
                        return process, base_url
            except (urllib.error.URLError, TimeoutError, OSError):
                pass
            if time.monotonic() > deadline:
                with contextlib.suppress(OSError):
                    process.kill()
                msg = f"llama-server did not become healthy within {load_timeout_seconds:.0f}s"
                raise RuntimeError(msg)
            time.sleep(_HEALTH_POLL_SECONDS)

    process, base_url = spawn()
    return Qwen3AsrEngine(
        process,
        base_url,
        context_tokens=context_tokens,
        timeout_seconds=timeout_seconds,
        spawn=spawn,
        restart_backoff_seconds=restart_backoff_seconds,
        closed_event=closed,
        max_audio_seconds=max_audio_seconds,
        direct_audio_seconds=direct_audio_seconds,
        chunk_window_seconds=chunk_window_seconds,
        chunk_overlap_seconds=chunk_overlap_seconds,
        chunk_snap_radius_seconds=chunk_snap_radius_seconds,
    )
