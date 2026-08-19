"""M28 — punctuated-Hindi data source probe (text-only, no audio, read-only).

Measures the punctuation style of candidate reference sources for a future
"Hindi Punctuation Evaluation v1" set, WITHOUT downloading audio and WITHOUT
touching any frozen artifact. Sources probed:

  1. FLEURS hi_in test split transcripts (google/fleurs, CC-BY-4.0) — the
     same source family M23 already approved for the English retention slice.
     Only the ~220 KB test.tsv text file is fetched.
  2. Our own corpus ingestion behavior: the datasets pipeline PRESERVES
     punctuation (pinned by ml/datasets/tests/test_validate.py
     test_case_and_punctuation_survive), so the zero-punctuation Hindi rows
     reflect the SOURCES (IndicVoices/Kathbath), not our processing.

Evidence: punctuated-sources.json. Run with PYTHONIOENCODING=utf-8.
"""

from __future__ import annotations

import csv
import io
import json
import unicodedata
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent / "punctuated-sources.json"
TSV_URL = "https://huggingface.co/datasets/google/fleurs/resolve/main/data/hi_in/test.tsv"


def stats(texts: list[str]) -> dict:
    n = len(texts)
    marks = {
        "danda": "।",
        "comma": ",",
        "question_mark": "?",
        "exclamation": "!",
        "full_stop": ".",
        "colon": ":",
        "semicolon": ";",
    }
    any_rows = sum(1 for t in texts if any(unicodedata.category(c).startswith("P") for c in t))
    return {
        "rows": n,
        "rows_with_any_punctuation": any_rows,
        "pct_rows_with_any_punctuation": round(100 * any_rows / n, 2) if n else None,
        "per_mark_total_count": {k: sum(t.count(m) for t in texts) for k, m in marks.items()},
        "per_mark_rows_containing": {k: sum(1 for t in texts if m in t) for k, m in marks.items()},
    }


req = urllib.request.Request(TSV_URL, headers={"User-Agent": "intelliai-research/1.0"})
with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310 — fixed https literal
    data = r.read().decode("utf-8")
rows = [row for row in csv.reader(io.StringIO(data), delimiter="\t") if len(row) > 3]
raw = [row[2] for row in rows]
norm = [row[3] for row in rows]

evidence = {
    "experiment": "28-hindi-punctuation",
    "phase": "punctuated-source-probe",
    "instrument": "m28_punctuated_sources_probe.py (text-only fetch, no audio)",
    "fleurs_hi_in_test": {
        "source": TSV_URL,
        "license": "CC-BY-4.0 (same source family as the approved M23 English slice)",
        "speech_style": "read speech (sentences read aloud), NOT spontaneous",
        "raw_transcription": {
            **stats(raw),
            "examples": [t[:150] for t in raw[:3]],
            "style_note": (
                "Mixed sentence-final style: both danda (।) and Latin full stop (.) "
                "appear as sentence enders — reference curation must pick one policy."
            ),
        },
        "transcription_normalized": {
            **stats(norm),
            "note": (
                "the normalized column already drops most punctuation — "
                "unusable as a punctuation reference"
            ),
        },
    },
    "our_pipeline_preserves_punctuation": {
        "claim": (
            "The zero-punctuation Hindi training rows reflect the sources "
            "(IndicVoices, Kathbath), not our ingestion: the datasets pipeline "
            "keeps punctuation verbatim."
        ),
        "pinned_by": "ml/datasets/tests/test_validate.py::test_case_and_punctuation_survive",
    },
}

OUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
f = evidence["fleurs_hi_in_test"]["raw_transcription"]
print(
    f"FLEURS hi_in raw: rows={f['rows']} any-punct={f['pct_rows_with_any_punctuation']}% "
    f"danda={f['per_mark_total_count']['danda']} comma={f['per_mark_total_count']['comma']} "
    f"fullstop={f['per_mark_total_count']['full_stop']}"
)
print(f"written: {OUT}")
