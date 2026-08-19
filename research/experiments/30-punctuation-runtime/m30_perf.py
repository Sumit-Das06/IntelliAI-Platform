"""M30 — performance of the PRODUCTION punctuation wrapper (dev box).

Measures the code that ships (`PunctuationRestorer`), not the research
decoder: warm-disk load, per-tier latency (model + word-copy write,
best of 3), RAM working set, and a 4-way concurrent burst through the
shared ONNX session. Development-machine numbers — NOT a production SLA;
the deploy box re-ladders before any production enable.

Run: uv run --package intelliai-stt-runtime python .../m30_perf.py
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from intelliai_runtime_contract import TranscriptionResult, TranscriptionSegment
from intelliai_stt_runtime.engines.punctuation import load_punctuation

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ARTIFACT_DIR = ROOT / "models/punct-cap-seg-47/v1"
RESULT = ROOT / "ml/evaluation/stt/results/2026-08-18-research-qwen3-asr-0.6b-hi-ft-e3-hi-m23.json"
CHARS_PER_SECOND = 12.18
TIERS = {"5s": 5, "30s": 30, "120s": 120, "300s": 300, "600s": 600}


class _PMC(ctypes.Structure):
    _fields_ = [
        ("cb", wt.DWORD),
        ("PageFaultCount", wt.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def rss_mib() -> tuple[float, float]:
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    fn = k32.K32GetProcessMemoryInfo
    fn.argtypes = [wt.HANDLE, ctypes.POINTER(_PMC), wt.DWORD]
    fn.restype = wt.BOOL
    pmc = _PMC()
    pmc.cb = ctypes.sizeof(_PMC)
    if not fn(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
        raise OSError(ctypes.get_last_error())
    return (
        round(pmc.WorkingSetSize / (1024 * 1024), 1),
        round(pmc.PeakWorkingSetSize / (1024 * 1024), 1),
    )


def tier_inputs() -> dict[str, str]:
    clips = json.loads(RESULT.read_text(encoding="utf-8"))["clips"]
    hyps = sorted(
        (c["hypothesis_text"] for c in clips if (c.get("hypothesis_text") or "").strip()),
        key=len,
        reverse=True,
    )
    inputs: dict[str, str] = {}
    for tier, seconds in TIERS.items():
        target = int(seconds * CHARS_PER_SECOND)
        acc: list[str] = []
        for h in hyps:
            if sum(len(a) + 1 for a in acc) >= target:
                break
            acc.append(h)
        inputs[tier] = " ".join(acc)[: target + 200]
    return inputs


def wrap(text: str) -> TranscriptionResult:
    return TranscriptionResult(
        text=text,
        language="hi",
        duration_seconds=1.0,
        segments=(TranscriptionSegment(start_seconds=0.0, end_seconds=1.0, text=text),),
    )


def main() -> None:
    inputs = tier_inputs()
    rss_before, _ = rss_mib()
    t0 = time.perf_counter()
    restorer = load_punctuation(ARTIFACT_DIR, languages=("hi",), timeout_ms=10_000)
    load_s = round(time.perf_counter() - t0, 2)
    rss_loaded, _ = rss_mib()
    restorer.restore_safely(wrap(inputs["5s"]), "hi")  # warmup

    tiers: dict[str, dict] = {}
    for tier, text in inputs.items():
        best = None
        for _ in range(3):
            t0 = time.perf_counter()
            outcome = restorer.restore_safely(wrap(text), "hi")
            elapsed = time.perf_counter() - t0
            best = elapsed if best is None or elapsed < best else best
        tiers[tier] = {
            "input_chars": len(text),
            "latency_seconds_best_of_3": round(best, 3),
            "applied": outcome.applied,
        }
        print(f"{tier}: {tiers[tier]['latency_seconds_best_of_3']}s applied={outcome.applied}")

    # 4-way concurrent burst on the 30s tier through the shared session
    burst_text = inputs["30s"]
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(restorer.restore_safely, wrap(burst_text), "hi") for _ in range(4)]
        outcomes = [future.result() for future in futures]
    burst_wall = round(time.perf_counter() - t0, 3)
    if not all(o.applied for o in outcomes):
        msg = "concurrent burst produced an unapplied outcome"
        raise SystemExit(msg)

    rss_after, rss_peak = rss_mib()
    evidence = {
        "experiment": "30-punctuation-runtime",
        "phase": "production-wrapper performance (development machine - NOT an SLA)",
        "cpu_logical_cores": os.cpu_count(),
        "warm_disk_load_seconds": load_s,
        "rss_mib": {
            "python_baseline": rss_before,
            "after_load": rss_loaded,
            "after_all": rss_after,
            "peak": rss_peak,
        },
        "tiers": tiers,
        "concurrent_burst": {
            "requests": 4,
            "tier": "30s",
            "wall_seconds": burst_wall,
            "note": "shared ONNX session, 4 worker threads",
        },
    }
    (HERE / "perf-runtime.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"load={load_s}s burst4x30s={burst_wall}s rss_peak={rss_peak}MiB")
    restorer.close()


if __name__ == "__main__":
    sys.exit(main())
