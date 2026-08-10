"""Milestone 15B Phase 7/8 spike: Qwen3-ASR 0.6B GGUF on CPU via llama.cpp.

NOT ledger evidence. This is a research-sandbox measurement of a candidate
that has no engine adapter behind the runtime contract: the results carry
no MeasurementRoute and may never be differenced against EvalRun records.
They answer exactly one question per language: is this candidate worth an
adapter at all?

Method:
- clips: the first N natural-speech clips (manifest order — already
  deterministic) from a FROZEN eval manifest, plus its probe clips;
- per clip: one `llama-mtmd-cli` invocation (the CLI is single-shot, so
  every invocation pays model load); gross wall time recorded per clip;
- fixed overhead: median of `--load-only-probe` runs (a 0.5 s silence
  clip) is reported alongside, so net decode time is estimable;
- scoring: the SAME rulers as the evaluation plane — `score()` and
  `hallucinated_words()` under `unicode_generic@v2` via `profile_for` —
  one aligner, one normalization registry, no second framework;
- peak RSS: sampled from the child process at 50 ms intervals.

Reproduce:
    uv run --package intelliai-datasets python \
        research/experiments/15b-qwen3-gguf-spike/run_spike.py \
        --manifest ml/evaluation/stt/datasets/stt-hi-fleurs-eval-v1.json \
        --data-root ml/datasets/data --clips 30 \
        --out research/experiments/15b-qwen3-gguf-spike/results-hi.json
"""

from __future__ import annotations

import argparse
import datetime
import json
import platform
import statistics
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from intelliai_evaluation.accuracy import RulerFailureError, hallucinated_words, score
from intelliai_evaluation.dataset import load_dataset
from intelliai_evaluation.fetch import generate_synthetic, sha256_file
from intelliai_evaluation.normalization import profile_for

SPIKE_DIR = Path("weights/qwen3-asr-spike")
CLI = SPIKE_DIR / "llama-cpp" / "llama-mtmd-cli.exe"
MODEL = SPIKE_DIR / "Qwen3-ASR-0.6B-Q8_0.gguf"
MMPROJ = SPIKE_DIR / "mmproj-Qwen3-ASR-0.6B-Q8_0.gguf"
PROMPT = "Transcribe the audio."
MARKER = "<asr_text>"


def _peak_rss_sampler(pid: int, samples: list[int], stop: threading.Event) -> None:
    """Sample the child's working set via PowerShell-free ctypes? No —
    tasklist is portable enough for a spike and adds no dependency."""
    while not stop.is_set():
        try:
            out = subprocess.run(  # noqa: S603 — fixed argv, spike tool
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            ).stdout
            if '","' in out:
                kb = out.rsplit('","', 1)[-1].strip().strip('"').replace(" K", "")
                samples.append(int(kb.replace(",", "").replace(".", "")) * 1024)
        except (subprocess.SubprocessError, ValueError):
            pass
        stop.wait(0.05)


