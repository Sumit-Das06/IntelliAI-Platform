"""M39 Hindi TTFA benchmark — stream vs whole-body through the REAL gateway.

The M36 instrument, parameterized for voice and fed the M38 Hindi
ladder (118/298/683/1189/1897 chars) plus a short question — so the
Hindi numbers land on the exact definitions the English ones did:
  TTFB = first response byte; TTFA = first byte past the 44-byte WAV
  preamble; total = last byte; RTF = total / audio_seconds.

Usage:
  uv run --package intelliai-evaluation python m39_ttfa_bench.py \
    --api-key-file <path> --voice hindi-female \
    --out evidence/m39-ttfa-hindi-female.json [--concurrency]
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import httpx

_PROBES = Path(__file__).parent.parent.parent / "38-hindi-tts-selection" / "probe-texts-hi-v1.json"


def load_texts() -> list[dict[str, str]]:
    cases = {
        case["id"]: case["text"]
        for case in json.loads(_PROBES.read_text(encoding="utf-8"))["cases"]
    }
    return [
        {"id": "short-question", "text": cases["m38-spec-name-q"]},
        {"id": "chars-118", "text": cases["m38-ladder-120"]},
        {"id": "chars-298", "text": cases["m38-ladder-300"]},
        {"id": "chars-683", "text": cases["m38-ladder-700"]},
        {"id": "chars-1189", "text": cases["m38-ladder-1200"]},
        {"id": "chars-1897", "text": cases["m38-ladder-2000"]},
    ]


def run_once(client: httpx.Client, key: str, text: str, voice: str, stream: bool) -> dict[str, Any]:
    body = {"model": "intelliai-tts", "input": text, "voice": voice, "stream": stream}
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
    seconds = len(bytes(received[44:])) / 2 / 24_000
    return {
        "ttfb_ms": round(ttfb_ms or 0.0, 1),
        "ttfa_ms": round(ttfa_ms or 0.0, 1),
        "total_ms": round(total_ms, 1),
        "audio_seconds": round(seconds, 3),
        "rtf": round(total_ms / 1000.0 / seconds, 4) if seconds else None,
        "bytes": len(received),
    }


def concurrency_ladder(base_url: str, key: str, text: str, voice: str) -> list[dict[str, Any]]:
    import concurrent.futures

    results = []
    for level in (1, 2, 4, 8):
        with httpx.Client(base_url=base_url, timeout=300.0) as client:
            run_once(client, key, "नमस्ते।", voice, True)  # connection + engine warm
            with concurrent.futures.ThreadPoolExecutor(max_workers=level) as pool:
                started = time.perf_counter()
                runs = list(
                    pool.map(lambda _: run_once(client, key, text, voice, True), range(level))
                )
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
    parser.add_argument("--voice", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--concurrency", action="store_true")
    args = parser.parse_args()

    key = Path(args.api_key_file).read_text(encoding="utf-8").strip()
    texts = load_texts()
    rows: list[dict[str, Any]] = []

    with httpx.Client(base_url=args.gateway_url, timeout=300.0) as client:
        run_once(client, key, "नमस्ते।", args.voice, True)  # excluded
        for case in texts:
            for mode in ("whole", "stream"):
                best: dict[str, Any] | None = None
                for _ in range(args.repetitions):
                    result = run_once(client, key, case["text"], args.voice, mode == "stream")
                    if "error" in result:
                        best = result
                        break
                    if best is None or result["ttfa_ms"] < best["ttfa_ms"]:
                        best = result
                if best is None:  # unreachable: repetitions >= 1
                    continue
                rows.append({"id": case["id"], "chars": len(case["text"]), "mode": mode, **best})
                print(
                    f"  {case['id']:<15} {mode:<6} ttfa {best.get('ttfa_ms')} ms "
                    f"total {best.get('total_ms')} ms audio {best.get('audio_seconds')} s"
                )
        ladder = (
            concurrency_ladder(args.gateway_url, key, texts[2]["text"], args.voice)
            if args.concurrency
            else None
        )

    report = {
        "experiment": "39-hindi-tts-local-web",
        "instrument": "m39_ttfa_bench.py",
        "voice": args.voice,
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
