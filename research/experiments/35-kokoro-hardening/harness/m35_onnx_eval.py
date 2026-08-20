"""M35 Phase 7 — community Kokoro ONNX, evaluated (research only).

The question: does `onnx-community/Kokoro-82M-v1.0-ONNX` (Apache-2.0)
buy enough RAM/simplicity to justify replacing the torch runtime later?
Measured with the same row schema as every M32-35 instrument, same
probe texts, WAVs judged through the same whisper route afterwards.
NOT a production switch — evidence for a future adoption decision.

Runs inside a scratch venv (WSL) with `kokoro-onnx` (MIT wrapper):
    python m35_onnx_eval.py --probes .../probe-texts-en-v1.json \
        --variant q8f16 --audio-dir ~/m35/audio/onnx \
        --out .../evidence/kokoro-onnx-bench.json
"""

from __future__ import annotations

import argparse
import json
import time
import wave
from pathlib import Path

MODEL_FILES = {
    "fp32": "onnx/model.onnx",
    "q8f16": "onnx/model_q8f16.onnx",
}
REPO = "onnx-community/Kokoro-82M-v1.0-ONNX"


def _rss_mib() -> float:
    with open("/proc/self/status", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024.0
    return 0.0


def _peak_rss_mib() -> float:
    with open("/proc/self/status", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) / 1024.0
    return 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probes", required=True)
    parser.add_argument("--variant", choices=sorted(MODEL_FILES), default="q8f16")
    parser.add_argument("--audio-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--voice", default="af_heart")
    parser.add_argument("--repetitions", type=int, default=2)
    args = parser.parse_args()

    from huggingface_hub import hf_hub_download, model_info

    revision = str(model_info(REPO).sha)
    model_path = hf_hub_download(REPO, MODEL_FILES[args.variant], revision=revision)
    # The combined voices file ships with the kokoro-onnx project (MIT),
    # not with the HF onnx conversion; pinned release asset, sha recorded.
    voices_url = (
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
        "model-files-v1.0/voices-v1.0.bin"
    )
    voices_path = str(Path(model_path).parent / "voices-v1.0.bin")
    if not Path(voices_path).exists():
        import urllib.request

        urllib.request.urlretrieve(voices_url, voices_path)
    import hashlib

    voices_sha = hashlib.sha256(Path(voices_path).read_bytes()).hexdigest()

    probes = [
        case
        for case in json.loads(Path(args.probes).read_text(encoding="utf-8"))["cases"]
        if case["language"] == "en"
    ]

    rss_before = _rss_mib()
    load_started = time.perf_counter()
    from kokoro_onnx import Kokoro

    engine = Kokoro(model_path, voices_path)
    load_seconds = time.perf_counter() - load_started
    rss_after = _rss_mib()

    engine.create("Warm up run.", voice=args.voice, speed=1.0, lang="en-us")

    audio_dir = Path(args.audio_dir).expanduser()
    audio_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    sample_rate = 24_000
    for case in probes:
        best: dict[str, object] | None = None
        samples = None
        for _ in range(max(1, args.repetitions)):
            started = time.perf_counter()
            try:
                samples, sample_rate = engine.create(
                    case["text"], voice=args.voice, speed=1.0, lang="en-us"
                )
            except Exception as exc:
                failures.append({"id": case["id"], "error": f"{exc.__class__.__name__}: {exc}"})
                break
            wall = time.perf_counter() - started
            seconds = len(samples) / sample_rate if samples is not None else 0.0
            row = {
                "id": case["id"],
                "language": "en",
                "category": case.get("category"),
                "chars": len(case["text"]),
                "wall_ms": round(wall * 1000.0, 1),
                "ttfa_ms": None,
                "audio_seconds": round(seconds, 3),
                "rtf": round(wall / seconds, 4) if seconds > 0 else None,
            }
            if best is None or row["wall_ms"] < best["wall_ms"]:  # type: ignore[operator]
                best = row
        if best is None:
            continue
        if samples is not None:
            import numpy as np

            pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
            with wave.open(str(audio_dir / f"{case['id']}.wav"), "wb") as fh:
                fh.setnchannels(1)
                fh.setsampwidth(2)
                fh.setframerate(sample_rate)
                fh.writeframes(pcm)
        rows.append(best)

    ok = [row for row in rows if row["rtf"] is not None]
    rtfs = sorted(float(row["rtf"]) for row in ok)  # type: ignore[arg-type]
    report = {
        "experiment": "35-kokoro-hardening",
        "instrument": "m35_onnx_eval.py",
        "engine": f"kokoro-onnx community ({args.variant})",
        "identity": {
            "hub_repo": REPO,
            "hub_revision": revision,
            "model_file": MODEL_FILES[args.variant],
            "wrapper": "kokoro-onnx (MIT)",
            "voices_file": {"url": voices_url, "sha256": voices_sha},
            "voice": args.voice,
            "g2p_note": (
                "the wrapper does its own phonemization - quality deltas vs the "
                "production engine include the frontend difference, not just the "
                "quantization"
            ),
        },
        "sample_rate_hz": sample_rate,
        "load_seconds": round(load_seconds, 2),
        "rss_before_load_mib": round(rss_before, 1),
        "rss_after_load_mib": round(rss_after, 1),
        "rss_peak_mib": round(_peak_rss_mib(), 1),
        "probe_count": len(rows),
        "failure_count": len(failures),
        "failures": failures,
        "rtf_median": rtfs[len(rtfs) // 2] if rtfs else None,
        "rtf_p95": rtfs[min(len(rtfs) - 1, int(0.95 * len(rtfs)))] if rtfs else None,
        "rows": rows,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"kokoro-onnx[{args.variant}]: {len(rows)} probes, {len(failures)} failures, "
        f"median RTF {report['rtf_median']}, peak RSS {report['rss_peak_mib']} MiB, "
        f"load {report['load_seconds']} s"
    )


if __name__ == "__main__":
    main()
