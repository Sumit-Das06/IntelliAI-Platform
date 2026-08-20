"""M36 TTFA benchmark — stream vs whole-body, same texts, same stack.

Definitions (Phase 7, exact):
  TTFB  = wall until the FIRST RESPONSE BYTE arrives (headers done).
  TTFA  = wall until the first PLAYABLE AUDIO byte arrives — the first
          byte AFTER the 44-byte WAV preamble. (An AudioContext player
          schedules immediately, so client TTFA ≈ this + O(ms).)
  total = wall until the last byte.
RTF = synthesis-side realtime factor = total / audio_seconds.

Also measured per text: audio duration (bytes/48000), interior-silence
windows (20 ms RMS < -50 dBFS, first/last 200 ms excluded) — the seam
metric: streaming must not add gaps the whole-body audio lacks.

Usage:
  uv run --package intelliai-evaluation python m36_ttfa_bench.py \
    --api-key-file <path> [--gateway-url http://localhost:8000] \
    --out evidence/m36-ttfa-matrix.json [--audio-dir <dir>] [--concurrency]
"""

from __future__ import annotations

import argparse
import array
import json
import math
import time
from pathlib import Path
from typing import Any

import httpx

TEXTS: list[dict[str, str]] = [
    {"id": "short", "text": "Thank you for calling."},
    {"id": "question", "text": "How are you?"},
    {
        "id": "chars-120",
        "text": (
            "IntelliAI turns text into natural speech. This fixed benchmark "
            "sentence measures synthesis latency and real time factor."
        ),
    },
    {
        "id": "chars-300",
        "text": (
            "Thank you for calling customer care today. Your complaint about the "
            "delayed delivery has been registered, and the reference number is "
            "88231. Our courier partner will contact you within two working days. "
            "Is there anything else at all that I can help you with before we "
            "close this call together?"
        ),
    },
]


def _load_long_texts() -> None:
    ladder = Path(__file__).parent.parent.parent / "34-qwen3-tts" / "long-texts.json"
    cases = {c["id"]: c["text"] for c in json.loads(ladder.read_text(encoding="utf-8"))["cases"]}
    TEXTS.append({"id": "chars-700", "text": cases["m34-len-795"][:700].rsplit(" ", 1)[0] + "."})
    TEXTS.append({"id": "chars-1200", "text": cases["m34-len-1990"][:1200].rsplit(" ", 1)[0] + "."})
    TEXTS.append(
        {"id": "chars-1990", "text": cases["m34-len-1990"][:1990].rsplit(" ", 1)[0] + "."}
    )  # trimmed under the 2000-char law (the untrimmed 2039-char input is
    # correctly REFUSED - that law is battery-tested, not re-proven here)


def interior_silence_windows(pcm: bytes, sample_rate: int = 24_000) -> int:
    samples = array.array("h")
    samples.frombytes(pcm[: len(pcm) - (len(pcm) % 2)])
    window = int(sample_rate * 0.02)
    edge = int(sample_rate * 0.2)
    count = 0
    for start in range(edge, max(edge, len(samples) - edge - window), window):
        chunk = samples[start : start + window]
        rms = math.sqrt(sum(s * s for s in chunk) / len(chunk)) if chunk else 0.0
        if rms < 32768 * 10 ** (-50 / 20):
            count += 1
    return count


