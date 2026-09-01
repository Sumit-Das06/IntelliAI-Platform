"""M56 scorer — outputs.jsonl vs the frozen benchmark.

    python score_correction.py --dataset <d.jsonl> --outputs <o.jsonl> --report <r.json>

Metrics: exact match, WER/CER vs gold (frozen unicode_generic@v2 ruler),
unchanged-correct + unnecessary-rewrite (already_correct rows), entity
preservation, meaning-trap pass, addition proxy (EXPERIMENTAL), per-category WER.
"""

# ruff: noqa: T201 — research scripts report via stdout

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml/evaluation/src"))
from intelliai_evaluation.accuracy import score  # noqa: E402
from intelliai_evaluation.normalization import UNICODE_GENERIC_V2  # noqa: E402

_STRIP = re.compile(r"[^0-9a-zऀ-ॿ]+")


def squash(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text).casefold()
    normalized = normalized.replace("।", "").replace("॥", "")  # danda is punctuation
    return _STRIP.sub("", normalized)


def tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^\wऀ-ॿ]+", unicodedata.normalize("NFC", text).casefold()) if t}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--outputs", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    gold = {
        r["id"]: r for r in map(json.loads, args.dataset.read_text(encoding="utf-8").splitlines())
    }
    outs = [json.loads(line) for line in args.outputs.read_text(encoding="utf-8").splitlines()]

    wers, cers = [], []
    per_category: dict[str, list[float]] = defaultdict(list)
    exact = 0
    unchanged_ok = unchanged_total = 0
    entity_ok = entity_total = 0
    trap_pass = trap_total = 0
    additions = 0
    addition_ids = []
    entity_fail_ids = []
    normalization_missed: list[str] = []
    language_flips: list[str] = []
    devanagari = re.compile(r"[ऀ-ॿ]")
    for out in outs:
        row = gold[out["id"]]
        output = out["output"]
        s = score(row["gold_correction"], output, UNICODE_GENERIC_V2)
        wers.append(s.wer)
        cers.append(s.cer)
        per_category[f"{row['language']}:{row['category']}"].append(s.wer)
        if output.strip() == row["gold_correction"].strip():
            exact += 1
        if row["already_correct"]:
            unchanged_total += 1
            # "Unchanged" means the model did not REWRITE correct
            # content — compared against the gold (== the input's words;
            # punctuation-only differences never count as a rewrite).
            if squash(output) == squash(row["gold_correction"]):
                unchanged_ok += 1
        row_entities_ok = True
        for entity in row["preserve_entities"]:
            entity_total += 1
            if squash(entity) in squash(output):
                entity_ok += 1
            elif squash(entity) not in squash(row["noisy_input"]):
                # The entity only EXISTS in normalized form in the gold
                # (input had it verbalized: "twelve thousand five
                # hundred"). The model kept the input wording instead of
                # normalizing — meaning-safe, formatting missed.
                normalization_missed.append(f"{out['id']}:{entity}")
            else:
                # The entity was present in the input and the output
                # altered or dropped it — a REAL violation.
                row_entities_ok = False
                entity_fail_ids.append(f"{out['id']}:{entity}")
        if row["meaning_trap"]:
            trap_total += 1
            if row_entities_ok:
                trap_pass += 1
        # Language contract: EN rows must stay Latin; HI rows must come
        # back in Devanagari (Roman-Hindi included).
        wrong_script = (row["language"] == "en" and devanagari.search(output)) or (
            row["language"] == "hi" and not devanagari.search(output)
        )
        if wrong_script:
            language_flips.append(out["id"])
        novel = {
            t
            for t in (tokens(output) - tokens(row["noisy_input"]) - tokens(row["gold_correction"]))
            if len(t) >= 4 or re.match(r"^[ऀ-ॿ]{3,}$", t)
        }
        if len(novel) >= 2:
            additions += 1
            addition_ids.append(out["id"])

    n = len(outs)
    report = {
        "rows": n,
        "exact_match": round(exact / n, 4),
        "wer_vs_gold_mean": round(statistics.mean(wers), 4),
        "wer_vs_gold_median": round(statistics.median(wers), 4),
        "cer_vs_gold_mean": round(statistics.mean(cers), 4),
        "unchanged_correct_rate": round(unchanged_ok / unchanged_total, 4)
        if unchanged_total
        else None,
        "unnecessary_rewrite_rate": round(1 - unchanged_ok / unchanged_total, 4)
        if unchanged_total
        else None,
        "entity_gold_form_rate": round(entity_ok / entity_total, 4) if entity_total else None,
        "entity_violation_rate_HARD_GATE": round(len(entity_fail_ids) / entity_total, 4)
        if entity_total
        else None,
        "entity_violations": entity_fail_ids[:25],
        "normalization_missed_meaning_safe": len(normalization_missed),
        "normalization_missed_ids": normalization_missed[:25],
        "language_flip_ids": language_flips[:25],
        "language_flip_rate": round(len(language_flips) / n, 4),
        "meaning_trap_pass_rate": round(trap_pass / trap_total, 4) if trap_total else None,
        "addition_proxy_rate_EXPERIMENTAL": round(additions / n, 4),
        "addition_flagged_ids": addition_ids[:25],
        "per_category_wer_mean": {
            k: round(statistics.mean(v), 4) for k, v in sorted(per_category.items())
        },
    }
    args.report.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "rows",
                    "exact_match",
                    "wer_vs_gold_mean",
                    "unchanged_correct_rate",
                    "entity_violation_rate_HARD_GATE",
                    "language_flip_rate",
                    "meaning_trap_pass_rate",
                    "addition_proxy_rate_EXPERIMENTAL",
                )
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
