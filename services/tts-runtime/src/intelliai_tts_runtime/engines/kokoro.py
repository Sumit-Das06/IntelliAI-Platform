"""Kokoro engine — the first foundation synthesis model, as an adapter.

Kokoro-82M (Apache-2.0, verified 2026-08-03 — M3 design review §8) behind
the same ``SynthesisEngine`` face as the reference engine: canonical text
and an engine voice reference in, canonical PCM out. English only in this
first integration, by license verdict, not by accident.

**License firewall.** ``misaki[en]`` transitively installs the GPL
espeak-ng wrapper chain (phonemizer-fork, espeakng-loader), and the
``kokoro`` package's ``__init__`` imports it unconditionally via its
pipeline module. The verdict approves English ONLY espeak-free, so before
any kokoro import this module registers a poison stub for
``misaki.espeak``: the GPL chain — Python or native — never enters the
process (proven empirically: zero phonemizer/espeak modules in
``sys.modules`` after a full model load and synthesis, asserted by the
local tier), and any future code path that touches espeak fails loudly
with a license error instead of silently linking. We deliberately bypass
``KPipeline`` for the same reasons: it constructs the espeak fallback and
downloads from the Hugging Face hub at runtime — this engine loads ONLY
hash-verified files from the ArtifactStore.

Chunking: the model accepts ~510 phonemes per pass; text is split on
sentence boundaries (word-wrapped when a sentence is huge) and the PCM is
concatenated. A smarter chunking strategy is production-validation
business (M3 step 7), registered debt — not silently absent.
"""

from __future__ import annotations

import re
import sys
import types
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Final

from intelliai_runtime_core import ArtifactFile, ArtifactSpec
from intelliai_tts_runtime.engines.base import SynthesizedAudio

ARTIFACT_ID: Final = "kokoro-82m"
SAMPLE_RATE_HZ: Final = 24_000

_HF: Final = "https://huggingface.co/hexgrad/Kokoro-82M/resolve/main"

# SHA-256 pins verified at source 2026-08-03: LFS oids from the Hugging
# Face API for the weights and voice packs; config.json (non-LFS) hashed
# from the downloaded file. Voice assets are separate hash-pinned files —
# never code, never repo content.
KOKORO_FILES: Final = ArtifactSpec(
    artifact=ARTIFACT_ID,
    version=1,
    files=(
        ArtifactFile(
            filename="kokoro-v1_0.pth",
            url=f"{_HF}/kokoro-v1_0.pth",
            sha256="496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4",
        ),
        ArtifactFile(
            filename="config.json",
            url=f"{_HF}/config.json",
            sha256="5abb01e2403b072bf03d04fde160443e209d7a0dad49a423be15196b9b43c17f",
        ),
        ArtifactFile(
            filename="af_heart.pt",
            url=f"{_HF}/voices/af_heart.pt",
            sha256="0ab5709b8ffab19bfd849cd11d98f75b60af7733253ad0d67b12382a102cb4ff",
        ),
        ArtifactFile(
            filename="am_michael.pt",
            url=f"{_HF}/voices/am_michael.pt",
            sha256="9a443b79a4b22489a5b0ab7c651a0bcd1a30bef675c28333f06971abbd47bd37",
        ),
    ),
)

# engine voice reference -> voice-pack file within the verified artifact
_VOICE_FILES: Final = {"af_heart": "af_heart.pt", "am_michael": "am_michael.pt"}

_MAX_PHONEMES: Final = 510  # the model's hard per-pass input limit
_CHUNK_CHARS: Final = 300  # keeps sentence chunks safely under it
_SENTENCE_SPLIT: Final = re.compile(r"(?<=[.!?;:])\s+")


def _install_license_firewall() -> None:
    """Poison-stub misaki.espeak BEFORE kokoro's package init can import
    the GPL chain. Idempotent; introspection-polite (dunder lookups get
    AttributeError so hasattr()-style probes behave normally)."""
    if "misaki.espeak" in sys.modules:
        return
    stub = types.ModuleType("misaki.espeak")

    def _banned(name: str) -> None:
        if name.startswith("__"):
            raise AttributeError(name)
        msg = "espeak is banned by license policy (M3 design review §8)"
        raise RuntimeError(msg)

    stub.__getattr__ = _banned  # type: ignore[method-assign]
    sys.modules["misaki.espeak"] = stub


def _chunks(text: str) -> Iterator[str]:
    for sentence in _SENTENCE_SPLIT.split(text):
        stripped = sentence.strip()
        if not stripped:
            continue
        if len(stripped) <= _CHUNK_CHARS:
            yield stripped
            continue
        piece: list[str] = []
        length = 0
        for word in stripped.split():
            if length + len(word) + 1 > _CHUNK_CHARS and piece:
                yield " ".join(piece)
                piece, length = [], 0
            piece.append(word)
            length += len(word) + 1
        if piece:
            yield " ".join(piece)


def _bounded_phonemes(phonemes: str) -> list[str]:
    """Defensive guard: no phoneme string ever exceeds the model limit."""
    if len(phonemes) <= _MAX_PHONEMES:
        return [phonemes]
    middle = len(phonemes) // 2
    split = phonemes.rfind(" ", 0, middle)
    if split <= 0:
        split = middle
    return _bounded_phonemes(phonemes[:split]) + _bounded_phonemes(phonemes[split:].lstrip())


class KokoroEngine:
    """Thin adapter: one loaded model + G2P + verified voice packs,
    stateless beyond them."""

    def __init__(self, model: Any, g2p: Any, voice_packs: dict[str, Any]) -> None:
        self._model = model
        self._g2p = g2p
        self._voice_packs = voice_packs

    def synthesize(self, text: str, voice: str, speed: float | None) -> SynthesizedAudio:
        import torch

        pack = self._voice_packs[voice]
        pcm = bytearray()
        with torch.inference_mode():
            for chunk in _chunks(text):
                phonemes, _ = self._g2p(chunk)
                phonemes = phonemes.strip()
                if not phonemes:
                    continue
                for piece in _bounded_phonemes(phonemes):
                    ref_s = pack[len(piece) - 1]
                    audio = self._model(piece, ref_s, speed if speed is not None else 1.0)
                    pcm += (audio.clamp(-1.0, 1.0) * 32767.0).to(torch.int16).numpy().tobytes()
        return SynthesizedAudio(pcm=bytes(pcm), sample_rate_hz=SAMPLE_RATE_HZ)

    def close(self) -> None:
        self._voice_packs.clear()


def load_kokoro(local_dir: Path | None) -> KokoroEngine:
    """Slot loader: verified artifact directory -> a loaded engine.

    Everything model-specific happens here — library imports (lazy, so the
    base service never needs them), weight loading from OUR verified store
    (never the Hugging Face hub), voice-pack loading, and the espeak-free
    G2P configuration (misaki-native English, fallback disabled)."""
    if local_dir is None:
        msg = "the kokoro engine requires a verified artifact directory"
        raise ValueError(msg)
    _install_license_firewall()
    import torch
    from kokoro.model import KModel
    from misaki import en

    model = KModel(
        config=str(local_dir / "config.json"), model=str(local_dir / "kokoro-v1_0.pth")
    ).eval()
    g2p = en.G2P(trf=False, british=False, fallback=None)
    voice_packs = {
        ref: torch.load(local_dir / filename, weights_only=True)
        for ref, filename in _VOICE_FILES.items()
    }
    return KokoroEngine(model=model, g2p=g2p, voice_packs=voice_packs)
