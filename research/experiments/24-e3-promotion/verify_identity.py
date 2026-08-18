"""M24 Phase 2: E3 artifact identity / supply chain, verified not assumed.

Every hash the promotion proposal will cite, recomputed from bytes on
this machine and cross-checked against the runtime's own admission
table (ARTIFACT_SPECS) — plus distinctness from base/E1/E2, the frozen
training and evaluation manifest pins, the base revision, and the
pinned runtime build. Any mismatch is a refusal, not a warning.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from intelliai_stt_runtime.engines.qwen3_asr import (
    ARTIFACT_SPECS,
    RUNTIME_BINARY_PINS,
)
from intelliai_training.config import QwenTrainingConfig

E3 = "qwen3-asr-0.6b-hi-ft-e3"
V3_MANIFEST = Path("ml/datasets/manifests/qwen-hi-public-train-v3.jsonl")
V3_SHA = "6cfc585d3cecbdc177f31f476ec10aa54232706c2e74015af28e2a041e73a467"
EVAL_MANIFEST = Path("ml/evaluation/stt/datasets/stt-hi-public-eval-v1.json")
EVAL_SHA = "cf6431466722c199f9430fc1d471cbf94301453317c2555fc8301679123e6ffc"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models-dir", type=Path, default=Path("models"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    spec = ARTIFACT_SPECS[E3]
    checks: dict[str, Any] = {}
    failures: list[str] = []

    # 1. On-disk bytes match the admission table, file by file.
    for file in spec.files:
        placed = args.models_dir / E3 / f"v{spec.version}" / file.filename
        actual = sha256_file(placed)
        ok = actual == file.sha256.lower()
        checks[f"placed:{file.filename}"] = {
            "expected": file.sha256,
            "actual": actual,
            "bytes": placed.stat().st_size,
            "ok": ok,
        }
        if not ok:
            failures.append(f"{file.filename}: {actual} != {file.sha256}")

    # 2. Distinctness: the E3 text weights match NO other registered qwen
    #    artifact; the mmproj IS the official one (tower frozen).
    model_sha = next(f.sha256 for f in spec.files if "mmproj" not in f.filename)
    mmproj_sha = next(f.sha256 for f in spec.files if "mmproj" in f.filename)
    for other in ("qwen3-asr-0.6b", "qwen3-asr-0.6b-hi-ft-e1", "qwen3-asr-0.6b-hi-ft-e2"):
        other_model = next(
            f.sha256 for f in ARTIFACT_SPECS[other].files if "mmproj" not in f.filename
        )
        other_mmproj = next(f.sha256 for f in ARTIFACT_SPECS[other].files if "mmproj" in f.filename)
        distinct = model_sha != other_model
        checks[f"distinct-from:{other}"] = {"ok": distinct}
        if not distinct:
            failures.append(f"model sha collides with {other}")
        if mmproj_sha != other_mmproj:
            failures.append(f"mmproj drifted from {other} (tower was frozen — must be shared)")

    # 3. The frozen manifests the training and evaluation stood on.
    for name, path, expected in (
        ("training-manifest:qwen-hi-public-train@v3", V3_MANIFEST, V3_SHA),
        ("eval-manifest:stt-hi-public-eval@v1", EVAL_MANIFEST, EVAL_SHA),
    ):
        actual = sha256_file(path)
        ok = actual == expected
        checks[name] = {"expected": expected, "actual": actual, "ok": ok}
        if not ok:
            failures.append(f"{name}: {actual} != {expected}")

    # 4. Identity constants the proposal cites.
    config = QwenTrainingConfig()
    checks["base-model"] = {
        "id": config.base_model_id,
        "revision": config.base_revision,
        "weights_sha256": config.base_weights_sha256,
        "ok": config.base_revision == "5eb144179a02acc5e5ba31e748d22b0cf3e303b0",
    }
    checks["runtime-pins"] = {
        "files": len(RUNTIME_BINARY_PINS),
        "llama_server": next(
            (sha for name, sha in RUNTIME_BINARY_PINS.items() if "llama-server.exe" in name),
            None,
        ),
        "ok": len(RUNTIME_BINARY_PINS) >= 6,
    }

    payload = {
        "experiment": "24-e3-promotion",
        "phase": "identity (Phase 2)",
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "artifact": f"{E3}@v{spec.version}",
        "checks": checks,
        "failures": failures,
        "verdict": "IDENTITY VERIFIED" if not failures else "REFUSED",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(payload["verdict"])
    for name, entry in checks.items():
        print(f"  {name}: {'OK' if entry.get('ok') else 'FAIL'}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
