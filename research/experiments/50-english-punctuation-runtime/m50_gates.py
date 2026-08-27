"""M50 gates harness — runs the SHIPPED English punctuation stage
(`intelliai_stt_runtime.engines.punctuation_en`) against the frozen
en-punct-eval@v1 set and the operational gates (latency, long-text,
edge cases, concurrency, memory).

Everything here measures the exact code path production would execute:
the artifact under models/punct-en-kredor/v1, the shipped windowing,
the shipped timeout seam. Nothing is re-implemented.

Modes:
    python m50_gates.py quality      # Phase 12 — frozen eval through the stage
    python m50_gates.py latency      # Phase 11 — size ladder, cold + warm p50/p95
    python m50_gates.py long         # Phase 14 — 30s/2m/5m/10m transcripts
    python m50_gates.py edge         # Phase 23 — invariant edge battery
    python m50_gates.py concurrency  # Phase 24 — c=1/2/4/8 on the shared stage
    python m50_gates.py memory       # Phase 10 — RSS in THIS fresh process
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for rel in (
    "services/stt-runtime/src",
    "packages/runtime-contract/src",
    "packages/runtime-core/src",
    "ml/evaluation/src",
):
    candidate = ROOT / rel
    if candidate.exists():
        sys.path.insert(0, str(candidate))

from intelliai_evaluation.punctuation import (  # noqa: E402
    load_punctuation_dataset,
    score_pair,
    strip_punctuation_for_input,
)
from intelliai_runtime_contract import TranscriptionResult, TranscriptionSegment  # noqa: E402
from intelliai_stt_runtime.engines.punctuation import depunct  # noqa: E402
from intelliai_stt_runtime.engines.punctuation_en import load_punctuation_en  # noqa: E402

ARTIFACT_DIR = ROOT / "models" / "punct-en-kredor" / "v1"
DATASET = ROOT / "ml" / "evaluation" / "punctuation" / "datasets" / "en-punct-eval-v1.json"
EVIDENCE = HERE / "evidence"
# The shipped production defaults (config.py): timeout 3000 ms. The gate
# runs run WITH that timeout so a too-slow request fails loudly here.
TIMEOUT_MS = 3000.0
LANGS = ("en", "en-US", "en-IN")


def _result(text: str) -> TranscriptionResult:
    # Shaped like a real engine result: segments cover the transcript.
    return TranscriptionResult(
        text=text,
        language="en",
        duration_seconds=1.0,
        segments=(TranscriptionSegment(start_seconds=0.0, end_seconds=1.0, text=text),),
    )


def _load():
    return load_punctuation_en(ARTIFACT_DIR, languages=LANGS, timeout_ms=TIMEOUT_MS)


def _rss_bytes() -> tuple[int, int]:
    """(working_set, peak_working_set) of this process, no dependencies."""

    class PMC(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.wintypes.DWORD),
            ("PageFaultCount", ctypes.wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    pmc = PMC()
    pmc.cb = ctypes.sizeof(PMC)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [
        ctypes.wintypes.HANDLE,
        ctypes.POINTER(PMC),
        ctypes.wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo.restype = ctypes.wintypes.BOOL
    if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
        msg = f"GetProcessMemoryInfo failed: {ctypes.get_last_error()}"
        raise OSError(msg)
    return int(pmc.WorkingSetSize), int(pmc.PeakWorkingSetSize)


def _mib(n: int) -> float:
    return round(n / (1024 * 1024), 1)


def _eval_words() -> list[str]:
    """A deterministic English word stream from the frozen eval set."""
    dataset = load_punctuation_dataset(DATASET)
    words: list[str] = []
    for row in dataset.rows:
        words.extend(strip_punctuation_for_input(row.reference_text).split())
    return words


def _make_text(words: list[str], count: int) -> str:
    out: list[str] = []
    while len(out) < count:
        out.extend(words[: count - len(out)])
    return " ".join(out)


def _percentiles(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)
    p50 = statistics.median(ordered)
    p95 = ordered[min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))]
    return {"p50_ms": round(p50, 1), "p95_ms": round(p95, 1)}


def _write(name: str, payload: dict) -> None:
    EVIDENCE.mkdir(exist_ok=True)
    path = EVIDENCE / name
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


# ── Phase 12: quality on the frozen eval through the shipped stage ──────


def run_quality() -> None:
    dataset = load_punctuation_dataset(DATASET)
    restorer = _load()
    from intelliai_evaluation.punctuation import CorpusScore

    overall = CorpusScore()
    by_domain: dict[str, CorpusScore] = {}
    not_applied: list[str] = []
    try:
        for row in dataset.rows:
            raw = strip_punctuation_for_input(row.reference_text)
            outcome = restorer.restore_safely(_result(raw), "en")
            predicted = outcome.result.text
            if not outcome.applied and predicted != raw:
                not_applied.append(row.id)
            pair = score_pair(row.reference_text, predicted)
            domain = by_domain.setdefault(row.domain, CorpusScore())
            for corpus in (overall, domain):
                corpus.rows += 1
                if not pair.aligned:
                    corpus.invariant_failures += 1
                    continue
                corpus.aligned_rows += 1
                corpus.micro.add(pair.micro)
                for mark, counts in pair.per_mark.items():
                    corpus.per_mark[mark].add(counts)
                corpus.boundary.add(pair.boundary)
    finally:
        restorer.close()
    _write(
        "quality-shipped-stage.json",
        {
            "dataset": DATASET.name,
            "stage": "intelliai_stt_runtime.engines.punctuation_en (shipped)",
            "timeout_ms": TIMEOUT_MS,
            "overall": overall.as_dict(),
            "per_domain": {domain: score.as_dict() for domain, score in by_domain.items()},
            "stage_errors_fail_open": not_applied,
        },
    )


# ── Phase 11: latency ladder ─────────────────────────────────────────────


def run_latency() -> None:
    words = _eval_words()
    ladder = {
        "sentence_1": "the meeting is scheduled for tomorrow morning at nine",
        "sentence_3": _make_text(words, 40),
        "words_100": _make_text(words, 100),
        "words_300": _make_text(words, 300),
        "words_700": _make_text(words, 700),
        "words_1200": _make_text(words, 1200),
        "words_2000": _make_text(words, 2000),
    }
    restorer = _load()
    results: dict[str, dict] = {}
    try:
        # Cold: the very first inference this process (session warm-up).
        cold_text = ladder["words_300"]
        started = time.perf_counter()
        restorer.restore_safely(_result(cold_text), "en")
        cold_ms = (time.perf_counter() - started) * 1000.0
        for name, text in ladder.items():
            samples: list[float] = []
            applied = True
            for _ in range(15):
                started = time.perf_counter()
                outcome = restorer.restore_safely(_result(text), "en")
                samples.append((time.perf_counter() - started) * 1000.0)
                applied = applied and (outcome.applied or outcome.result.text == text)
            results[name] = {
                "words": len(text.split()),
                **_percentiles(samples),
                "min_ms": round(min(samples), 1),
                "max_ms": round(max(samples), 1),
                "no_stage_error": applied,
            }
    finally:
        restorer.close()
    _write(
        "latency-ladder.json",
        {
            "timeout_ms": TIMEOUT_MS,
            "cold_first_inference_ms_words_300": round(cold_ms, 1),
            "warm_iterations": 15,
            "ladder": results,
        },
    )


# ── Phase 14: long transcripts ───────────────────────────────────────────


def run_long() -> None:
    words = _eval_words()
    # ~150 spoken words/minute.
    sizes = {"30s_75w": 75, "2min_300w": 300, "5min_750w": 750, "10min_1500w": 1500}
    restorer = _load()
    results: dict[str, dict] = {}
    try:
        for name, count in sizes.items():
            text = _make_text(words, count)
            started = time.perf_counter()
            outcome = restorer.restore_safely(_result(text), "en")
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            out = outcome.result.text
            results[name] = {
                "input_words": len(text.split()),
                "output_words": len(out.split()),
                "words_preserved_exactly": depunct(text) == depunct(out),
                "applied": outcome.applied,
                "latency_ms": round(elapsed_ms, 1),
                "input_chars": len(text),
                "output_chars": len(out),
            }
    finally:
        restorer.close()
    rss, peak = _rss_bytes()
    _write(
        "long-transcripts.json",
        {"results": results, "process_rss_mib": _mib(rss), "process_peak_rss_mib": _mib(peak)},
    )


# ── Phase 23: edge cases ─────────────────────────────────────────────────

EDGES = [
    "the M16 rifle was used in the incident",
    "the pH of the solution is 7.4 today",
    "the meeting is at 3 pm GMT on friday",
    "TMZ reported the story first",
    "visit example.com today",
    "email test@example.com tomorrow",
    "the version is 2.5 today",
    "call me at 98765 43210 tomorrow morning",
    "the price is 1499.99 rupees",
    "we launched IntelliAI Console last week did you see it",
    "the deadline is 26 august 2026 can we make it",
    "namaste doston welcome to the channel aaj hum baat karenge",
    "run pip install numpy then import numpy as np",
    "the file is at C:\\Users\\demo\\report.pdf check it",
]


def run_edge() -> None:
    restorer = _load()
    rows = []
    try:
        for text in EDGES:
            outcome = restorer.restore_safely(_result(text), "en")
            out = outcome.result.text
            rows.append(
                {
                    "input": text,
                    "output": out,
                    "invariant_holds": depunct(text) == depunct(out),
                    "applied": outcome.applied,
                }
            )
    finally:
        restorer.close()
    failures = [row for row in rows if not row["invariant_holds"]]
    _write("edge-cases.json", {"rows": rows, "invariant_failures": len(failures)})


# ── Phase 24: concurrency ────────────────────────────────────────────────


def run_concurrency() -> None:
    words = _eval_words()
    text = _make_text(words, 300)
    restorer = _load()
    results: dict[str, dict] = {}
    try:
        restorer.restore_safely(_result(text), "en")  # warm the session once

        def one() -> tuple[float, bool]:
            started = time.perf_counter()
            outcome = restorer.restore_safely(_result(text), "en")
            elapsed = (time.perf_counter() - started) * 1000.0
            # fail-open path taken (timeout under contention counts as
            # an observation, not a crash — recorded honestly)
            failed_open = not outcome.applied and outcome.result.text == text
            return elapsed, failed_open

        for c in (1, 2, 4, 8):
            rss_before, _ = _rss_bytes()
            started_all = time.perf_counter()
            with ThreadPoolExecutor(max_workers=c) as pool:
                observations = [future.result() for future in [pool.submit(one) for _ in range(16)]]
            wall = (time.perf_counter() - started_all) * 1000.0
            samples = [elapsed for elapsed, _ in observations]
            errors = sum(1 for _, failed_open in observations if failed_open)
            rss_after, peak = _rss_bytes()
            results[f"c{c}"] = {
                "requests": 16,
                **_percentiles(samples),
                "wall_ms": round(wall, 1),
                "fail_open_count": errors,
                "rss_before_mib": _mib(rss_before),
                "rss_after_mib": _mib(rss_after),
                "peak_rss_mib": _mib(peak),
            }
    finally:
        restorer.close()
    _write("concurrency.json", {"input_words": 300, "results": results})


# ── Phase 10: memory (run in a FRESH process) ────────────────────────────


def run_memory() -> None:
    words_baseline, _ = _rss_bytes()
    started = time.perf_counter()
    restorer = _load()
    load_ms = (time.perf_counter() - started) * 1000.0
    loaded, _ = _rss_bytes()
    words = _eval_words()
    text = _make_text(words, 300)
    try:
        started = time.perf_counter()
        restorer.restore_safely(_result(text), "en")
        first_ms = (time.perf_counter() - started) * 1000.0
        after_first, _ = _rss_bytes()
        for _ in range(30):
            restorer.restore_safely(_result(text), "en")
        after_30, peak = _rss_bytes()
    finally:
        restorer.close()
    _write(
        "memory-gate.json",
        {
            "gate_mib": 700,
            "baseline_mib": _mib(words_baseline),
            "after_load_mib": _mib(loaded),
            "after_first_request_mib": _mib(after_first),
            "after_30_requests_mib": _mib(after_30),
            "peak_mib": _mib(peak),
            "delta_from_baseline_mib": _mib(after_30 - words_baseline),
            "load_ms": round(load_ms, 1),
            "cold_first_request_ms_words_300": round(first_ms, 1),
            "verdict": "PASS" if peak <= 700 * 1024 * 1024 else "FAIL",
        },
    )


MODES = {
    "quality": run_quality,
    "latency": run_latency,
    "long": run_long,
    "edge": run_edge,
    "concurrency": run_concurrency,
    "memory": run_memory,
}

if __name__ == "__main__":
    MODES[sys.argv[1]]()
