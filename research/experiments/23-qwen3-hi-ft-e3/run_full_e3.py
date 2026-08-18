"""M23 Phase 11: the funded E3 run — 2 epochs over qwen-hi-public-train@v3.

The E2 configuration held constant (effective batch 16 as micro-batch
1 x grad-acc 16 — the recorded E2 full-run shape — lr 1e-5 linear + 3%
warmup, Adafactor, bf16, frozen tower, seed 20260817, checkpoints
every 300 steps); the ONLY experimental variable is the data: v2's
27.3 h verbatim + the 5.92% English retention slice + the bounded
[0.5 s, 2.0 s) short-Hindi slice.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

from intelliai_training.qwen_trainer import train

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_smoke_e3 import e3_config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    record = train(e3_config(per_device_batch_size=1, gradient_accumulation=16))
    payload = {
        "experiment": "23-qwen3-hi-ft-e3",
        "phase": "full",
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "record": record.model_dump(),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        k: payload["record"][k]
        for k in (
            "steps_completed",
            "final_train_loss",
            "validation_history",
            "peak_vram_mib",
            "train_duration_seconds",
        )
    }
    print(json.dumps(summary, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
