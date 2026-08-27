"""M53 quality + scorecard post-processing.

Scores the battery's realtime FINALS:

* Hindi — against IndicVoices GROUND TRUTH (the M52H ruler), side by
  side with M52H's offline per-clip baselines for the same material.
* English — against the batch pipeline's text for the same clip
  (boss30), WER via the frozen evaluation ruler.

Also assembles the Phase-47 scorecard from the battery JSONs.

    python m53_quality.py
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EVIDENCE = HERE / "evidence"
sys.path.insert(0, str(ROOT / "ml/evaluation/src"))

from intelliai_evaluation.accuracy import score  # noqa: E402
from intelliai_evaluation.normalization import UNICODE_GENERIC_V2  # noqa: E402
from intelliai_evaluation.wer import word_error_rate  # noqa: E402

H = Path(
    r"C:\Users\VIKASH~1\AppData\Local\Temp\claude"
    r"\d--Sumit-Projects-IntelliAI-Platform"
    r"\67762b73-e6aa-43b8-a730-264d0d432d4f\scratchpad\m52hclips"
)


def load(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def main() -> None:
    # ── Hindi vs ground truth ────────────────────────────────────────────
    m52h_baseline = json.loads(
        (
            ROOT
            / "research/experiments/52h-hindi-qwen-gpu/evidence/long-offline-per-clip-baseline.json"
        ).read_text(encoding="utf-8")
    )
    hindi = {}
    for session, ref_name in (
        ("hi-real30s-realtime.json", "real30s"),
        ("hi-real2min-realtime.json", "real2min"),
        ("hi-real5min-realtime.json", "real5min"),
        ("hi-real10min-realtime.json", "real10min"),
    ):
        run = load(session)
        reference = (H / f"{ref_name}.ref.txt").read_text(encoding="utf-8")
        final = str(run.get("final_text") or "")
        scores = score(reference, final, UNICODE_GENERIC_V2)
        baseline = m52h_baseline.get(ref_name, {}).get("per_clip_offline_vs_truth")
        hindi[ref_name] = {
            "realtime_final_vs_truth": {"wer": round(scores.wer, 4), "cer": round(scores.cer, 4)},
            "m52h_offline_per_clip_baseline": baseline,
            "final_words": len(final.split()),
            "ref_words": len(reference.split()),
        }
        print(ref_name, hindi[ref_name]["realtime_final_vs_truth"], "baseline", baseline)
    (EVIDENCE / "hindi-quality.json").write_text(
        json.dumps(
            {"ruler": "unicode_generic@v2 (frozen)", "sessions": hindi},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    # ── English vs the batch pipeline ────────────────────────────────────
    batch = load("batch-regression.json")["text"]
    realtime_final = str(load("en-boss30-realtime.json").get("final_text") or "")
    breakdown = word_error_rate(batch, realtime_final)
    english = {
        "clip": "boss30",
        "reference": "the batch pipeline's own punctuated text (same stack, same clip)",
        "realtime_vs_batch_wer": round(breakdown.wer, 4),
        "note": "punctuation differences count as substitutions under this "
        "ruler; word-stream equality is the law being checked",
    }
    (EVIDENCE / "english-quality.json").write_text(
        json.dumps(english, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("english boss30 realtime-vs-batch WER:", english["realtime_vs_batch_wer"])

    # ── scorecard ────────────────────────────────────────────────────────
    def row(name: str) -> dict:
        run = load(name)
        return {
            "fpt_s": run.get("first_partial_at_s"),
            "partial_gap_p50_s": run.get("partial_gap_p50_s"),
            "finalization_ms": run.get("finalization_ms"),
            "degraded": run.get("degraded"),
            "errors": len(run.get("errors") or []),
            "sample_id": run.get("sample_id_present"),
        }

    en_shorts = [load(f"en-short-{k}.json") for k in ("hello", "yes", "no", "okay", "stop")]
    hi_shorts = [
        load(name)
        for name in (
            "hi-short_haan.json",
            "hi-short_nahin.json",
            "hi-short_theek.json",
            "hi-short_chalo.json",
            "hi-short_haansir.json",
            "hi-realshort_0.json",
            "hi-realshort_1.json",
            "hi-realshort_2.json",
        )
    ]
    scorecard = {
        "english": {
            "boss30": row("en-boss30-realtime.json"),
            "long_2min": row("en-2min-realtime.json"),
            "long_5min": row("en-5min-realtime.json"),
            "long_10min": row("en-10min-realtime.json"),
            "short_final_ms_median": statistics.median(
                run["finalization_ms"] for run in en_shorts if run.get("finalization_ms")
            ),
            "silence": {
                "partials": load("en-silence5.json")["partial_count"],
                "final_text_empty": not load("en-silence5.json").get("final_text"),
                "sample_stored": load("en-silence5.json")["sample_id_present"],
            },
            "flood": {
                "degraded": load("en-2min-flood.json")["degraded"],
                "final_present": load("en-2min-flood.json")["finalization_ms"] is not None,
            },
        },
        "hindi": {
            "real30s": row("hi-real30s-realtime.json"),
            "long_2min": row("hi-real2min-realtime.json"),
            "long_5min": row("hi-real5min-realtime.json"),
            "long_10min": row("hi-real10min-realtime.json"),
            "short_final_ms_median": statistics.median(
                run["finalization_ms"] for run in hi_shorts if run.get("finalization_ms")
            ),
            "silence": {
                "partials": load("hi-silence5.json")["partial_count"],
                "final_text_empty": not load("hi-silence5.json").get("final_text"),
            },
        },
    }
    (EVIDENCE / "scorecard.json").write_text(
        json.dumps(scorecard, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("scorecard written")


if __name__ == "__main__":
    main()
