"""M33 — Chatterbox-nano English bench (research venv, CPU torch).

OUTCOME (2026-08-20): NOT MEASURED — packaging wall, recorded as a finding.
No released loader can construct nano: PyPI chatterbox-tts 0.1.7 and GitHub
main both lack the card's `nano=True` API; pointing the turbo loader at the
nano repo fails first on filenames (t3_turbo_v1 vs t3_nano_v1) and then,
symlinked, on architecture shape mismatches (nano t3 is 768-dim, the turbo
class builds 1024-dim). The instrument stays for the day upstream ships a
real loader; until then the candidate is unimplementable, not just unmeasured.

Measurement core mirrors M32's `wsl_synth_bench.py` (same fields, same JSON
shape) so results merge into one decision table; only the adapter is new.

Chatterbox-nano is a 110M MIT model that REQUIRES a reference clip (no preset
voices). Policy-clean reference: a SYNTHETIC voice sample produced by our own
production engine (no real person's voice is cloned; the consent question is
moot by construction). The reference path is recorded in the output identity.

Run inside the venv (WSL):
    python m33_nano_bench.py --probes probe-texts-en-v1.json \
        --ref-wav ~/m33/ref-af-heart.wav --audio-dir ~/m33/audio/nano \
        --out evidence/chatterbox-nano-bench.json --repetitions 2
"""

from __future__ import annotations

import argparse
import json
import time
import wave
from pathlib import Path


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


def _write_wav(path: Path, pcm: bytes, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(sample_rate)
        fh.writeframes(pcm)


def _to_pcm16(audio: object) -> bytes:
    import numpy as np

    arr = audio
    if hasattr(arr, "detach"):
        arr = arr.detach().cpu().numpy()
    arr = np.asarray(arr, dtype=np.float32).reshape(-1)
    arr = np.clip(arr, -1.0, 1.0)
    return (arr * 32767.0).astype("<i2").tobytes()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probes", required=True)
    parser.add_argument("--ref-wav", required=True)
    parser.add_argument("--audio-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--repetitions", type=int, default=1)
    args = parser.parse_args()

    probes = json.loads(Path(args.probes).read_text(encoding="utf-8"))["cases"]
    probes = [case for case in probes if case["language"] == "en"]
    ref_wav = str(Path(args.ref_wav).expanduser())

    rss_before = _rss_mib()
    load_started = time.perf_counter()
    # Packaging reality (recorded finding): no released chatterbox-tts (PyPI
    # 0.1.7 or GitHub main at verification) exposes the nano loader the model
    # card advertises (`from_pretrained(..., nano=True)`). The turbo loader is
    # repo-compatible, so the nano checkpoint is loaded by pointing the
    # module's REPO_ID at the nano repo — the exact hack a production adapter
    # would NOT be allowed to ship.
    import chatterbox.tts_turbo as turbo

    turbo.REPO_ID = "ResembleAI/chatterbox-nano"
    model = turbo.ChatterboxTurboTTS.from_pretrained(device="cpu")
    load_seconds = time.perf_counter() - load_started
    rss_after_load = _rss_mib()
    sample_rate = int(model.sr)

    model.generate("Warm up run.", audio_prompt_path=ref_wav)

    audio_dir = Path(args.audio_dir).expanduser()
    rows: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    for case in probes:
        text = case["text"]
        best: dict[str, object] | None = None
        pcm = b""
        for _ in range(max(1, args.repetitions)):
            started = time.perf_counter()
            try:
                audio = model.generate(text, audio_prompt_path=ref_wav)
            except Exception as exc:
                failures.append({"id": case["id"], "error": f"{exc.__class__.__name__}: {exc}"})
                break
            wall = time.perf_counter() - started
            pcm = _to_pcm16(audio)
            seconds = (len(pcm) // 2) / sample_rate if pcm else 0.0
            row = {
                "id": case["id"],
                "language": "en",
                "category": case.get("category"),
                "chars": len(text),
                "wall_ms": round(wall * 1000.0, 1),
                "ttfa_ms": None,
                "audio_seconds": round(seconds, 3),
                "rtf": round(wall / seconds, 4) if seconds > 0 else None,
            }
            if best is None or row["wall_ms"] < best["wall_ms"]:  # type: ignore[operator]
                best = row
        if best is None:
            continue
        if pcm:
            _write_wav(audio_dir / f"{case['id']}.wav", pcm, sample_rate)
        rows.append(best)

    ok = [row for row in rows if row["rtf"] is not None]
    rtfs = sorted(float(row["rtf"]) for row in ok)  # type: ignore[arg-type]
    report = {
        "experiment": "33-english-tts-selection",
        "instrument": "m33_nano_bench.py",
        "engine": "chatterbox-nano (ResembleAI, 110M, MIT)",
        "identity": {
            "hub_repo": "ResembleAI/chatterbox-nano",
            "reference_wav": ref_wav,
            "reference_note": "synthetic clip from our own engine - no real voice cloned",
            "watermark_note": "library applies the Perth watermark to all output",
            "sample_rate_hz": sample_rate,
        },
        "sample_rate_hz": sample_rate,
        "repetitions": args.repetitions,
        "load_seconds": round(load_seconds, 2),
        "rss_before_load_mib": round(rss_before, 1),
        "rss_after_load_mib": round(rss_after_load, 1),
        "rss_peak_mib": round(_peak_rss_mib(), 1),
        "probe_count": len(rows),
        "failure_count": len(failures),
        "failures": failures,
        "rtf_median": rtfs[len(rtfs) // 2] if rtfs else None,
        "rtf_p95": rtfs[min(len(rtfs) - 1, int(0.95 * len(rtfs)))] if rtfs else None,
        "streaming": "none exposed by the python API (single-shot generate)",
        "rows": rows,
    }
    Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"chatterbox-nano: {len(rows)} probes, {len(failures)} failures, "
        f"median RTF {report['rtf_median']}, peak RSS {report['rss_peak_mib']} MiB"
    )


if __name__ == "__main__":
    main()
