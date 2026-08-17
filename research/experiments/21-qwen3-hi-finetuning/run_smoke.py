"""M21 Phase 5: the Qwen SFT smoke test on THIS machine's RTX 5070.

Proves, before any real compute is funded: pinned-revision snapshot →
wrapper load → audio-tower freeze → real-manifest collation → loss →
backward → optimizer step → VRAM ceiling → checkpoint save → wrapper
reload → one real transcription from the reloaded checkpoint.
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path

from intelliai_training.config import QwenTrainingConfig
from intelliai_training.qwen_trainer import smoke_test


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--grad-acc", type=int, default=2)
    parser.add_argument("--no-freeze", action="store_true")
    args = parser.parse_args()

    config = QwenTrainingConfig(
        per_device_batch_size=args.batch_size,
        gradient_accumulation=args.grad_acc,
        freeze_audio_encoder=not args.no_freeze,
    )
    report = smoke_test(config, samples=args.samples, steps=args.steps, work_dir=args.work)
    payload = {
        "experiment": "21-qwen3-hi-finetuning",
        "phase": "smoke",
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "freeze_audio_encoder": not args.no_freeze,
        "report": report.model_dump(),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
