"""M29A — baseline predictors: NO-OP and SIMPLE RULES (research instruments).

Reads the harness inputs file (id -> punctuation-stripped input text) and
writes one predictions file per system. No repo package imports — these run
in any Python. The scoring side (intelliai_evaluation.punctuation) judges
the outputs; nothing here touches product code.

Systems:
  no-op  — output == input. The current-production floor: F1 must be 0.
  rules  — the MINIMUM deterministic rules worth measuring:
             * one final sentence-ender per text:
                 "?" when the text starts with a Hindi interrogative word,
                 "।" when the text contains Devanagari,
                 "." otherwise (Latin-only text)
           Nothing else: no internal boundaries, no commas. The point is to
           measure how far trivial determinism goes, not to build a restorer.

Run with PYTHONIOENCODING=utf-8.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

QUESTION_STARTERS = {
    "क्या",
    "कौन",
    "कब",
    "कहाँ",
    "कहां",
    "क्यों",
    "कैसे",
    "किसने",
    "किसका",
    "किसकी",
    "किसके",
    "कितना",
    "कितने",
    "कितनी",
}


def has_devanagari(text: str) -> bool:
    return any("ऀ" <= ch <= "ॿ" for ch in text)


def rules_restore(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return text
    words = stripped.split()
    if words[0] in QUESTION_STARTERS:
        return stripped + "?"
    if has_devanagari(stripped):
        return stripped + "।"
    return stripped + "."


def main() -> None:
    inputs_path = HERE / "harness" / "inputs.json"
    inputs = json.loads(inputs_path.read_text(encoding="utf-8"))
    rows = inputs["rows"]

    for system, restore in (("no-op", lambda t: t), ("rules", rules_restore)):
        predictions = [{"id": r["id"], "output_text": restore(r["input_text"])} for r in rows]
        out = HERE / "harness" / f"predictions-{system}.json"
        out.write_text(
            json.dumps(
                {
                    "experiment": "29a-hindi-punctuation-eval",
                    "system": system,
                    "dataset": inputs["dataset"],
                    "dataset_sha256": inputs["dataset_sha256"],
                    "predictions": predictions,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"{system}: {len(predictions)} predictions -> {out.name}")


if __name__ == "__main__":
    sys.exit(main())
