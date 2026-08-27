"""Launch the Hindi realtime GPU backend (M52H-verified, staging only).

Serves the UNCHANGED production E3 GGUF through llama.cpp b10344
(7a20b417f) with the CUDA backend. Identity is pinned byte-for-byte
before anything starts:

* ``llama-server.exe`` — **the exact same binary as the production CPU
  pin** (engines/qwen3_asr.py RUNTIME_BINARY_PINS, win32): the b10344
  release ships one server executable; the CUDA capability arrives as
  a backend DLL beside it.
* ``ggml-cuda.dll`` — pinned from the official
  ``llama-b10344-bin-win-cuda-13.3-x64.zip`` (M52H, hardware.json
  records the zip SHAs).

Refuses to start on any drift — adopting a new build is a reviewed
edit here, never a swap on disk. Production is untouched: this serves
127.0.0.1 only and nothing in any compose file references it.

    uv run python tools/realtime/launch_qwen_gpu.py [--port 8797]
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Final

REPO: Final = Path(__file__).resolve().parents[2]
BUILD_DIR: Final = REPO / "weights" / "llama-cuda-b10344"
MODEL_DIR: Final = REPO / "models" / "qwen3-asr-0.6b-hi-ft-e3" / "v1"

#: Byte-for-byte identity of the serving build (see module docstring).
PINS: Final = {
    "llama-server.exe": "b2ace4b8aed7c60e217fcaed8541850f4998539b8478880f1c3264387a0a8d97",
    "ggml-cuda.dll": "5ea989dcd77a312377af39c0da3245d5921695d105f2c30dbe8d2bf9ad90318c",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8797)
    parser.add_argument("--ctx", type=int, default=4096)
    args = parser.parse_args()

    for filename, expected in PINS.items():
        candidate = BUILD_DIR / filename
        if not candidate.exists():
            print(f"missing {candidate} — stage the M52H CUDA build into {BUILD_DIR}")  # noqa: T201
            return 2
        actual = _sha256(candidate)
        if actual != expected:
            print(f"{filename} does not match its pin; refusing an unpinned build")  # noqa: T201
            return 2
    model = MODEL_DIR / "Qwen3-ASR-0.6B-Q8_0.gguf"
    mmproj = MODEL_DIR / "mmproj-Qwen3-ASR-0.6B-Q8_0.gguf"
    if not model.exists() or not mmproj.exists():
        print(f"E3 artifact missing under {MODEL_DIR} — run 'make seed-models' first")  # noqa: T201
        return 2

    argv = [
        str(BUILD_DIR / "llama-server.exe"),
        "-m",
        str(model),
        "--mmproj",
        str(mmproj),
        "-c",
        str(args.ctx),
        "-ngl",
        "99",
        "--host",
        "127.0.0.1",
        "--port",
        str(args.port),
    ]
    print(f"launching pinned CUDA llama-server on 127.0.0.1:{args.port}")  # noqa: T201
    return subprocess.call(argv)  # noqa: S603 — fixed argv from verified pins


if __name__ == "__main__":
    sys.exit(main())
