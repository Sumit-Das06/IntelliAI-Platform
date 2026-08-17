"""M21 Phase 8: the funded full run — 2 epochs over hi-public-train@v1.

Same configuration the pilot validated (effective batch 16, Adafactor,
frozen tower, bf16); checkpoints + validation every 150 optimizer
steps; the run record (config, hashes, environment, loss histories,
VRAM, duration) is the reproducibility artifact.
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path

from intelliai_training.config import QwenTrainingConfig
from intelliai_training.qwen_trainer import train


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    config = QwenTrainingConfig()  # the committed defaults ARE the run config
    record = train(config)
    payload = {
        "experiment": "21-qwen3-hi-finetuning",
        "phase": "full",
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "record": record.model_dump(),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                k: payload["record"][k]
                for k in (
                    "steps_completed",
                    "final_train_loss",
                    "validation_history",
                    "peak_vram_mib",
                    "train_duration_seconds",
                )
            },
            ensure_ascii=False,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
