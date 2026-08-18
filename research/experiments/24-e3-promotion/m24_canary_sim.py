"""M24 Phase 11: local mixed-traffic canary simulation, E3 challenger.

NOT a production canary and NOT ledger evidence: one machine, research
runtime, frozen-eval audio. What it CAN honestly measure is the
operational shape of the proposed split running through ONE multi-slot
process — error rate per arm, latency per arm, and whether mixed
routing destabilizes either engine. Quality is not re-measured here;
the M23/M24 EvalRuns own that.

The split is deterministic (seeded), the clip cycle is fixed, and each
request pins its artifact exactly the way registry resolution would
downstream — this simulates the ROUTING OUTCOME, not the registry.
Escalation ladder per the milestone: 90/10 first; 25/75 and 50/50 only
if 90/10 is clean.
"""

from __future__ import annotations

import argparse
import datetime
import json
import random
import statistics
import time
from pathlib import Path

import httpx

CLIPS = [
    "indicvoices/hindi/valid/indicvoices-hindi-valid-0-001287.flac",  # median 6.9 s
    "indicvoices/hindi/valid/indicvoices-hindi-valid-0-000462.flac",
    "indicvoices/hindi/valid/indicvoices-hindi-valid-0-002151.flac",
    "indicvoices/hindi/valid/indicvoices-hindi-valid-0-004235.flac",
    "indicvoices/hindi/valid/indicvoices-hindi-valid-0-001914.flac",
]
INCUMBENT = "whisper-small"
CHALLENGER = "qwen3-asr-0.6b-hi-ft-e3"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8011")
    parser.add_argument("--data-root", type=Path, default=Path("ml/datasets/data"))
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--challenger-share", type=float, default=0.10)
    parser.add_argument("--seed", type=int, default=20260818)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    rng = random.Random(args.seed)  # noqa: S311 — deterministic traffic plan, not cryptography
    plan = [
        CHALLENGER if rng.random() < args.challenger_share else INCUMBENT
        for _ in range(args.requests)
    ]
    audio = {clip: (args.data_root / clip).read_bytes() for clip in CLIPS}

    samples: list[dict[str, object]] = []
    with httpx.Client(base_url=args.url, timeout=300.0) as client:
        for index, artifact in enumerate(plan):
            clip = CLIPS[index % len(CLIPS)]
            started = time.perf_counter()
            status = 0
            error_type = None
            try:
                response = client.post(
                    "/v1/transcribe",
                    files={"file": (Path(clip).name, audio[clip], "audio/flac")},
                    data={"params": json.dumps({"language": "hi", "model": artifact})},
                )
                status = response.status_code
                if status != 200:
                    error_type = str(response.json().get("type"))
            except httpx.HTTPError as exc:
                error_type = type(exc).__name__
            samples.append(
                {
                    "artifact": artifact,
                    "clip": clip,
                    "status": status,
                    "error_type": error_type,
                    "client_ms": round((time.perf_counter() - started) * 1000, 1),
                }
            )

    def arm(name: str) -> dict[str, object]:
        rows = [s for s in samples if s["artifact"] == name]
        ok = [s for s in rows if s["status"] == 200]
        latencies = sorted(float(s["client_ms"]) for s in ok)  # type: ignore[arg-type]
        return {
            "requests": len(rows),
            "succeeded": len(ok),
            "failed": len(rows) - len(ok),
            "p50_ms": round(statistics.median(latencies), 1) if latencies else None,
            "p95_ms": (
                round(latencies[min(int(len(latencies) * 0.95), len(latencies) - 1)], 1)
                if latencies
                else None
            ),
            "max_ms": max(latencies) if latencies else None,
        }

    payload = {
        "simulation": f"24-local-canary-challenger-share-{args.challenger_share}",
        "NOT_LEDGER_EVIDENCE": (
            "operational mixed-routing smoke on research runtime; no quality claim"
        ),
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "seed": args.seed,
        "challenger_share": args.challenger_share,
        "incumbent": arm(INCUMBENT),
        "challenger": arm(CHALLENGER),
        "fallback_events": 0,  # no fallback policy exists; recorded as a fact
        "samples": samples,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"incumbent": arm(INCUMBENT), "challenger": arm(CHALLENGER)}, indent=2))
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
