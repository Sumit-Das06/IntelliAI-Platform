"""M32 — ASR round-trip intelligibility judge over synthesized probe WAVs.

The platform's own judging pattern (M2.5/M3): synthesized audio is transcribed by
the production STT plane and compared to the input text. English probes are judged
by the whisper-small route, Hindi/Devanagari-mixed probes by the promoted E3 Hindi
specialist — both through the real gateway, with the frozen evaluation-plane
normalization profiles and WER/CER implementations (no parallel metric code).

Romanized-Hinglish probes (language == "mixed-roman") are transcribed by BOTH
routes and reported verbatim WITHOUT a score: the reference is Latin-script while
the Hindi route emits Devanagari, so an edit-distance number would measure the
transliteration gap, not intelligibility. Honest label: metric_not_computable.

Run from the repo root:
    uv run --package intelliai-evaluation python .../roundtrip_judge.py \
      --api-key-file <path> --probes .../probe-texts-v1.json \
      --audio-dir <dir with <probe-id>.wav> --engine-label kokoro-hi \
      --out .../evidence/kokoro-hi-roundtrip.json
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx

from intelliai_evaluation.accuracy import cer_unicode, wer_unicode
from intelliai_evaluation.normalization import profile_for

JUDGE_BY_LANGUAGE = {
    "en": ("en",),
    "hi": ("hi",),
    "mixed": ("hi",),
    "mixed-roman": ("en", "hi"),
}


def transcribe(client: httpx.Client, wav_path: Path, language: str) -> dict[str, object]:
    started = time.perf_counter()
    with wav_path.open("rb") as fh:
        response = client.post(
            "/v1/audio/transcriptions",
            data={"model": "intelliai-stt", "language": language, "response_format": "json"},
            files={"file": (wav_path.name, fh, "audio/wav")},
        )
    wall = time.perf_counter() - started
    if response.status_code != 200:
        return {"error": response.status_code, "body": response.text[:200], "wall_s": wall}
    return {"text": response.json()["text"], "wall_s": round(wall, 2)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gateway-url", default="http://localhost:8000")
    parser.add_argument("--api-key-file", required=True)
    parser.add_argument("--probes", required=True)
    parser.add_argument("--audio-dir", required=True)
    parser.add_argument("--engine-label", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    key = Path(args.api_key_file).read_text(encoding="utf-8").strip()
    probes = json.loads(Path(args.probes).read_text(encoding="utf-8"))["cases"]
    audio_dir = Path(args.audio_dir)

    rows: list[dict[str, object]] = []
    with httpx.Client(
        base_url=args.gateway_url,
        headers={"Authorization": f"Bearer {key}"},
        timeout=300.0,
    ) as client:
        for case in probes:
            wav_path = audio_dir / f"{case['id']}.wav"
            if not wav_path.exists():
                continue
            language = case["language"]
            judges = JUDGE_BY_LANGUAGE.get(language, ("en",))
            row: dict[str, object] = {
                "id": case["id"],
                "language": language,
                "category": case.get("category"),
                "reference": case["text"],
            }
            for judge_language in judges:
                outcome = transcribe(client, wav_path, judge_language)
                row[f"judge_{judge_language}"] = outcome
                if "text" not in outcome:
                    continue
                hypothesis = str(outcome["text"])
                if language == "mixed-roman":
                    row["metric"] = "not_computable (Latin reference vs Devanagari route)"
                    continue
                profile = profile_for(judge_language)
                word_level = wer_unicode(case["text"], hypothesis, profile)
                char_level = cer_unicode(case["text"], hypothesis, profile)
                row[f"wer_{judge_language}"] = round(word_level.wer, 4)
                # cer_unicode returns the same breakdown type; its .wer IS the
                # character-level rate (units are characters there).
                row[f"cer_{judge_language}"] = round(char_level.wer, 4)
            rows.append(row)

    def collect(metric_prefix: str, language: str) -> list[float]:
        judge = "hi" if language in ("hi", "mixed") else language
        return [
            float(row[f"{metric_prefix}_{judge}"])
            for row in rows
            if row.get("language") == language and f"{metric_prefix}_{judge}" in row
        ]

    def mean(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 4) if values else None

    report = {
        "experiment": "32-tts-model-selection",
        "instrument": "roundtrip_judge.py",
        "engine_label": args.engine_label,
        "judge_note": (
            "en judged by the whisper-small route, hi/mixed by the promoted E3 route, "
            "through the real gateway; frozen normalization profiles; WER/CER from "
            "intelliai_evaluation.accuracy (no parallel metric code)"
        ),
        "aggregates": {
            "en_round_trip_wer_mean": mean(collect("wer", "en")),
            "en_round_trip_cer_mean": mean(collect("cer", "en")),
            "hi_round_trip_wer_mean": mean(collect("wer", "hi")),
            "hi_round_trip_cer_mean": mean(collect("cer", "hi")),
            "mixed_round_trip_cer_mean": mean(collect("cer", "mixed")),
            "judged_rows": len(rows),
        },
        "rows": rows,
    }
    Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{args.engine_label}: judged {len(rows)} probes -> {json.dumps(report['aggregates'])}")


if __name__ == "__main__":
    main()
