"""Freeze smart-correction-en-hi@v1 → evidence/dataset.jsonl + manifest.

Run once; the manifest sha256 pins the frozen file. Re-running after a
row edit produces a DIFFERENT hash — which is the point: edits are a
new version, never a silent change.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from rows_en import ROWS_EN
from rows_hi import ROWS_HI

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"


def main() -> None:
    rows = []
    for language, source in (("en", ROWS_EN), ("hi", ROWS_HI)):
        for index, (category, noisy, gold, entities, flags) in enumerate(source, start=1):
            rows.append(
                {
                    "id": f"{language}-{index:03d}",
                    "language": language,
                    "category": category,
                    "noisy_input": noisy,
                    "gold_correction": gold,
                    "preserve_entities": entities,
                    "already_correct": "already_correct" in flags,
                    "meaning_trap": "meaning_trap" in flags,
                    "ambiguous": "ambiguous" in flags,
                    "source_type": "AUTHORED",
                }
            )
    EVIDENCE.mkdir(exist_ok=True)
    payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    (EVIDENCE / "dataset.jsonl").write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    by_language = Counter(row["language"] for row in rows)
    by_category = Counter(f"{row['language']}:{row['category']}" for row in rows)
    manifest = {
        "name": "smart-correction-en-hi",
        "version": "v1",
        "frozen": True,
        "sha256": digest,
        "rows": len(rows),
        "by_language": dict(by_language),
        "by_category": dict(sorted(by_category.items())),
        "flags": {
            "already_correct": sum(1 for r in rows if r["already_correct"]),
            "meaning_trap": sum(1 for r in rows if r["meaning_trap"]),
            "ambiguous": sum(1 for r in rows if r["ambiguous"]),
        },
        "source_types": {"AUTHORED": len(rows)},
        "notes": [
            "All rows AUTHORED for this benchmark in STT-noise style (lowercase, missing "
            "punctuation, spoken artifacts, spelled-out numbers); no public corpus rows in "
            "v1 (licensing review deferred to v2), no private/boss audio, no customer data.",
            "Roman-Hindi rows carry Devanagari gold: transliteration+cleanup is its own "
            "category, per the M56 spec.",
            "already_correct rows measure over-correction; meaning_trap rows are the "
            "protected-meaning gate; ambiguous rows prefer preservation.",
        ],
        "date": "2026-09-01",
    }
    (EVIDENCE / "dataset-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {k: manifest[k] for k in ("rows", "by_language", "sha256", "flags")}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
