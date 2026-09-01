"""Launch the Smart Correction GPU backend (M57, staging only).

Serves the M56-selected correction model — Qwen3-4B-Instruct-2507
Q4_K_M (Apache-2.0) — through the SAME pinned llama.cpp b10344 CUDA
build the platform already trusts. Identity is byte-pinned before
anything starts:

* ``llama-server.exe`` / ``ggml-cuda.dll`` — the M52H/M55 pins.
* the GGUF artifact — sha256-pinned below (downloaded once from the
  unsloth GGUF conversion of the official Apache-2.0 release; adopting
  a different file is a reviewed edit here, never a swap on disk).

Runs on its OWN port so correction can never sit in the realtime
llama-server's queue (the M55 isolation design). 127.0.0.1 only;
nothing in any committed compose file starts this — the operator does,
exactly like the realtime GPU services.

    uv run python tools/correction/launch_correction_gpu.py [--port 8802]
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
MODEL: Final = REPO / "weights" / "research-smart-correction" / "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"

#: Byte-for-byte identity of the serving build + model.
PINS: Final = {
    BUILD_DIR / "llama-server.exe": (
        "b2ace4b8aed7c60e217fcaed8541850f4998539b8478880f1c3264387a0a8d97"
    ),
    BUILD_DIR / "ggml-cuda.dll": (
        "5ea989dcd77a312377af39c0da3245d5921695d105f2c30dbe8d2bf9ad90318c"
    ),
    MODEL: "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8802)
    parser.add_argument("--ctx", type=int, default=8192)
    args = parser.parse_args()

    for path, expected in PINS.items():
        if not path.exists():
            print(f"missing {path} — stage the pinned artifact first")  # noqa: T201
            return 2
        if _sha256(path) != expected:
            print(f"{path.name} does not match its pin; refusing an unpinned artifact")  # noqa: T201
            return 2

    argv = [
        str(BUILD_DIR / "llama-server.exe"),
        "-m",
        str(MODEL),
        "-c",
        str(args.ctx),
        "-ngl",
        "99",
        "--host",
        "127.0.0.1",
        "--port",
        str(args.port),
    ]
    print(f"launching pinned correction llama-server on 127.0.0.1:{args.port}")  # noqa: T201
    return subprocess.call(argv)  # noqa: S603 — fixed argv from verified pins


if __name__ == "__main__":
    sys.exit(main())
