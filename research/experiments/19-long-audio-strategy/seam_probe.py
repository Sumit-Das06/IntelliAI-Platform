"""M19 Phase 16: continuous-speech seam quality, fixed vs snapped windows.

NOT ledger evidence. The research warned that the strategy probe's
seams happened to fall near silence. This probe builds a HARDER input —
spontaneous speech only (IndicVoices Extempore/Conversation scenarios,
no Read clips), so the 95 s window boundaries land mid-speech — and
runs it THROUGH ``Qwen3AsrEngine.transcribe()`` twice per duration:

  radius 8 s  — the committed default (seams snap toward quiet moments)
  radius 0 s  — fixed boundaries (the snap disabled)

Per run it records CER/WER/completeness with the evaluation ruler, the
seam texts, and a duplicate detector: any normalized trigram from the
12 words before a seam that reappears in the 12 words after it is an
overlap the merge failed to dedup. Missing content shows up as
completeness/CER movement against the same reference.
"""

from __future__ import annotations

import argparse
import datetime
import itertools
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine_proof import decoded_audio
from longaudio_probe import RssSampler

from intelliai_evaluation.accuracy import score
from intelliai_evaluation.dataset import load_dataset
from intelliai_evaluation.normalization import profile_for
from intelliai_runtime_contract import TranscriptionRequest
from intelliai_stt_runtime.engines.qwen3_asr import (
    load_qwen3_asr,
    normalize_for_merge,
)


def build_spontaneous_concat(
    manifest: Path, data_root: Path, seconds: int, work: Path
) -> tuple[Path, str]:
    """Concat of Extempore/Conversation clips only — seams land mid-speech."""
    wav_path = work / f"spont-{seconds}s.wav"
    ref_path = work / f"spont-{seconds}s.ref.txt"
    if wav_path.exists() and ref_path.exists():
        return wav_path, ref_path.read_text(encoding="utf-8")
    dataset = load_dataset(manifest)
    spontaneous = [
        c
        for c in dataset.clips
        if c.synthetic is None and ("Extempore" in c.notes or "Conversation" in c.notes)
    ]
    total, chosen = 0.0, []
    for clip in spontaneous:
        chosen.append(clip)
        total += clip.duration_seconds
        if total >= seconds:
            break
    listing = work / f"spont-{seconds}s.txt"
    listing.write_text(
        "".join(f"file '{(data_root / c.filename).resolve().as_posix()}'\n" for c in chosen),
        encoding="utf-8",
    )
    subprocess.run(  # noqa: S603 — ffmpeg from PATH, probe tooling
        [  # noqa: S607
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-t",
            str(seconds),
            "-ar",
            "16000",
            "-ac",
            "1",
            "-sample_fmt",
            "s16",
            str(wav_path),
        ],
        check=True,
        timeout=300,
    )
    reference = " ".join(c.reference_text for c in chosen)
    ref_path.write_text(reference, encoding="utf-8")
    return wav_path, reference


def seam_duplicates(segments: list[Any]) -> list[str]:
    """Normalized trigrams straddling a seam that the merge failed to dedup."""
    duplicated: list[str] = []
    for before, after in itertools.pairwise(segments):
        tail = [normalize_for_merge(w) for w in before.text.split()[-12:]]
        head = [normalize_for_merge(w) for w in after.text.split()[:12]]
        tail_trigrams = {tuple(tail[i : i + 3]) for i in range(len(tail) - 2)}
        head_trigrams = {tuple(head[i : i + 3]) for i in range(len(head) - 2)}
        for trigram in tail_trigrams & head_trigrams:
            if all(trigram):
                duplicated.append(" ".join(trigram))
    return duplicated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("ml/evaluation/stt/datasets/stt-hi-public-eval-v1.json"),
    )
    parser.add_argument("--data-root", type=Path, default=Path("ml/datasets/data"))
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--weights", type=Path, default=Path("weights/qwen3-asr-spike"))
    parser.add_argument(
        "--server-binary",
        type=Path,
        default=Path("weights/qwen3-asr-spike/llama-cpp/llama-server.exe"),
    )
    parser.add_argument("--durations", default="300,600")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    args.work.mkdir(parents=True, exist_ok=True)
    profile = profile_for("hi")
    rows: dict[str, Any] = {}
    for radius in (8.0, 0.0):
        label = f"radius{radius:g}"
        print(f"loading engine ({label}) …", flush=True)
        engine = load_qwen3_asr(
            args.weights,
            server_binary=args.server_binary,
            context_tokens=4096,
            max_audio_seconds=600.0,  # proof override; committed default stays 120
            chunk_snap_radius_seconds=radius,
        )
        try:
            for seconds in (int(s) for s in args.durations.split(",")):
                wav_path, reference = build_spontaneous_concat(
                    args.manifest, args.data_root, seconds, args.work
                )
                audio = decoded_audio(wav_path)
                sampler = RssSampler()
                started = time.perf_counter()
                result = engine.transcribe(audio, TranscriptionRequest(language="hi"))
                wall = round(time.perf_counter() - started, 1)
                scored = score(reference, result.text, profile)
                ref_chars = len(profile.characters(reference))
                hyp_chars = len(profile.characters(result.text))
                segments = list(result.segments)
                rows[f"{seconds}s-{label}"] = {
                    "radius_seconds": radius,
                    "wall_seconds": wall,
                    "peak_rss_mib": sampler.stop(),
                    "cer_unicode": round(scored.cer, 4),
                    "wer_unicode": round(scored.wer, 4),
                    "completeness_chars": round(hyp_chars / ref_chars, 3) if ref_chars else None,
                    "segments": len(segments),
                    "segment_spans": [
                        [round(s.start_seconds, 2), round(s.end_seconds, 2)] for s in segments
                    ],
                    "seam_duplicate_trigrams": seam_duplicates(segments),
                    "seams": [
                        f"…{a.text[-45:]} ⇢ {b.text[:45]}…" for a, b in itertools.pairwise(segments)
                    ],
                    "text": result.text,
                }
                row = rows[f"{seconds}s-{label}"]
                print(
                    f"[seam-probe] {seconds}s {label} -> cer={row['cer_unicode']} "
                    f"completeness={row['completeness_chars']} "
                    f"dups={len(row['seam_duplicate_trigrams'])} wall={wall}s",
                    flush=True,
                )
        finally:
            engine.close()

    payload = {
        "probe": "19-long-audio-seam-quality",
        "NOT_LEDGER_EVIDENCE": (
            "spontaneous-speech concatenation THROUGH Qwen3AsrEngine.transcribe(); "
            "read beside the frozen benchmark, never entered in it"
        ),
        "input": "IndicVoices Extempore/Conversation clips only (no Read) — seams land mid-speech",
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
