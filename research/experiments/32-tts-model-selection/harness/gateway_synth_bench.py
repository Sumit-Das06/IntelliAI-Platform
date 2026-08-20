"""M32 — production-path synthesis bench: the shipping runtime through the gateway.

Drives POST /v1/audio/speech (the real customer surface: registry routing, voice
resolution, admission, metering) for every probe the production engine can serve,
records wall time / audio seconds / RTF per probe, and saves the WAVs for the
round-trip judge. v1 is unstreamed, so TTFA equals full response time by design.

Run from the repo root:
    uv run --package intelliai-evaluation python \
      research/experiments/32-tts-model-selection/harness/gateway_synth_bench.py \
      --api-key-file <path> --probes .../probe-texts-v1.json \
      --languages en,mixed-roman --voice reference-alto \
      --audio-dir <non-repo dir> --out .../evidence/gateway-kokoro-en-bench.json
"""

from __future__ import annotations

import argparse
import json
import time
import wave
from pathlib import Path

import httpx


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gateway-url", default="http://localhost:8000")
    parser.add_argument("--api-key-file", required=True)
    parser.add_argument("--probes", required=True)
    parser.add_argument("--languages", default="en")
    parser.add_argument("--voice", default="reference-alto")
    parser.add_argument("--model", default="intelliai-tts")
    parser.add_argument("--audio-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--repetitions", type=int, default=2)
    args = parser.parse_args()

    key = Path(args.api_key_file).read_text(encoding="utf-8").strip()
    probes = json.loads(Path(args.probes).read_text(encoding="utf-8"))["cases"]
    wanted = {piece.strip() for piece in args.languages.split(",") if piece.strip()}
    probes = [case for case in probes if case["language"] in wanted]

    audio_dir = Path(args.audio_dir)
    audio_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []

    with httpx.Client(
        base_url=args.gateway_url,
        headers={"Authorization": f"Bearer {key}"},
        timeout=120.0,
    ) as client:
        # one warm probe, excluded from rows
        client.post(
            "/v1/audio/speech",
            json={"model": args.model, "input": "Warm up.", "voice": args.voice},
        )
        for case in probes:
            best: dict[str, object] | None = None
            audio_bytes = b""
            for _ in range(max(1, args.repetitions)):
                started = time.perf_counter()
                response = client.post(
                    "/v1/audio/speech",
                    json={"model": args.model, "input": case["text"], "voice": args.voice},
                )
                wall = time.perf_counter() - started
                if response.status_code != 200:
                    failures.append(
                        {
                            "id": case["id"],
                            "status": response.status_code,
                            "body": response.text[:300],
                        }
                    )
                    break
                audio_bytes = response.content
                row = {
                    "id": case["id"],
                    "language": case["language"],
                    "category": case.get("category"),
                    "chars": len(case["text"]),
                    "wall_ms": round(wall * 1000.0, 1),
                    "bytes": len(audio_bytes),
                }
                if best is None or row["wall_ms"] < best["wall_ms"]:  # type: ignore[operator]
                    best = row
            if best is None:
                continue
            wav_path = audio_dir / f"{case['id']}.wav"
            wav_path.write_bytes(audio_bytes)
            with wave.open(str(wav_path), "rb") as fh:
                seconds = fh.getnframes() / fh.getframerate()
                best["sample_rate_hz"] = fh.getframerate()
            best["audio_seconds"] = round(seconds, 3)
            best["rtf"] = round(float(best["wall_ms"]) / 1000.0 / seconds, 4) if seconds else None
            rows.append(best)

    ok = [row for row in rows if row.get("rtf") is not None]
    rtfs = sorted(float(row["rtf"]) for row in ok)  # type: ignore[arg-type]
    walls = sorted(float(row["wall_ms"]) for row in ok)
    report = {
        "experiment": "32-tts-model-selection",
        "instrument": "gateway_synth_bench.py",
        "engine": "production tts-runtime via gateway (kokoro-82m slot)",
        "voice": args.voice,
        "unstreamed_note": "v1 returns whole-body WAV; TTFA == wall_ms by design",
        "repetitions": args.repetitions,
        "probe_count": len(rows),
        "failure_count": len(failures),
        "failures": failures,
        "wall_ms_median": walls[len(walls) // 2] if walls else None,
        "rtf_median": rtfs[len(rtfs) // 2] if rtfs else None,
        "rtf_p95": rtfs[min(len(rtfs) - 1, int(0.95 * len(rtfs)))] if rtfs else None,
        "rows": rows,
    }
    Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"gateway bench: {len(rows)} probes ok, {len(failures)} failures, "
        f"median wall {report['wall_ms_median']} ms, median RTF {report['rtf_median']}"
    )


if __name__ == "__main__":
    main()
