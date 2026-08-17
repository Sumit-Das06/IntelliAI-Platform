"""M22 Phase 10: the funded E2 run — 2 epochs over qwen-hi-public-train@v2.

The E1 configuration held constant (effective batch 16, lr 1e-5 linear
+ 3% warmup, Adafactor, bf16, frozen tower, seed 20260817); the ONLY
experimental variables are the data (10.0 h dirty -> 27.3 h cleaned +
negatives) and the checkpoint cadence bookkeeping (every 300 steps for
the same early/mid/late coverage over ~1,636 steps).
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

from intelliai_training.qwen_trainer import train

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_smoke_e2 import e2_config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    # Micro-batch 1 x grad-acc 16: SAME effective batch 16 as E1. The
    # first attempt (2x8) OOMed at step 378 when v2's longer
    # conversational clips paired two ~30 s items in one batch — the
    # logits tensor for such a pair alone approaches a gibibyte. One
    # item per forward caps the worst case; the optimizer sees the
    # identical accumulation. Recorded here, not silently.
    record = train(e2_config(per_device_batch_size=1, gradient_accumulation=16))
    payload = {
        "experiment": "22-qwen3-hi-ft-e2",
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
