"""No-speech negatives — the M22 answer to the E1 silence regression.

E1 trained on 10 h of pure speech and learned that SOMETHING must always
be said; on digital silence it voiced a repeated token. These negatives
teach the opposite lesson with the OFFICIAL representation: a ``zxx``
candidate with an empty transcript, which the Qwen training conversion
renders as ``language None<asr_text>`` — the exact string the pinned
base model emits on silence (committed 15E probe evidence).

Three deterministic kinds, seeded and reproducible byte-for-byte:

- ``silence``: digital zeros (the exact observed failure input);
- ``noise``: low-amplitude gaussian noise (quiet-room hiss);
- ``derived``: the quietest window cut from an approved ingested clip
  (real room tone; parent clip id recorded in the candidate notes).

Ratio discipline lives with the caller: these are seasoning, not diet —
M22 starts at ~2% of rows and records the number.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from intelliai_datasets.samples import CandidateSample

SAMPLE_RATE = 16_000
#: Amplitude of the noise negatives: about -50 dBFS hiss, far below speech.
NOISE_AMPLITUDE = 0.003
#: Derived-window shape: long enough to be a real training example,
#: quiet enough to carry no intelligible speech.
DERIVED_WINDOW_SECONDS = 4.0
DERIVED_MAX_MEAN_ABS = 0.004


def _write_flac(path: Path, samples: Any) -> tuple[str, float]:
    import soundfile

    path.parent.mkdir(parents=True, exist_ok=True)
    soundfile.write(str(path), samples, SAMPLE_RATE, subtype="PCM_16", format="FLAC")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest, len(samples) / SAMPLE_RATE


def generate_negatives(
    *,
    data_root: Path,
    out_candidates: Path,
    silence_count: int,
    noise_count: int,
    derived_count: int,
    derived_pool: list[CandidateSample],
    seed: int,
) -> list[CandidateSample]:
    """Write negative audio + a candidates file; return the candidates.

    Deterministic: the seed fixes every generated sample; the derived
    pool is scanned in ascending sha256 order and each accepted parent
    contributes at most one window.
    """
    import numpy as np
    import soundfile

    def decode_mono(path: Path, rate: int) -> Any:
        data, actual = soundfile.read(str(path), dtype="float32", always_2d=True)
        if actual != rate:
            msg = f"{path}: {actual} Hz, expected {rate} (ingested audio is canonical)"
            raise ValueError(msg)
        return data.mean(axis=1)

    rng = np.random.default_rng(seed)
    candidates: list[CandidateSample] = []
    base = data_root / "negatives" / "hi-nospeech"

    for index in range(silence_count):
        seconds = float(rng.integers(3, 11))
        samples = np.zeros(int(seconds * SAMPLE_RATE), dtype=np.float32)
        path = base / f"silence-{index:03d}.flac"
        digest, duration = _write_flac(path, samples)
        candidates.append(
            _candidate(
                f"neg-silence-{index:03d}",
                path,
                data_root,
                digest,
                duration,
                source="negatives-synthetic",
                notes="digital silence",
            )
        )

    for index in range(noise_count):
        seconds = float(rng.integers(3, 11))
        samples = (rng.standard_normal(int(seconds * SAMPLE_RATE)) * NOISE_AMPLITUDE).astype(
            "float32"
        )
        path = base / f"noise-{index:03d}.flac"
        digest, duration = _write_flac(path, samples)
        candidates.append(
            _candidate(
                f"neg-noise-{index:03d}",
                path,
                data_root,
                digest,
                duration,
                source="negatives-synthetic",
                notes="low-amplitude gaussian noise",
            )
        )

    taken = 0
    for parent in sorted(derived_pool, key=lambda s: s.sha256):
        if taken >= derived_count:
            break
        wave = decode_mono(data_root / parent.path, SAMPLE_RATE)
        window = int(DERIVED_WINDOW_SECONDS * SAMPLE_RATE)
        if len(wave) < window:
            continue
        # Quietest window at 0.5 s hop — argmin of mean |x|, ties earliest.
        hop = SAMPLE_RATE // 2
        best_start, best_energy = None, None
        for start in range(0, len(wave) - window + 1, hop):
            energy = float(abs(wave[start : start + window]).mean())
            if best_energy is None or energy < best_energy:
                best_start, best_energy = start, energy
        if best_start is None or best_energy is None or best_energy > DERIVED_MAX_MEAN_ABS:
            continue
        path = base / f"derived-{taken:03d}.flac"
        digest, duration = _write_flac(path, wave[best_start : best_start + window])
        candidates.append(
            _candidate(
                f"neg-derived-{taken:03d}",
                path,
                data_root,
                digest,
                duration,
                source="negatives-indicvoices-derived",
                notes=f"quietest {DERIVED_WINDOW_SECONDS:.0f}s window of {parent.id}",
            )
        )
        taken += 1

    out_candidates.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_revision": f"generated:seed={seed}",
        "candidates": [c.model_dump() for c in candidates],
        "ingestion_problems": [],
    }
    out_candidates.write_bytes(
        (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    return candidates


def _candidate(
    sample_id: str,
    path: Path,
    data_root: Path,
    digest: str,
    duration: float,
    *,
    source: str,
    notes: str,
) -> CandidateSample:
    return CandidateSample(
        id=sample_id,
        path=path.relative_to(data_root).as_posix(),
        sha256=digest,
        duration_seconds=round(duration, 3),
        sample_rate_hz=SAMPLE_RATE,
        channels=1,
        language="zxx",
        text="",
        speaker_id=None,
        split="train",
        source=source,
        license="synthetic" if source == "negatives-synthetic" else "CC-BY-4.0",
        notes=notes,
    )
