"""M38 — Kokoro-hi in-process concurrency probe (research instrument only).

Threads share ONE loaded upstream KPipeline (lang 'h') — the same
one-model-many-requests shape the production runtime uses — and synthesize
the same fixed ~300-char Hindi text at c=1/2/4/8. torch releases the GIL
inside the model pass, so threads approximate the runtime's worker pool.

NOT a production capacity claim: WSL venv, upstream pipeline, no gateway,
no admission law. It answers one research question: how does Hindi
synthesis throughput degrade under concurrent load on this machine?

Run inside the research venv (WSL):
    python m38_concurrency_probe.py --probes probe-texts-hi-v1.json \
        --case-id m38-ladder-300 --voice hf_alpha --out m38-kokoro-hi-concurrency.json
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probes", required=True)
    parser.add_argument("--case-id", default="m38-ladder-300")
    parser.add_argument("--voice", default="hf_alpha")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    cases = json.loads(Path(args.probes).read_text(encoding="utf-8"))["cases"]
    text = next(case["text"] for case in cases if case["id"] == args.case_id)

    from kokoro import KModel, KPipeline

    model = KModel().eval()
    pipeline = KPipeline(lang_code="h", model=model)

    # MEASURED (this instrument, first run): the in-process espeak chain is
    # NOT thread-safe - concurrent phonemize calls corrupt espeak's shared
    # buffer (UnicodeDecodeError on garbage bytes). The G2P step is therefore
    # serialized behind a lock; model passes stay concurrent. This mirrors
    # the production shape, where G2P is an isolated subprocess per call and
    # the torch pass dominates wall time.
    import threading

    g2p_lock = threading.Lock()
    original_g2p = pipeline.g2p

    def locked_g2p(text: str):
        with g2p_lock:
            return original_g2p(text)

    pipeline.g2p = locked_g2p

    def synthesize() -> tuple[float, float]:
        started = time.perf_counter()
        seconds = 0.0
        for result in pipeline(text, voice=args.voice):
            audio = getattr(result, "audio", None)
            if audio is not None:
                seconds += float(audio.shape[-1]) / 24_000.0
        return time.perf_counter() - started, seconds

    synthesize()  # warm-up, excluded

    levels = []
    for level in (1, 2, 4, 8):
        with concurrent.futures.ThreadPoolExecutor(max_workers=level) as pool:
            started = time.perf_counter()
            runs = list(pool.map(lambda _: synthesize(), range(level)))
            wall = time.perf_counter() - started
        walls = sorted(run[0] for run in runs)
        audio_total = sum(run[1] for run in runs)
        levels.append(
            {
                "concurrency": level,
                "wall_s": round(wall, 2),
                "per_request_p50_s": round(walls[len(walls) // 2], 2),
                "per_request_max_s": round(walls[-1], 2),
                "audio_seconds_total": round(audio_total, 2),
                "throughput_audio_seconds_per_wall_second": round(audio_total / wall, 2),
            }
        )
        print(levels[-1])

    report = {
        "experiment": "38-hindi-tts-selection",
        "instrument": "m38_concurrency_probe.py",
        "engine": "kokoro-hi (upstream KPipeline, research venv)",
        "voice": args.voice,
        "case_id": args.case_id,
        "chars": len(text),
        "note": (
            "research-only in-process thread ladder; NOT production capacity - "
            "no gateway, no admission law, WSL venv"
        ),
        "levels": levels,
    }
    Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"recorded: {args.out}")


if __name__ == "__main__":
    main()
