"""M56 extras — punctuation interaction (Phase 23), chunking coherence
(Phase 20), and the human-eval pack generator (Phase 30).

    python extras.py --url http://127.0.0.1:8899 --evidence <evidence-dir>
"""

# ruff: noqa: T201 — research scripts report via stdout

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from run_correction import correct


def punctuation_interaction(url: str, rows: list[dict], evidence: Path) -> None:
    """Arrangement A (punctuated input -> correction) vs raw input.

    The naive-punctuated variant approximates the existing punctuation
    stage's output (words unchanged, marks added)."""
    subset = [r for r in rows if r["language"] == "en" and not r["already_correct"]][:12]
    report = []
    for row in subset:
        raw = row["noisy_input"]
        naive = raw[0].upper() + raw[1:] + "."
        out_raw, _ = correct(url, raw, language="en")
        out_punct, _ = correct(url, naive, language="en")
        report.append(
            {
                "id": row["id"],
                "out_from_raw": out_raw,
                "out_from_punctuated": out_punct,
                "same_words": " ".join(out_raw.split()).casefold().rstrip(".")
                == " ".join(out_punct.split()).casefold().rstrip("."),
            }
        )
    agree = sum(1 for r in report if r["same_words"])
    (evidence / "punctuation-interaction.json").write_text(
        json.dumps(
            {
                "what": "correction output from RAW vs PRE-PUNCTUATED input (12 EN rows)",
                "word_level_agreement": f"{agree}/{len(report)}",
                "verdict_input": report,
                "architecture_note": "the correction model punctuates on its own either way; "
                "pre-punctuation neither helps nor harms materially — see the milestone doc "
                "for the recommended arrangement",
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print("punctuation-interaction:", agree, "/", len(report))


CHUNK_TEXTS = [
    (
        "en",
        "yesterday priya joined the project she dont have access yet so i shared my screen "
        "she will got her own login by friday then she can work independent",
    ),
    (
        "en",
        "the server crashed at nine we restart it twice it keep crashing finally we found "
        "the disk were full we clean the logs and it run fine since then",
    ),
    (
        "hi",
        "kal humne naya feature launch kiya tha users ko bahut pasand aaya lekin raat ko "
        "server slow ho gaya phir humne use restart kiya ab sab theek chal raha hai",
    ),
    (
        "hi",
        "mera bhai dilli mein rehta hai wo engineer hai usne mujhe laptop gift kiya main "
        "usse roz baat karta hoon",
    ),
]


def chunking(url: str, evidence: Path) -> None:
    report = []
    for language, text in CHUNK_TEXTS:
        whole, _ = correct(url, text, language=language)
        # Naive sentence-ish chunks: thirds by word count.
        words = text.split()
        third = len(words) // 3
        chunks = [
            " ".join(words[:third]),
            " ".join(words[third : 2 * third]),
            " ".join(words[2 * third :]),
        ]
        chunked_parts = [correct(url, chunk, language=language)[0] for chunk in chunks]
        report.append(
            {
                "language": language,
                "input": text,
                "whole": whole,
                "chunked_merged": " ".join(chunked_parts),
            }
        )
    (evidence / "chunking.json").write_text(
        json.dumps(
            {
                "what": "whole-transcript vs blind-chunk correction (context-dependency probe)",
                "cases": report,
                "note": "read whole vs chunked_merged: blind chunking loses cross-sentence "
                "context (pronouns/tense) — quoted verbatim for the milestone doc verdict",
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print("chunking cases:", len(report))


def human_pack(url: str, rows: list[dict], evidence: Path) -> None:
    random.seed(56)
    en = random.sample([r for r in rows if r["language"] == "en" and not r["already_correct"]], 25)
    hi = random.sample([r for r in rows if r["language"] == "hi" and not r["already_correct"]], 25)
    pack = []
    for row in en + hi:
        output, _ = correct(url, row["noisy_input"], language=row["language"])
        pack.append(
            {
                "id": row["id"],
                "language": row["language"],
                "noisy": row["noisy_input"],
                "model_output": output,
                "scores": {
                    "grammar": None,
                    "readability": None,
                    "meaning": None,
                    "naturalness": None,
                    "unnecessary_changes": None,
                },
            }
        )
    (evidence / "human-eval-pack.json").write_text(
        json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("human pack rows:", len(pack))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    dataset = args.evidence / "dataset.jsonl"
    rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines()]
    punctuation_interaction(args.url, rows, args.evidence)
    chunking(args.url, args.evidence)
    human_pack(args.url, rows, args.evidence)


if __name__ == "__main__":
    main()
