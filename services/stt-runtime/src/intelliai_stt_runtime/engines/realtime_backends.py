"""Realtime decode backends (Milestone 53) — the engine-owned half of
the realtime feature, in engines/ because ONLY engines may import
foundation-model libraries (ADR-0016; CI-enforced).

Two backends, both encoding M52/M52H measured law:

* ``WhisperRealtime`` — a DEDICATED faster-whisper instance (never the
  batch slot: realtime must not queue behind batch inference, and
  device/compute are realtime deployment configuration). Greedy
  partials, beam-5 finals (M52: identical under LocalAgreement-2
  display, cheaper).
* ``QwenRealtime`` — the M52H-verified llama-server contract for the
  UNCHANGED Hindi E3 GGUF: one WAV per request, temperature 0, prompt
  cache off. The server is the same llama.cpp commit family as the
  production pin, CUDA variant, operator-managed.
"""

from __future__ import annotations

import base64
import io
import json
import os
import sys
import urllib.request
import wave
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol

if TYPE_CHECKING:
    import numpy as np

SAMPLE_RATE: Final = 16_000

#: The fixed ASR prompt/output marker — mirrors engines/qwen3_asr.py.
_ASR_PROMPT: Final = "Transcribe the audio."
_ASR_MARKER: Final = "<asr_text>"


class RealtimeDecodeError(RuntimeError):
    """A decode backend failed; message is safe for logs, never clients."""


class RealtimeEngine(Protocol):
    """One realtime decode backend. ``decode`` receives float32 PCM @16k."""

    def decode(self, audio: np.ndarray, *, final: bool) -> str: ...
    def close(self) -> None: ...


def bootstrap_cuda_dlls() -> None:
    """Windows CT2-CUDA needs the cu12 wheel DLL dirs on PATH (measured:
    ``os.add_dll_directory`` alone is not honored by CT2's loader)."""
    if sys.platform != "win32":
        return
    try:
        # Untyped on win32 (wheels installed), absent entirely on Linux
        # CI — the ignore must cover both worlds.
        import nvidia  # type: ignore[import-untyped,import-not-found,unused-ignore]
    except ImportError:
        return
    dll_dirs = sorted(
        {str(dll.parent) for root in nvidia.__path__ for dll in Path(root).rglob("*.dll")}
    )
    if dll_dirs:
        # BOTH mechanisms, measured necessary together: PATH feeds CT2's
        # own LoadLibrary calls; add_dll_directory feeds Python's loader
        # for extension-module dependencies.
        os.environ["PATH"] = os.pathsep.join([*dll_dirs, os.environ.get("PATH", "")])
        for directory in dll_dirs:
            os.add_dll_directory(directory)


class WhisperRealtime:
    """English realtime decodes on a dedicated faster-whisper instance."""

    def __init__(self, model_dir: Path, *, device: str, compute_type: str) -> None:
        if device == "cuda":
            bootstrap_cuda_dlls()
        from faster_whisper import WhisperModel

        if not compute_type:
            compute_type = "float16" if device == "cuda" else "int8"
        self._model = WhisperModel(str(model_dir), device=device, compute_type=compute_type)
        self.device = device
        self.compute_type = compute_type

    def decode(self, audio: np.ndarray, *, final: bool) -> str:
        model = self._model
        if model is None:
            msg = "realtime whisper backend is closed"
            raise RealtimeDecodeError(msg)
        segments, _ = model.transcribe(
            audio,
            task="transcribe",
            language="en",
            beam_size=5 if final else 1,
            vad_filter=False,
            condition_on_previous_text=False,
        )
        return "".join(segment.text for segment in segments).strip()

    def close(self) -> None:  # the model frees with the process
        self._model = None


def pcm16_wav_bytes(audio: np.ndarray) -> bytes:
    """float32 PCM → a 16 kHz mono s16le WAV container (in memory)."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        out.writeframes((audio * 32768.0).clip(-32768, 32767).astype("int16").tobytes())
    return buffer.getvalue()


class QwenRealtime:
    """Hindi realtime decodes over the M52H-verified llama-server contract."""

    def __init__(self, url: str, *, timeout_seconds: float = 30.0) -> None:
        self._url = url.rstrip("/") + "/v1/chat/completions"
        self._timeout = timeout_seconds

    def decode(self, audio: np.ndarray, *, final: bool) -> str:
        del final  # one decode quality: temperature 0, model self-reports
        # Duration-scaled token budget (M53 battery finding): a rare
        # generation loop on a ~20 s span once inflated a session by
        # ~180 repeated words. Real Hindi speech in this corpus runs
        # ~3.5 words/s ≈ ~10 tokens/s; 14 tokens/s is generous headroom
        # while structurally bounding what a loop can emit.
        seconds = len(audio) / SAMPLE_RATE
        max_tokens = max(96, min(1024, int(seconds * 14)))
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": base64.b64encode(pcm16_wav_bytes(audio)).decode("ascii"),
                                "format": "wav",
                            },
                        },
                        {"type": "text", "text": _ASR_PROMPT},
                    ],
                }
            ],
            "temperature": 0.0,
            "max_tokens": max_tokens,
            "cache_prompt": False,
        }
        request = urllib.request.Request(  # noqa: S310 — operator-configured internal URL
            self._url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310
                body = json.loads(response.read())
            raw = str(body["choices"][0]["message"]["content"])
        except Exception as exc:  # OSError, HTTPError, KeyError, JSON
            msg = "hindi realtime backend did not answer"
            raise RealtimeDecodeError(msg) from exc
        if _ASR_MARKER in raw:
            return raw.partition(_ASR_MARKER)[2].strip()
        return raw.strip()

    def probe(self) -> None:
        """Startup reachability check: an ENABLED deployment with an
        unreachable backend refuses to serve (the artifact-seeding law,
        applied to a network backend)."""
        health = self._url.rsplit("/v1/", 1)[0] + "/health"
        with urllib.request.urlopen(health, timeout=5) as response:  # noqa: S310
            if response.status != 200:
                msg = f"realtime hindi backend unhealthy: {response.status}"
                raise RealtimeDecodeError(msg)

    def close(self) -> None:
        """The server is operator-managed; nothing to release here."""
