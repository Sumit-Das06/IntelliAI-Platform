"""M23 Phase 9: E3 smoke — v3 retention-mix data, same machine, same laws.

Beyond the E2 smoke (load → freeze → collate → loss → backward → step →
checkpoint → reload → transcribe), this one verifies the RETENTION-MIX
representation end to end: the converted JSONL renders exactly three
row shapes — Hindi speech, English speech (`language English<asr_text>`),
and the zxx negatives (`language None<asr_text>`) — and the official
collator tokenizes a mixed batch into a supervisable target.
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path

from intelliai_training.config import QwenTrainingConfig
from intelliai_training.qwen_trainer import smoke_test


def e3_config(**overrides: object) -> QwenTrainingConfig:
    """The E2 configuration verbatim; ONLY the data pin changes (E3 law)."""
    values: dict[str, object] = {
        "experiment": "qwen-e3-hi-sft",
        "manifest_path": "ml/datasets/manifests/qwen-hi-public-train-v3.jsonl",
        "manifest_sha256": "6cfc585d3cecbdc177f31f476ec10aa54232706c2e74015af28e2a041e73a467",
        "output_dir": "weights/qwen-e3-hi-sft",
        # Same cadence bookkeeping as E2: ~1,843 optimizer steps at
        # effective batch 16 over 2 epochs; every 300 keeps 6-7
        # checkpoints spanning early/mid/late.
        "save_steps": 300,
    }
    values.update(overrides)
    return QwenTrainingConfig.model_validate(values)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    config = e3_config()
    report = smoke_test(config, samples=8, steps=4, work_dir=args.work)

    # Representation check on the ACTUAL converted rows: exactly three
    # shapes, counted, nothing else.
    train_jsonl = args.work / "qwen-train.jsonl"
    rows = [json.loads(line) for line in train_jsonl.read_text(encoding="utf-8").splitlines()]
    negatives = [r for r in rows if r["text"] == "language None<asr_text>"]
    hindi = [r for r in rows if r["text"].startswith("language Hindi<asr_text>")]
    english = [r for r in rows if r["text"].startswith("language English<asr_text>")]
    if not negatives or not english or not hindi:
        msg = (
            f"converted corpus is missing a retention-mix ingredient: "
            f"hindi={len(hindi)} english={len(english)} negatives={len(negatives)}"
        )
        raise RuntimeError(msg)
    if len(negatives) + len(hindi) + len(english) != len(rows):
        msg = "unexpected fourth row shape in the converted corpus"
        raise RuntimeError(msg)

    payload = {
        "experiment": "23-qwen3-hi-ft-e3",
        "phase": "smoke",
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "hindi_rows_in_corpus": len(hindi),
        "english_rows_in_corpus": len(english),
        "negative_rows_in_corpus": len(negatives),
        "report": report.model_dump(),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
