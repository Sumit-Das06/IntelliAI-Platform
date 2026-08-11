"""Decode stored original audio into 16 kHz mono float32 for training.

WAV/FLAC decode via soundfile (libsndfile); M4A via the ffmpeg boundary
— the same division of labor the ingestion probe uses. Resampling to
the canonical 16 kHz is ffmpeg's job in the serving pipeline; training
receives the same canonical form so features match serving.

Heavy imports are lazy: this module is importable without the `train`
extra; only calling decode requires it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

CANONICAL_RATE = 16_000


def decode_to_float32(path: Path) -> Any:
    """Return a 1-D float32 numpy array at 16 kHz mono."""
    import numpy as np

    suffix = path.suffix.lower()
    if suffix in (".wav", ".flac"):
        import soundfile

        data, rate = soundfile.read(str(path), dtype="float32", always_2d=True)
        mono = data.mean(axis=1)
        if rate == CANONICAL_RATE:
            return np.ascontiguousarray(mono)
        return _ffmpeg_decode(path)  # resample through the one media boundary
    return _ffmpeg_decode(path)


def _ffmpeg_decode(path: Path) -> Any:
    import numpy as np

    result = subprocess.run(  # noqa: S603 — fixed argv; ffmpeg is the media boundary
        [  # noqa: S607 — PATH lookup deliberate, same as the serving pipeline
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "-ac",
            "1",
            "-ar",
            str(CANONICAL_RATE),
            "pipe:1",
        ],
        capture_output=True,
        timeout=120,
        check=True,
    )
    return np.frombuffer(result.stdout, dtype=np.float32).copy()
