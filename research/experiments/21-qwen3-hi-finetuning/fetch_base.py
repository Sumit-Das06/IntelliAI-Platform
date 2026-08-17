"""Fetch the pinned base-model snapshot, riding out flaky DNS.

Each retry resumes the partial download; the loop gives a flapping
resolver up to ~30 minutes to deliver the ~2 GB snapshot before giving
up loudly.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from intelliai_training.config import QwenTrainingConfig
from intelliai_training.qwen_trainer import snapshot_base_model


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=30)
    args = parser.parse_args()

    config = QwenTrainingConfig()
    last_error: Exception | None = None
    for attempt in range(1, args.attempts + 1):
        try:
            path = snapshot_base_model(config, cache_dir=args.work / "hf-cache")
        except Exception as error:
            last_error = error
            print(f"attempt {attempt}: {type(error).__name__}; retrying in 60s", flush=True)
            time.sleep(60)
        else:
            # Verify the full weights hash ONCE here; every later load
            # trusts presence + pinned size (snapshot_base_model).
            from intelliai_training.manifest import sha256_file

            digest = sha256_file(path / "model.safetensors")
            if digest != config.base_weights_sha256:
                print(f"HASH MISMATCH: {digest} != pinned {config.base_weights_sha256}")
                return 1
            print(f"snapshot complete and hash-verified: {path}", flush=True)
            return 0
    print(f"giving up after {args.attempts} attempts: {last_error}", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