def run_once(client: httpx.Client, key: str, text: str, stream: bool) -> dict[str, Any]:
    body = {
        "model": "intelliai-tts",
        "input": text,
        "voice": "english-female",
        "stream": stream,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    started = time.perf_counter()
    ttfb_ms: float | None = None
    ttfa_ms: float | None = None
    received = bytearray()
    with client.stream("POST", "/v1/audio/speech", json=body, headers=headers) as response:
        if response.status_code != 200:
            return {"error": response.status_code}
        for chunk in response.iter_bytes():
            now = (time.perf_counter() - started) * 1000.0
            if ttfb_ms is None and chunk:
                ttfb_ms = now
            received.extend(chunk)
            if ttfa_ms is None and len(received) > 44:
                ttfa_ms = now
    total_ms = (time.perf_counter() - started) * 1000.0
    pcm = bytes(received[44:])
    seconds = len(pcm) / 2 / 24_000
    return {
        "ttfb_ms": round(ttfb_ms or 0.0, 1),
        "ttfa_ms": round(ttfa_ms or 0.0, 1),
        "total_ms": round(total_ms, 1),
        "audio_seconds": round(seconds, 3),
        "rtf": round(total_ms / 1000.0 / seconds, 4) if seconds else None,
        "interior_silence_windows": interior_silence_windows(pcm),
        "bytes": len(received),
        "pcm": pcm,
    }


def concurrency_ladder(base_url: str, key: str, text: str) -> list[dict[str, Any]]:
    import concurrent.futures

    results = []
    for level in (1, 2, 4, 8):
        with httpx.Client(base_url=base_url, timeout=300.0) as client:
            run_once(client, key, "Warm up run.", True)  # connection + engine warm
            with concurrent.futures.ThreadPoolExecutor(max_workers=level) as pool:
                started = time.perf_counter()
                runs = list(pool.map(lambda _: run_once(client, key, text, True), range(level)))
                wall = time.perf_counter() - started
        ok = [r for r in runs if "error" not in r]
        ttfas = sorted(r["ttfa_ms"] for r in ok)
        results.append(
            {
                "concurrency": level,
                "ok": len(ok),
                "errors": len(runs) - len(ok),
                "ttfa_p50_ms": ttfas[len(ttfas) // 2] if ttfas else None,
                "ttfa_max_ms": ttfas[-1] if ttfas else None,
                "wall_s": round(wall, 2),
                "audio_seconds_total": round(sum(r["audio_seconds"] for r in ok), 2),
            }
        )
        print(f"  c={level}: ok={len(ok)} ttfa_p50={results[-1]['ttfa_p50_ms']} ms")
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gateway-url", default="http://localhost:8000")
    parser.add_argument("--api-key-file", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--audio-dir", default=None)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--concurrency", action="store_true")
    args = parser.parse_args()

    _load_long_texts()
    key = Path(args.api_key_file).read_text(encoding="utf-8").strip()
    audio_dir = Path(args.audio_dir) if args.audio_dir else None
    rows: list[dict[str, Any]] = []

    with httpx.Client(base_url=args.gateway_url, timeout=300.0) as client:
        run_once(client, key, "Warm up run.", True)  # excluded
        for case in TEXTS:
            for mode in ("whole", "stream"):
                best: dict[str, Any] | None = None
                for _ in range(args.repetitions):
                    result = run_once(client, key, case["text"], mode == "stream")
                    if "error" in result:
                        best = result
                        break
                    if best is None or result["ttfa_ms"] < best["ttfa_ms"]:
                        best = result
                if best is None:  # unreachable: repetitions >= 1
                    continue
                pcm = best.pop("pcm", b"")
                if audio_dir is not None and pcm:
                    audio_dir.mkdir(parents=True, exist_ok=True)
                    (audio_dir / f"{case['id']}-{mode}.pcm").write_bytes(pcm)
                rows.append({"id": case["id"], "chars": len(case["text"]), "mode": mode, **best})
                print(
                    f"  {case['id']:<11} {mode:<6} ttfa {best.get('ttfa_ms')} ms "
                    f"total {best.get('total_ms')} ms audio {best.get('audio_seconds')} s"
                )

        ladder = (
            concurrency_ladder(args.gateway_url, key, TEXTS[2]["text"])
            if args.concurrency
            else None
        )

    report = {
        "experiment": "36-tts-streaming",
        "instrument": "m36_ttfa_bench.py",
        "definitions": {
            "ttfb_ms": "first response byte",
            "ttfa_ms": "first byte past the 44-byte WAV preamble (first playable audio)",
            "total_ms": "last byte",
        },
        "gateway": args.gateway_url,
        "repetitions": f"best-of-{args.repetitions} by ttfa",
        "rows": rows,
        "stream_concurrency_ladder": ladder,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"recorded: {out}")


if __name__ == "__main__":
    main()
