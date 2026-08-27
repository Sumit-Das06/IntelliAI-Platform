"""M52 streaming simulator — measures what a realtime STT session would
feel like on THIS machine using the CURRENT production engine
(faster-whisper whisper-small INT8, CPU), without touching production.

The simulator replays a WAV as if a microphone produced it in
`chunk_ms` frames on a virtual clock, and re-decodes the active window
whenever the (single) decoder is free — the honest model of a stack
whose engine has NO incremental state (repo-verified: faster-whisper
and llama.cpp both decode a complete clip per call). Decode compute is
REAL (measured wall time); only the microphone timeline is virtual.

Window policies:
    growing              — window = everything since session start
    rolling              — window capped (25 s); segments older than a
                           5 s margin are COMMITTED and never re-decoded
                           (the long-session policy)

    python sim_streaming.py <wav> <language> <chunk_ms> <growing|rolling> <out.json> \
        [model_name=whisper-small] [partial_beam=5]

`partial_beam` applies to IN-SESSION decodes only; the offline
reference and the final decode always use the production default
(beam 5), so a greedy-partials configuration still finishes with
production-quality text.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import itertools
import json
import os
import statistics
import sys
import time
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EVIDENCE = HERE / "evidence"
sys.path.insert(0, str(ROOT / "services/stt-runtime/src"))
sys.path.insert(0, str(ROOT / "ml/evaluation/src"))

from intelliai_evaluation.wer import normalize_words, word_error_rate  # noqa: E402

MAX_WINDOW_S = 25.0
COMMIT_MARGIN_S = 5.0


def _rss_mib() -> float:
    if sys.platform != "win32":
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return round(int(line.split()[1]) / 1024, 1)
        return 0.0

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
    kernel32 = ctypes.WinDLL("kernel32")
    psapi = ctypes.WinDLL("psapi")
    kernel32.GetCurrentProcess.restype = ctypes.wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [
        ctypes.wintypes.HANDLE,
        ctypes.POINTER(PMC),
        ctypes.wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
    return round(pmc.WorkingSetSize / (1024 * 1024), 1)


def load_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as handle:
        if handle.getframerate() != 16_000 or handle.getnchannels() != 1:
            msg = "need 16 kHz mono WAV"
            raise ValueError(msg)
        pcm = np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16)
    return pcm.astype(np.float32) / 32768.0


def words_lcp(previous: list[str], current: list[str]) -> int:
    n = 0
    for a, b in zip(previous, current, strict=False):
        if a != b:
            break
        n += 1
    return n


def adjacent_repeat(text: str, n: int = 3) -> bool:
    words = normalize_words(text)
    grams = [tuple(words[i : i + n]) for i in range(len(words) - n + 1)]
    return any(grams[i] == grams[i + n] for i in range(len(grams) - n))


def main() -> None:
    wav_path, language, chunk_ms_s, mode, out_name = sys.argv[1:6]
    model_name = sys.argv[6] if len(sys.argv) > 6 else "whisper-small"
    partial_beam = int(sys.argv[7]) if len(sys.argv) > 7 else 5
    chunk_s = int(chunk_ms_s) / 1000.0
    audio = load_wav(Path(wav_path))
    total_s = len(audio) / 16_000.0

    from faster_whisper import WhisperModel

    model = WhisperModel(
        str(ROOT / "models" / model_name / "v1"), device="cpu", compute_type="int8"
    )

    def decode(window: np.ndarray, beam: int) -> tuple[str, list[tuple[float, float, str]], float]:
        started = time.perf_counter()
        segments, _info = model.transcribe(
            window,
            task="transcribe",
            language=language,
            beam_size=beam,
            vad_filter=False,
            condition_on_previous_text=False,
        )
        rows = [(segment.start, segment.end, segment.text) for segment in segments]
        elapsed = time.perf_counter() - started
        text = "".join(row[2] for row in rows).strip()
        return text, rows, elapsed

    # Offline reference: one full-clip decode, exactly the current product
    # (this also warms the model, like a long-lived serving process).
    offline_text, _, offline_s = decode(audio, 5)

    committed = ""
    window_start = 0.0
    clock = chunk_s  # first chunk has arrived
    events: list[dict] = []
    partial_texts: list[str] = []
    decode_rtfs: list[float] = []

    while True:
        available = min(total_s, max(clock, chunk_s))
        available = (int(available / chunk_s)) * chunk_s  # whole chunks only
        if total_s - available < chunk_s:  # the tail partial chunk arrives with the end
            available = total_s
        window = audio[int(window_start * 16_000) : int(available * 16_000)]
        is_final = available >= total_s
        text, rows, elapsed = decode(window, 5 if is_final else partial_beam)
        clock = max(clock, available) + elapsed
        partial = (committed + " " + text).strip()
        events.append(
            {
                "audio_available_s": round(available, 2),
                "done_at_s": round(clock, 2),
                "latency_ms": round((clock - available) * 1000.0, 1),
                "decode_ms": round(elapsed * 1000.0, 1),
                "window_s": round(available - window_start, 2),
                "chars": len(partial),
            }
        )
        partial_texts.append(partial)
        if available - window_start > 0:
            decode_rtfs.append(elapsed / (available - window_start))

        if mode == "rolling" and (available - window_start) > MAX_WINDOW_S:
            # Commit whole segments older than the margin; they leave the
            # window and are never re-decoded (bounded compute + memory).
            cutoff = (available - window_start) - COMMIT_MARGIN_S
            commit_rows = [row for row in rows if row[1] <= cutoff]
            if commit_rows and len(commit_rows) == len(rows):
                commit_rows = rows[:-1]  # always keep the newest segment live
            if commit_rows:
                committed = (committed + "".join(row[2] for row in commit_rows)).strip()
                window_start += commit_rows[-1][1]

        if available >= total_s:
            break
        if clock >= total_s and available >= total_s:
            break

    final_text = partial_texts[-1]
    finalization_ms = events[-1]["latency_ms"]

    fpt_ms = None
    for event, text in zip(events, partial_texts, strict=True):
        if text:
            fpt_ms = event["done_at_s"] * 1000.0
            break

    ratios = []
    churn = 0
    for previous, current in itertools.pairwise(partial_texts):
        p_words, c_words = previous.split(), current.split()
        if not p_words:
            continue
        lcp = words_lcp(p_words, c_words)
        ratios.append(lcp / len(p_words))
        if lcp < len(p_words):
            churn += 1

    gaps = [b["done_at_s"] - a["done_at_s"] for a, b in itertools.pairwise(events)]
    latencies = [event["latency_ms"] for event in events[:-1]] or [0.0]

    streamed_wer = word_error_rate(offline_text, final_text).wer if offline_text else None

    payload = {
        "wav": Path(wav_path).name,
        "language": language,
        "chunk_ms": int(chunk_ms_s),
        "mode": mode,
        "audio_seconds": round(total_s, 2),
        "engine": f"faster-whisper {model_name} INT8 CPU, partial_beam={partial_beam}, "
        "final/offline beam=5, condition_on_previous_text=False",
        "offline_decode_s": round(offline_s, 2),
        "offline_rtf": round(offline_s / total_s, 3),
        "events": events,
        "updates": len(events),
        "fpt_ms": round(fpt_ms, 1) if fpt_ms else None,
        "update_latency_ms": {
            "p50": round(statistics.median(latencies), 1),
            "max": round(max(latencies), 1),
        },
        "effective_cadence_s": round(statistics.median(gaps), 2) if gaps else None,
        "finalization_ms": finalization_ms,
        "decode_rtf": {
            "p50": round(statistics.median(decode_rtfs), 3),
            "max": round(max(decode_rtfs), 3),
        },
        "stability": {
            "stable_token_ratio_mean": round(statistics.mean(ratios), 3) if ratios else 1.0,
            "stable_token_ratio_min": round(min(ratios), 3) if ratios else 1.0,
            "rewrite_events": churn,
            "partials": len(partial_texts),
        },
        "final_vs_offline_wer": round(streamed_wer, 4) if streamed_wer is not None else None,
        "adjacent_3gram_repeat": adjacent_repeat(final_text),
        "final_text": final_text,
        "offline_text": offline_text,
        "rss_mib_end": _rss_mib(),
    }
    EVIDENCE.mkdir(exist_ok=True)
    (EVIDENCE / out_name).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if os.environ.get("M52_SAVE_PARTIALS"):
        (EVIDENCE / (out_name + ".partials.json")).write_text(
            json.dumps(partial_texts, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(
        f"{out_name}: fpt={payload['fpt_ms']}ms cadence={payload['effective_cadence_s']}s "
        f"final={finalization_ms}ms stable={payload['stability']['stable_token_ratio_mean']} "
        f"wer_vs_offline={payload['final_vs_offline_wer']} rtf_p50={payload['decode_rtf']['p50']}"
    )


if __name__ == "__main__":
    main()
