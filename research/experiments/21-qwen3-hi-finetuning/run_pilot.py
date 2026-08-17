"""M21 Phase 7: a bounded pilot before the full run is funded.

30 optimizer steps at the FULL run's configuration (effective batch 16,
Adafactor, frozen tower), checkpoints + validation every 15 steps, then
a qualitative gate: the last inferable checkpoint transcribes three
validation clips — eyes on repetition, malformed output, language loss —
beside the loss numbers.
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path

from intelliai_training.config import QwenTrainingConfig
from intelliai_training.qwen_trainer import load_wrapper, train


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    config = QwenTrainingConfig(
        output_dir="weights/qwen-e1-hi-sft-pilot",
        save_steps=15,
        log_steps=5,
    )
    record = train(config, max_steps=args.steps)

    # Qualitative gate on the newest inferable checkpoint.
    checkpoints = sorted(
        Path(record.checkpoint_dir).glob("checkpoint-*/inferable"),
        key=lambda p: int(p.parent.name.split("-")[-1]),
    )
    transcriptions: list[dict[str, str]] = []
    if checkpoints:
        wrapper = load_wrapper(checkpoints[-1])
        validation_rows = [
            json.loads(line)
            for line in (Path(config.output_dir) / "qwen-validation.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()[:3]
        ]
        for row in validation_rows:
            result = wrapper.transcribe(str(Path(config.data_root) / row["audio"]))
            hypothesis = result[0].text if result else ""
            transcriptions.append(
                {"audio": row["audio"], "reference": row["text"], "hypothesis": str(hypothesis)}
            )

    payload = {
        "experiment": "21-qwen3-hi-finetuning",
        "phase": "pilot",
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "record": record.model_dump(),
        "qualitative": transcriptions,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
