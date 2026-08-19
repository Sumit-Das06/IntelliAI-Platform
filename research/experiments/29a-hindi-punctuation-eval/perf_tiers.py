"""M29A — performance tiers for the lead model (research instrument, venv).

Re-measures the M28 tier benchmark inside this experiment with load-time,
RAM (Windows working set) and CPU context recorded. Development-machine
numbers — NOT a production SLA (the deploy-box re-ladder belongs to the
implementation milestone).

Tier inputs are REAL E3 hypotheses concatenated to the char-equivalent of
each duration at the frozen eval's measured 12.18 chars/sec (M28 baseline).
"Cold load including download" was measured once in M28 (36.3 s); this
instrument measures the disk-cached load, which is what a service restart
would see. PYTHONIOENCODING=utf-8.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import os
import sys
import time
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
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


def depunct(text: str) -> str:
    folded = unicodedata.normalize("NFC", text).casefold()
    cleaned = "".join(" " if unicodedata.category(ch).startswith("P") else ch for ch in folded)
    return " ".join(cleaned.split())


def main() -> None:
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

    rss_before, _ = rss_mib()
    t0 = time.perf_counter()
    from punctuators.models import PunctCapSegModelONNX

    model = PunctCapSegModelONNX.from_pretrained("pcs_47lang")
    warm_disk_load_seconds = round(time.perf_counter() - t0, 2)
    rss_loaded, _ = rss_mib()

    model.infer([inputs["5s"]])  # session warmup

    tiers: dict[str, dict] = {}
    for tier, text in inputs.items():
        best = None
        for _ in range(3):
            t0 = time.perf_counter()
            out = model.infer([text])
            elapsed = time.perf_counter() - t0
            best = elapsed if best is None or elapsed < best else best
        raw = out[0]
        joined = " ".join(raw) if isinstance(raw, list) else str(raw)
        tiers[tier] = {
            "input_chars": len(text),
            "latency_seconds_best_of_3": round(best, 3),
            "invariant": "PASS" if depunct(joined) == depunct(text) else "FAIL",
            "output_chars": len(joined),
            "marks_added": {
                "danda": joined.count("।"),
                "comma": joined.count(","),
                "question_mark": joined.count("?"),
            },
        }
        print(f"{tier}: {tiers[tier]['latency_seconds_best_of_3']}s inv={tiers[tier]['invariant']}")

    rss_after, rss_peak = rss_mib()
    evidence = {
        "experiment": "29a-hindi-punctuation-eval",
        "phase": "performance-tiers (development machine — NOT production SLA)",
        "model": "1-800-BAD-CODE/punct_cap_seg_47_language"
        " @ 1b9d51fc7989ebc61e844d407d9dadd08ff4ba28",
        "cpu_logical_cores": os.cpu_count(),
        "cold_load_including_download_seconds": {
            "value": 36.3,
            "label": "MEASURED once in M28 (first-ever download)",
        },
        "warm_disk_load_seconds": warm_disk_load_seconds,
        "rss_mib": {
            "python_baseline": rss_before,
            "after_model_load": rss_loaded,
            "after_all_tiers": rss_after,
            "peak": rss_peak,
        },
        "chars_per_second_basis": CHARS_PER_SECOND,
        "tiers": tiers,
    }
    out_path = HERE / "perf-tiers.json"
    out_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"load={warm_disk_load_seconds}s rss_peak={rss_peak}MiB")
    print(f"written: {out_path}")


if __name__ == "__main__":
    sys.exit(main())