def run_clip(
    audio_path: Path, *, context_tokens: int = 0, sample_ram: bool = False
) -> dict[str, Any]:
    argv = [
        str(CLI),
        "-m",
        str(MODEL),
        "--mmproj",
        str(MMPROJ),
        "--audio",
        str(audio_path),
        "-p",
        PROMPT,
    ]
    if context_tokens > 0:
        argv += ["-c", str(context_tokens)]
    started = time.perf_counter()
    process = subprocess.Popen(  # noqa: S603 — fixed argv, spike tool
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    rss_samples: list[int] = []
    stop = threading.Event()
    sampler: threading.Thread | None = None
    if sample_ram:
        sampler = threading.Thread(
            target=_peak_rss_sampler, args=(process.pid, rss_samples, stop), daemon=True
        )
        sampler.start()
    stdout, _ = process.communicate(timeout=600)
    wall = time.perf_counter() - started
    if sampler is not None:
        stop.set()
        sampler.join(timeout=2)

    emitted_language = ""
    hypothesis = stdout.strip()
    if MARKER in stdout:
        head, _, tail = stdout.partition(MARKER)
        hypothesis = tail.strip()
        if "language" in head:
            emitted_language = head.rsplit("language", 1)[-1].strip()
    return {
        "wall_seconds": round(wall, 3),
        "hypothesis": hypothesis,
        "emitted_language": emitted_language,
        "returncode": process.returncode,
        "peak_rss_mib": round(max(rss_samples) / (1 << 20), 1) if rss_samples else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=Path("ml/datasets/data"))
    parser.add_argument("--clips", type=int, default=30)
    parser.add_argument("--overhead-runs", type=int, default=3)
    parser.add_argument("--ctx", type=int, default=0, help="llama.cpp context tokens; 0 = default")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    dataset = load_dataset(args.manifest)
    profile = profile_for(dataset.clips[0].language)
    natural = [c for c in dataset.clips if c.synthetic is None][: args.clips]
    probes = [c for c in dataset.clips if c.synthetic is not None]

    # Fixed-overhead probe: a 0.5 s silence clip, run N times.
    overhead_clip = args.data_root / "_spike-overhead-0.5s.wav"
    if not overhead_clip.exists():
        from intelliai_evaluation.dataset import SyntheticSpec

        generate_synthetic(SyntheticSpec(kind="silence", duration_seconds=0.5), overhead_clip)
    overhead_walls = [
        run_clip(overhead_clip, context_tokens=args.ctx)["wall_seconds"]
        for _ in range(args.overhead_runs)
    ]
    overhead = statistics.median(overhead_walls)

    results: list[dict[str, Any]] = []
    total_audio = 0.0
    total_net = 0.0
    for index, clip in enumerate(natural):
        audio = args.data_root / clip.filename
        outcome = run_clip(audio, context_tokens=args.ctx, sample_ram=(index == 0))
        row: dict[str, Any] = {
            "clip_id": clip.id,
            "duration_seconds": clip.duration_seconds,
            **outcome,
        }
        if outcome["returncode"] == 0 and outcome["hypothesis"]:
            try:
                scores = score(clip.reference_text, outcome["hypothesis"], profile)
                row["cer_unicode"] = round(scores.cer, 4)
                row["wer_unicode"] = round(scores.wer, 4)
            except RulerFailureError as exc:
                row["ruler_failure"] = str(exc)
        net = max(outcome["wall_seconds"] - overhead, 0.0)
        row["net_seconds_est"] = round(net, 3)
        total_audio += clip.duration_seconds
        total_net += net
        results.append(row)

    probe_results: list[dict[str, Any]] = []
    for clip in probes:
        audio = args.data_root / clip.filename
        if not audio.exists() and clip.synthetic is not None:
            generate_synthetic(clip.synthetic, audio)
        outcome = run_clip(audio, context_tokens=args.ctx)
        emitted = hallucinated_words(
            declared_reference="", hypothesis=outcome["hypothesis"], profile=profile
        )
        probe_results.append({"clip_id": clip.id, "hallucinated_words": emitted, **outcome})

    scored = [r for r in results if "cer_unicode" in r]
    ref_chars = {
        r["clip_id"]: len(profile.characters(c.reference_text))
        for r, c in zip(results, natural, strict=True)
        if "cer_unicode" in r
    }
    weighted_cer = (
        sum(r["cer_unicode"] * ref_chars[r["clip_id"]] for r in scored) / sum(ref_chars.values())
        if scored
        else None
    )

    payload = {
        "spike": "15b-qwen3-asr-0.6b-gguf-cpu",
        "NOT_LEDGER_EVIDENCE": (
            "research-sandbox spike; no MeasurementRoute; never difference against EvalRun records"
        ),
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "manifest": {
            "name": dataset.name,
            "version": dataset.version,
            "sha256": sha256_file(args.manifest),
        },
        "artifacts": {
            "model": {"path": str(MODEL), "sha256": sha256_file(MODEL)},
            "mmproj": {"path": str(MMPROJ), "sha256": sha256_file(MMPROJ)},
            "llama_cpp": "b10344 win-cpu-x64 "
            "(zip sha256 c0cec8825843957cae6620f927eb6eb9f7f4680da3206910932ea9075f91b405)",
        },
        "environment": {
            "cpu": platform.processor(),
            "machine": platform.machine(),
            "os": f"{platform.system()} {platform.release()}",
            "python": platform.python_version(),
            "prompt": PROMPT,
        },
        "method": {
            "per_clip_process": "each clip pays one full CLI invocation (model load included)",
            "overhead_probe_walls": overhead_walls,
            "overhead_median_seconds": overhead,
            "net_rtf_definition": "(wall - overhead_median) / audio_duration, per clip",
            "context_tokens": args.ctx or "llama.cpp default (32k) - allocates ~8.5 GiB KV",
        },
        "aggregates": {
            "clips_scored": len(scored),
            "clips_failed": len(results) - len(scored),
            "cer_unicode_char_weighted": round(weighted_cer, 4)
            if weighted_cer is not None
            else None,
            "gross_rtf": round(sum(r["wall_seconds"] for r in results) / total_audio, 3)
            if total_audio
            else None,
            "net_rtf_est": round(total_net / total_audio, 3) if total_audio else None,
            "peak_rss_mib_first_clip": next(
                (r["peak_rss_mib"] for r in results if r.get("peak_rss_mib")), None
            ),
        },
        "probes": probe_results,
        "clips": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    aggregates = payload["aggregates"]
    print(json.dumps(aggregates, indent=2))
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
