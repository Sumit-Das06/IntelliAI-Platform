"""M29B — performance tiers for lead model + word-copy decoder (venv).

Separates the two costs the milestone asks for:
  model latency   = WordCopyPunctuator.predict_marks (tokenize + ONNX)
  decoder latency = apply_marks (pure string assembly)

Tier inputs are the M29A construction: REAL E3 hypotheses concatenated to
each duration's char-equivalent at 12.18 chars/sec. Development-machine
numbers, NOT a production SLA. PYTHONIOENCODING=utf-8.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))

from wordcopy_decoder import WordCopyPunctuator  # noqa: E402

from intelliai_evaluation.punctuation import apply_marks, invariant_holds  # noqa: E402

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
    ws = pmc.WorkingSetSize / (1024 * 1024)
    peak = pmc.PeakWorkingSetSize / (1024 * 1024)
    return round(ws, 1), round(peak, 1)


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
    decoder = WordCopyPunctuator()
    warm_load = round(time.perf_counter() - t0, 2)
    rss_loaded, _ = rss_mib()
    decoder.punctuate(inputs["5s"])  # warmup

    tiers: dict[str, dict] = {}
    for tier, text in inputs.items():
        best_model = best_apply = None
        for _ in range(3):
            t0 = time.perf_counter()
            marks = decoder.predict_marks(text)
            model_s = time.perf_counter() - t0
            t0 = time.perf_counter()
            out = apply_marks(text, marks)
            apply_s = time.perf_counter() - t0
            best_model = model_s if best_model is None or model_s < best_model else best_model
            best_apply = apply_s if best_apply is None or apply_s < best_apply else best_apply
        tiers[tier] = {
            "input_chars": len(text),
            "model_latency_seconds": round(best_model, 3),
            "decoder_latency_seconds": round(best_apply, 5),
            "total_latency_seconds": round(best_model + best_apply, 3),
            "invariant": "PASS" if invariant_holds(text, out) else "FAIL",
            "marks_added": {
                "danda": out.count("।"),
                "comma": out.count(","),
                "question_mark": out.count("?"),
            },
        }
        t = tiers[tier]
        print(
            f"{tier}: model={t['model_latency_seconds']}s "
            f"decoder={t['decoder_latency_seconds']}s "
            f"total={t['total_latency_seconds']}s inv={t['invariant']}"
        )

    rss_after, rss_peak = rss_mib()
    evidence = {
        "experiment": "29b-hindi-punctuation-eval",
        "phase": "performance-tiers word-copy (development machine - NOT production SLA)",
        "cpu_logical_cores": os.cpu_count(),
        "cold_load_including_download_seconds": {"value": 36.3, "label": "MEASURED once in M28"},
        "warm_disk_load_seconds": warm_load,
        "rss_mib": {
            "python_baseline": rss_before,
            "after_load": rss_loaded,
            "after_all_tiers": rss_after,
            "peak": rss_peak,
        },
        "tiers": tiers,
    }
    (HERE / "perf-tiers-v2.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"load={warm_load}s rss_peak={rss_peak}MiB")


if __name__ == "__main__":
    sys.exit(main())
