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
import json
import socket
import struct
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Final

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
RUNTIME_BUILD: Final = "llama.cpp b10344 (7a20b417f) win-cpu-x64, Clang 20.1.8"

RUNTIME_BINARY_PINS: Final[dict[str, str]] = {
    "llama-server.exe": "b2ace4b8aed7c60e217fcaed8541850f4998539b8478880f1c3264387a0a8d97",
    "llama-server-impl.dll": "27eb413c373bad732533c3d8cde7d0841a0038be59485e2da6a4b0d323a9f8ad",
    "llama.dll": "b1e503807cf5811569eaa3cd867830ad73535f51efc4138b042b81284a90146f",
    "mtmd.dll": "cd0c5118f34ebabb706a1e4deb3a7a469ca030ef4501e14d91b0fcfeef294e45",
    "ggml.dll": "112c29c592a9b0f86bfc91aed9397d64bbd06552f68c9d503f3bbb1a545503ab",
    "ggml-base.dll": "58ef8ecf8e2a1935df8016739d7ffa2c27ab5957bade9da2273fa7ec8ed9a0b1",
}


def verify_runtime_binaries(server_binary: Path) -> None:
    """Refuse to serve through a runtime build we did not pin.

    The GGUF weights are verified by the ArtifactStore at boot; this
    closes the OTHER half of the supply chain — the decoder executing
    them. Hash mismatch and missing file are the same refusal: an
    unverifiable runtime is an unpinned runtime.
    """
    import hashlib

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


class Qwen3AsrEngine:
    """One llama-server child, one loaded Qwen3-ASR artifact."""

    def __init__(
        self,
        process: subprocess.Popen[bytes],
        base_url: str,
        *,
        context_tokens: int,
        timeout_seconds: float,
        max_tokens: int = 2048,
    ) -> None:
        self._process = process
        self._base_url = base_url
        self._context_tokens = context_tokens
        self._timeout_seconds = timeout_seconds
        self._max_tokens = max_tokens

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
            },
        )

    def transcribe(self, audio: DecodedAudio, request: TranscriptionRequest) -> TranscriptionResult:
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
        except (TimeoutError, urllib.error.URLError) as exc:
            raise RuntimeServiceError(
                RuntimeErrorType.INTERNAL,
                "the transcription backend did not answer in time",
            ) from exc
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeServiceError(
                RuntimeErrorType.INTERNAL,
                "the transcription backend returned an unreadable response",
            ) from exc

        emitted, text = parse_asr_output(content)
        segments: tuple[TranscriptionSegment, ...] = ()
        if text:
            # No timestamps exist in this lineage's ASR output; the honest
            # segmentation is one utterance spanning the decoded audio.
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

    def close(self) -> None:
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
        if process.poll() is not None:
            msg = f"llama-server exited with code {process.returncode} during load"
            raise RuntimeError(msg)
        try:
            with urllib.request.urlopen(  # noqa: S310 — loopback-only, fixed scheme
                f"{base_url}/health", timeout=2
            ) as response:
                if response.status == 200:
                    break
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        if time.monotonic() > deadline:
            with contextlib.suppress(OSError):
                process.kill()
            msg = f"llama-server did not become healthy within {load_timeout_seconds:.0f}s"
            raise RuntimeError(msg)
        time.sleep(_HEALTH_POLL_SECONDS)

    return Qwen3AsrEngine(
        process,
        base_url,
        context_tokens=context_tokens,
        timeout_seconds=timeout_seconds,
    )
