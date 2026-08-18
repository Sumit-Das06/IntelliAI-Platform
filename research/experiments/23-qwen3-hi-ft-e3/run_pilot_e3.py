"""M23 Phase 10: E3 pilot — the retention questions asked EARLY.

30 optimizer steps at the full E3 configuration, then the last
checkpoint answers what matters before funding the ~6 h run: does
Hindi still transcribe, does ENGLISH still transcribe (E2's failure),
does 1 s Hindi produce text (E2's other failure), and does silence
stay empty (E2's win)? If the pilot already shows the E2 failure
modes, the milestone says stop and inspect the composition — not burn
the full run.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

import numpy as np

from intelliai_training.audio_io import decode_to_float32
from intelliai_training.qwen_trainer import load_wrapper, train

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "21-qwen3-hi-finetuning"))
from english_regression import CLIPS, JFK_REFERENCE, fetch
from run_smoke_e3 import e3_config

RATE = 16_000


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    # Micro-batch 1 x grad-acc 16: the recorded E2 full-run shape (same
    # effective batch 16; the 2x8 pairing OOMed on ~30 s clip pairs).
    config = e3_config(
        output_dir="weights/qwen-e3-hi-sft-pilot",
        save_steps=15,
        log_steps=5,
        per_device_batch_size=1,
        gradient_accumulation=16,
    )
    record = train(config, max_steps=args.steps)

    checkpoints = sorted(
        Path(record.checkpoint_dir).glob("checkpoint-*/inferable"),
        key=lambda p: int(p.parent.name.split("-")[-1]),
    )
    qualitative: dict[str, object] = {}
    if checkpoints:
        wrapper = load_wrapper(checkpoints[-1], device_map="cuda:0")

        # Durations come from the frozen v3 manifest, keyed by audio path.
        duration_by_audio = {
            row["audio"]: row["duration_seconds"]
            for row in (
                json.loads(line)
                for line in Path(config.manifest_path).read_text(encoding="utf-8").splitlines()
            )
        }
        validation_rows = [
            json.loads(line)
            for line in (Path(config.output_dir) / "qwen-validation.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]

        def transcribe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
            probed = []
            for row in rows:
                result = wrapper.transcribe(str(Path(config.data_root) / row["audio"]))
                probed.append(
                    {
                        "audio": row["audio"],
                        "reference": row["text"],
                        "hypothesis": str(result[0].text) if result else "",
                    }
                )
            return probed

        hindi_rows = [
            r
            for r in validation_rows
            if r["text"].startswith("language Hindi<asr_text>")
            and duration_by_audio.get(r["audio"], 0) >= 2.0
        ][:3]
        english_rows = [
            r for r in validation_rows if r["text"].startswith("language English<asr_text>")
        ][:2]
        short_rows = [
            r
            for r in validation_rows
            if r["text"].startswith("language Hindi<asr_text>")
            and duration_by_audio.get(r["audio"], 99) < 2.0
        ][:2]
        qualitative["hindi_speech"] = transcribe_rows(hindi_rows)
        qualitative["english_speech"] = transcribe_rows(english_rows)
        qualitative["short_hindi_speech"] = transcribe_rows(short_rows)

        # JFK: real out-of-corpus English, the M21 pinned tripwire clip.
        jfk_id, jfk_url, jfk_sha = CLIPS[0]
        jfk = fetch(jfk_url, jfk_sha, args.work / Path(jfk_url).name)
        result = wrapper.transcribe(str(jfk))
        jfk_text = str(result[0].text) if result else ""
        qualitative["jfk_english"] = {
            "id": jfk_id,
            "reference": JFK_REFERENCE,
            "hypothesis": jfk_text,
            "latin_letters": any("a" <= ch.lower() <= "z" for ch in jfk_text),
            "devanagari": any("ऀ" <= ch <= "ॿ" for ch in jfk_text),
        }

        # 1 s Hindi window (the M22 battery's anchor) + digital silence.
        speech = decode_to_float32(
            Path(config.data_root) / "indicvoices/hindi/train/indicvoices-hindi-train-0-000005.flac"
        )
        result = wrapper.transcribe((speech[RATE : RATE * 2], RATE))
        one_second = str(result[0].text) if result else ""
        qualitative["one_second_hindi"] = {
            "empty": not one_second.strip(),
            "devanagari": any("ऀ" <= ch <= "ॿ" for ch in one_second),
            "text_head": one_second[:60],
        }
        silence = np.zeros(RATE * 10, dtype=np.float32)
        result = wrapper.transcribe((silence, RATE))
        silence_text = str(result[0].text) if result else ""
        qualitative["silence_10s"] = {
            "empty": not silence_text.strip(),
            "text_head": silence_text[:60],
        }

    payload = {
        "experiment": "23-qwen3-hi-ft-e3",
        "phase": "pilot",
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "record": record.model_dump(),
        "qualitative": qualitative,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
