"""M22 Phase 9: E2 pilot — stability + the silence lesson, early.

30 optimizer steps at the full E2 configuration, then the last
checkpoint answers the questions that matter before funding the run:
does Hindi still transcribe, and what does the model now do with pure
digital silence? (E1's pilot could not ask the second question — its
corpus had no negatives to learn from.)
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

import numpy as np

from intelliai_training.qwen_trainer import load_wrapper, train

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_smoke_e2 import e2_config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    config = e2_config(
        output_dir="weights/qwen-e2-hi-sft-pilot",
        save_steps=15,
        log_steps=5,
    )
    record = train(config, max_steps=args.steps)

    checkpoints = sorted(
        Path(record.checkpoint_dir).glob("checkpoint-*/inferable"),
        key=lambda p: int(p.parent.name.split("-")[-1]),
    )
    qualitative: dict[str, object] = {}
    if checkpoints:
        wrapper = load_wrapper(checkpoints[-1], device_map="cuda:0")
        validation_rows = [
            json.loads(line)
            for line in (Path(config.output_dir) / "qwen-validation.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        speech_rows = [r for r in validation_rows if "None<asr_text>" not in r["text"]][:3]
        transcriptions = []
        for row in speech_rows:
            result = wrapper.transcribe(str(Path(config.data_root) / row["audio"]))
            transcriptions.append(
                {
                    "audio": row["audio"],
                    "reference": row["text"],
                    "hypothesis": str(result[0].text) if result else "",
                }
            )
        qualitative["speech"] = transcriptions

        silence = np.zeros(16000 * 10, dtype=np.float32)
        result = wrapper.transcribe((silence, 16000))
        silence_text = str(result[0].text) if result else ""
        qualitative["silence_10s"] = {
            "empty": not silence_text.strip(),
            "text_head": silence_text[:60],
        }

    payload = {
        "experiment": "22-qwen3-hi-ft-e2",
        "phase": "pilot",
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "record": record.model_dump(),
        "qualitative": qualitative,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2)[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
