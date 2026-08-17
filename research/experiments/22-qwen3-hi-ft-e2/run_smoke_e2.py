"""M22 Phase 8: E2 smoke — v2 data, negative targets, same machine.

Beyond the E1 smoke (load → freeze → collate → loss → backward → step →
checkpoint → reload → transcribe), this one verifies the NEGATIVE
representation end to end: the converted JSONL renders zxx rows as
exactly ``language None<asr_text>``, and the official collator
tokenizes a negative batch into a supervisable target (finite loss).
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path

from intelliai_training.config import QwenTrainingConfig
from intelliai_training.qwen_trainer import smoke_test


def e2_config(**overrides: object) -> QwenTrainingConfig:
    values: dict[str, object] = {
        "experiment": "qwen-e2-hi-sft",
        "manifest_path": "ml/datasets/manifests/qwen-hi-public-train-v2.jsonl",
        "manifest_sha256": "31e61c1cd6240177f4d88009254746beb091b9dfada5b00c4c1d683337e86708",
        "output_dir": "weights/qwen-e2-hi-sft",
        # Checkpoint FREQUENCY only (bookkeeping, not dynamics): 2.7x the
        # data means ~1,636 optimizer steps; every 300 keeps 6 checkpoints
        # spanning early/mid/late exactly like E1's 150-step cadence did.
        "save_steps": 300,
    }
    values.update(overrides)
    return QwenTrainingConfig.model_validate(values)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    config = e2_config()
    report = smoke_test(config, samples=8, steps=4, work_dir=args.work)

    # Negative-representation check on the ACTUAL converted rows.
    train_jsonl = args.work / "qwen-train.jsonl"
    rows = [json.loads(line) for line in train_jsonl.read_text(encoding="utf-8").splitlines()]
    negatives = [r for r in rows if r["text"] == "language None<asr_text>"]
    speech = [r for r in rows if r["text"].startswith("language Hindi<asr_text>")]
    if not negatives:
        msg = "converted corpus carries no negatives"
        raise RuntimeError(msg)
    if len(negatives) + len(speech) != len(rows):
        msg = "unexpected third row shape in the converted corpus"
        raise RuntimeError(msg)

    payload = {
        "experiment": "22-qwen3-hi-ft-e2",
        "phase": "smoke",
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "negative_rows_in_corpus": len(negatives),
        "speech_rows_in_corpus": len(speech),
        "report": report.model_dump(),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
