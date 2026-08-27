"""M52H bench harness — Hindi Qwen3-ASR 0.6B E3 on the RTX 5070.

The GPU runtime is the SAME llama.cpp commit as the production pin
(b10344 / 7a20b417f), CUDA-13.3 variant, serving the UNCHANGED E3 GGUF
artifact — so every delta against the CPU baseline is the backend, not
the build or the weights. Research-only server on 127.0.0.1:8795;
production remains the pinned CPU build.

Requests mirror the production engine byte-for-byte (OpenAI-shaped
`input_audio` + "Transcribe the audio.", temperature 0) and every
benchmark decode sends `cache_prompt: false` so numbers are honest
full-inference costs, never llama-server prefix-cache hits (the cache
effect is recorded separately).

Modes:
    cpu-baseline | gpu-ladder | windows | sim | shorts | probes |
    silence | long | memory | concurrency | quality

    python m52h_bench.py <mode> [args]
"""

from __future__ import annotations

import base64
import json
import statistics
import subprocess
import sys
import time
import urllib.request
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EVIDENCE = HERE / "evidence"
sys.path.insert(0, str(ROOT / "ml/evaluation/src"))
sys.path.insert(0, str(ROOT / "services/stt-runtime/src"))

from intelliai_evaluation.accuracy import score  # noqa: E402
from intelliai_evaluation.normalization import UNICODE_GENERIC_V2  # noqa: E402

SCRATCH = Path(
    r"C:\Users\VIKASH~1\AppData\Local\Temp\claude"
    r"\d--Sumit-Projects-IntelliAI-Platform"
    r"\67762b73-e6aa-43b8-a730-264d0d432d4f\scratchpad"
)
CLIPS = SCRATCH / "m52clips"
H = SCRATCH / "m52hclips"
GPU = "http://127.0.0.1:8795"
CPU_RUNTIME = "http://127.0.0.1:8001/v1/transcribe"
ASR_MARKER = "<asr_text>"
PREFIXES = ("1s", "2s", "3s", "5s", "8s", "12s", "16s", "full")


def parse_asr(raw: str) -> str:
    if ASR_MARKER in raw:
        return raw.partition(ASR_MARKER)[2].strip()
    return raw.strip()


def gpu_decode(wav: bytes, *, cache: bool = False, timeout: float = 300.0) -> tuple[str, float]:
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": base64.b64encode(wav).decode("ascii"),
                            "format": "wav",
                        },
                    },
                    {"type": "text", "text": "Transcribe the audio."},
                ],
            }
        ],
        "temperature": 0.0,
        "max_tokens": 1024,
        "cache_prompt": cache,
    }
    request = urllib.request.Request(  # noqa: S310 — loopback research server
        f"{GPU}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        body = json.loads(response.read())
    elapsed = (time.perf_counter() - started) * 1000.0
    return parse_asr(str(body["choices"][0]["message"]["content"])), elapsed


def cpu_decode(path: Path) -> dict:
    import uuid

    boundary = uuid.uuid4().hex
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="params"\r\n\r\n'
        '{"language": "hi"}\r\n'
    ).encode()
    body += (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{path.name}"\r\nContent-Type: application/octet-stream\r\n\r\n'
    ).encode()
    body += path.read_bytes() + b"\r\n" + f"--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        CPU_RUNTIME,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=900) as response:  # noqa: S310
        envelope = json.loads(response.read())
    return {
        "text": envelope["output"]["text"],
        "inference_ms": round(envelope["timing"]["stages"]["inference"], 1),
        "duration_s": round(envelope["output"]["duration_seconds"], 2),
    }


def wav_bytes_of(path: Path) -> bytes:
    return path.read_bytes()


def slice_wav(path: Path, seconds: float, out: Path) -> Path:
    subprocess.run(  # noqa: S603 — fixed argv (repo law)
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-t", str(seconds), str(out)],  # noqa: S607
        check=True,
    )
    return out


def vram() -> dict:
    out = subprocess.run(
        [  # noqa: S607 — PATH nvidia-smi, research probe
            "nvidia-smi",
            "--query-gpu=memory.used,utilization.gpu",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    used, util = out.split(",")
    return {"vram_used_mib": int(used), "gpu_util_percent": int(util)}


def write(name: str, payload: dict) -> None:
    EVIDENCE.mkdir(exist_ok=True)
    (EVIDENCE / name).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {name}")


def hindi_score(reference: str, hypothesis: str) -> dict:
    scores = score(reference, hypothesis, UNICODE_GENERIC_V2)
    return {"wer": round(scores.wer, 4), "cer": round(scores.cer, 4)}


# ── modes ────────────────────────────────────────────────────────────────


def mode_cpu_baseline() -> None:
    m52 = {
        "1s": 1306.8,
        "2s": 1614.0,
        "3s": 14488.1,
        "5s": 2085.6,
        "8s": 2715.8,
        "12s": 4777.2,
        "16s": 4579.1,
        "full": 7546.0,
    }
    cpu_decode(CLIPS / "hindi_pre_1s.wav")  # warm
    rows = {}
    for name in PREFIXES:
        runs = [cpu_decode(CLIPS / f"hindi_pre_{name}.wav") for _ in range(2)]
        best = min(run["inference_ms"] for run in runs)
        rows[name] = {
            "duration_s": runs[0]["duration_s"],
            "inference_ms": best,
            "m52_reference_ms": m52[name],
        }
        print(name, rows[name])
    write("cpu-baseline.json", {"engine": "staging container (pinned CPU build)", "rows": rows})


def mode_gpu_ladder() -> None:
    gpu_decode(wav_bytes_of(CLIPS / "hindi_pre_1s.wav"))  # warm graphs
    rows = {}
    for name in PREFIXES:
        wav = wav_bytes_of(CLIPS / f"hindi_pre_{name}.wav")
        with wave.open(str(CLIPS / f"hindi_pre_{name}.wav"), "rb") as handle:
            duration = handle.getnframes() / handle.getframerate()
        results = [gpu_decode(wav) for _ in range(3)]
        times = sorted(ms for _, ms in results)
        rows[name] = {
            "duration_s": round(duration, 2),
            "inference_ms_median": round(times[1], 1),
            "rtf_median": round(times[1] / 1000.0 / duration, 3),
            **vram(),
            "text": results[-1][0],
        }
        print(name, rows[name]["inference_ms_median"], "ms rtf", rows[name]["rtf_median"])
    # prompt-cache effect, recorded separately (same audio repeated)
    wav = wav_bytes_of(CLIPS / "hindi_pre_5s.wav")
    gpu_decode(wav, cache=True)
    cached = [gpu_decode(wav, cache=True)[1] for _ in range(3)]
    write(
        "gpu-baseline.json",
        {
            "runtime": "llama.cpp b10344 (7a20b417f) win-cuda-13.3, -ngl 99, same E3 GGUF pins",
            "rows": rows,
            "prompt_cache_repeat_5s_ms": [round(t, 1) for t in cached],
        },
    )


def mode_windows(source_wav: str) -> None:
    source = Path(source_wav)
    H.mkdir(exist_ok=True)
    gpu_decode(wav_bytes_of(CLIPS / "hindi_pre_1s.wav"))  # warm
    rows = {}
    for ms in (250, 500, 750, 1000, 1500, 2000, 3000, 5000):
        clip = slice_wav(source, ms / 1000.0, H / f"win_{ms}ms.wav")
        results = [gpu_decode(wav_bytes_of(clip)) for _ in range(3)]
        times = sorted(t for _, t in results)
        rows[f"{ms}ms"] = {
            "decode_ms_median": round(times[1], 1),
            "keeps_up_at_this_cadence": times[1] < ms,
            "text": results[-1][0][:80],
        }
        print(ms, "ms window ->", rows[f"{ms}ms"]["decode_ms_median"], "ms")
    smallest = next(
        (
            ms
            for ms in (250, 500, 750, 1000, 1500, 2000, 3000, 5000)
            if rows[f"{ms}ms"]["decode_ms_median"] < ms
        ),
        None,
    )
    write("gpu-window-ladder.json", {"rows": rows, "smallest_realtime_window_ms": smallest})


def mode_sim(wav_path: str, mode: str, out_name: str, chunk_ms: int = 500) -> None:
    """Streaming sim over the GPU server: virtual mic clock, real decodes."""
    from intelliai_stt_runtime.pipeline.audio import DecodedAudio
    from intelliai_stt_runtime.pipeline.vad import EnergyVad

    source = Path(wav_path)
    with wave.open(str(source), "rb") as handle:
        rate = handle.getframerate()
        pcm = handle.readframes(handle.getnframes())
    total_s = len(pcm) / 2 / rate
    vad = EnergyVad()
    analysis = vad.analyze(
        DecodedAudio(
            pcm=pcm, sample_rate_hz=rate, duration_seconds=total_s, channels=1, sample_width_bytes=2
        )
    )
    speech_start = analysis.regions[0].start_seconds if analysis.regions else 0.0

    def window_wav(start_s: float, end_s: float) -> bytes:
        import io

        chunk = pcm[int(start_s * rate) * 2 : int(end_s * rate) * 2]
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(rate)
            out.writeframes(chunk)
        return buffer.getvalue()

    gpu_decode(window_wav(0, min(1.0, total_s)))  # warm
    chunk_s = chunk_ms / 1000.0
    import os

    max_window = float(os.environ.get("M52H_MAX_WINDOW_S", "25"))
    commit_margin = 5.0
    committed = ""
    window_start = 0.0
    clock = chunk_s
    events: list[dict] = []
    partials: list[str] = []
    while True:
        available = min(total_s, int(max(clock, chunk_s) / chunk_s) * chunk_s)
        if total_s - available < chunk_s:
            available = total_s
        if available - window_start < 0.25 and available < total_s:
            clock = max(clock, available) + chunk_s  # window too fresh — wait a chunk
            continue
        text, elapsed_ms = gpu_decode(window_wav(window_start, available))
        clock = max(clock, available) + elapsed_ms / 1000.0
        partial = (committed + " " + text).strip()
        events.append(
            {
                "audio_s": round(available, 2),
                "done_at_s": round(clock, 2),
                "latency_ms": round((clock - available) * 1000.0, 1),
                "decode_ms": round(elapsed_ms, 1),
            }
        )
        partials.append(partial)
        if mode == "rolling" and (available - window_start) > max_window:
            # This endpoint returns no per-segment timestamps, so the text
            # cannot be split by time. Policy: snap a cut to the latest
            # VAD-quiet boundary (M19's quietest-moment idea), decode the
            # committed span ONCE more as its final text, and advance the
            # window past it — no overlap, no duplication by construction.
            span_pcm = pcm[int(window_start * rate) * 2 : int(available * rate) * 2]
            span = vad.analyze(
                DecodedAudio(
                    pcm=span_pcm,
                    sample_rate_hz=rate,
                    duration_seconds=available - window_start,
                    channels=1,
                    sample_width_bytes=2,
                )
            )
            cut_local = next(
                (
                    region.end_seconds
                    for region in reversed(span.regions)
                    if region.end_seconds <= (available - window_start) - commit_margin
                ),
                (available - window_start) - commit_margin,
            )
            cut = min(window_start + cut_local, available - 1.0)  # never empty the live window
            span_text, span_ms = gpu_decode(window_wav(window_start, cut))
            clock += span_ms / 1000.0  # the commit decode also costs time
            committed = (committed + " " + span_text).strip()
            window_start = cut
        if available >= total_s:
            break
    final_text = partials[-1]
    # Single-pass offline is only a valid ruler inside E3's proven direct
    # envelope (<=120 s, M19 law); beyond that it truncates (measured,
    # long-2min-quality.json) and >~5 min exceeds the 4096 context outright
    # (HTTP 400). Long sessions are scored against GROUND TRUTH instead.
    if total_s <= 120.0:
        offline_text, offline_ms = gpu_decode(window_wav(0, total_s), timeout=600)
    else:
        offline_text, offline_ms = None, None
    fpt = next((e["done_at_s"] for e, p in zip(events, partials, strict=True) if p), None)
    latencies = [e["latency_ms"] for e in events[:-1]] or [0.0]
    import itertools

    gaps = [b["done_at_s"] - a["done_at_s"] for a, b in itertools.pairwise(events)]
    ratios = []
    rewrites = 0
    for prev, cur in itertools.pairwise(partials):
        p, c = prev.split(), cur.split()
        if not p:
            continue
        lcp = 0
        for x, y in zip(p, c, strict=False):
            if x != y:
                break
            lcp += 1
        ratios.append(lcp / len(p))
        if lcp < len(p):
            rewrites += 1
    # LocalAgreement-2 display metrics
    displayed: list[int] = []
    lags = []
    shrink = 0
    last_shown = 0
    for prev, cur in itertools.pairwise(partials):
        p, c = prev.split(), cur.split()
        lcp = 0
        for x, y in zip(p, c, strict=False):
            if x != y:
                break
            lcp += 1
        shown = max(lcp, last_shown)
        if shown < last_shown:
            shrink += 1
        last_shown = shown
        displayed.append(shown)
        lags.append(len(c) - shown)
    payload = {
        "wav": source.name,
        "mode": mode,
        "chunk_ms": chunk_ms,
        "audio_seconds": round(total_s, 2),
        "speech_start_s": round(speech_start, 2),
        "updates": len(events),
        "fpt_ms_from_session_start": round(fpt * 1000.0, 1) if fpt else None,
        "fpt_ms_from_speech_start": round((fpt - speech_start) * 1000.0, 1) if fpt else None,
        "update_latency_ms": {
            "p50": round(statistics.median(latencies), 1),
            "p95": round(
                sorted(latencies)[min(len(latencies) - 1, round(0.95 * (len(latencies) - 1)))], 1
            ),
        },
        "cadence_s_p50": round(statistics.median(gaps), 2) if gaps else None,
        "finalization_ms": events[-1]["latency_ms"],
        "stability": {
            "stable_token_ratio_mean": round(statistics.mean(ratios), 3) if ratios else 1.0,
            "rewrite_events": rewrites,
            "partials": len(partials),
        },
        "la2": {
            "monotonic": shrink == 0,
            "lag_words_mean": round(statistics.mean(lags), 1) if lags else 0,
            "live_coverage_of_final": round(
                (displayed[-1] if displayed else 0) / max(len(final_text.split()), 1), 3
            ),
        },
        "final_vs_offline": hindi_score(offline_text, final_text) if offline_text else None,
        "offline_decode_ms": round(offline_ms, 1) if offline_ms else None,
        "final_text": final_text,
        "offline_text": offline_text,
        "events": events,
    }
    write(out_name, payload)
    print(
        out_name,
        "fpt",
        payload["fpt_ms_from_speech_start"],
        "lat_p50",
        payload["update_latency_ms"]["p50"],
        "final",
        payload["finalization_ms"],
        "wer_vs_offline",
        payload["final_vs_offline"]["wer"] if payload["final_vs_offline"] else "n/a-long",
    )


def mode_memory() -> None:
    baseline = vram()
    wav = wav_bytes_of(CLIPS / "hindi_pre_5s.wav")
    peak = baseline["vram_used_mib"]
    for index in range(50):
        gpu_decode(wav)
        if index % 5 == 0:
            peak = max(peak, vram()["vram_used_mib"])
    after = vram()
    write(
        "gpu-memory.json",
        {
            "requests": 50,
            "baseline": baseline,
            "peak_vram_mib_sampled": peak,
            "after": after,
            "vram_growth_mib": after["vram_used_mib"] - baseline["vram_used_mib"],
        },
    )
    print("memory:", baseline, "->", after, "peak", peak)


def mode_concurrency() -> None:
    wav = wav_bytes_of(CLIPS / "hindi_pre_2s.wav")
    gpu_decode(wav)
    results = {}

    def one() -> float | None:
        try:
            _, ms = gpu_decode(wav)
        except Exception:
            return None
        return ms

    for c in (1, 2, 4, 8):
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=c) as pool:
            outcomes = [future.result() for future in [pool.submit(one) for _ in range(16)]]
        wall = time.perf_counter() - started
        failures = sum(1 for outcome in outcomes if outcome is None)
        ordered = sorted(outcome for outcome in outcomes if outcome is not None)
        results[f"c{c}"] = {
            "requests": 16,
            "p50_ms": round(statistics.median(ordered), 1) if ordered else None,
            "p95_ms": round(ordered[min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))], 1)
            if ordered
            else None,
            "wall_s": round(wall, 2),
            "throughput_rps": round(len(ordered) / wall, 2),
            "failures": failures,
            **vram(),
        }
        print(f"c{c}", results[f"c{c}"])
    write("concurrency.json", {"clip": "2s hindi", "results": results})


def mode_quality(n: int = 30) -> None:
    manifest = json.loads(
        (ROOT / "ml/datasets/manifests/candidates-indicvoices-hindi-valid.json").read_text(
            encoding="utf-8"
        )
    )
    rows = [row for row in manifest["candidates"] if 3.0 <= row["duration_seconds"] <= 15.0][:n]
    gpu_scores = []
    cpu_scores = []
    agree = 0
    H.mkdir(exist_ok=True)
    per_clip = []
    for row in rows:
        flac = ROOT / "ml/datasets/data" / row["path"]
        wav = slice_wav(flac, row["duration_seconds"] + 1, H / "q.wav")
        gpu_text, _ = gpu_decode(wav_bytes_of(wav))
        cpu_text = cpu_decode(wav)["text"]
        g = hindi_score(row["text"], gpu_text)
        c = hindi_score(row["text"], cpu_text)
        gpu_scores.append(g)
        cpu_scores.append(c)
        if gpu_text.strip() == cpu_text.strip():
            agree += 1
        per_clip.append(
            {
                "id": row["id"],
                "gpu": g,
                "cpu": c,
                "identical_text": gpu_text.strip() == cpu_text.strip(),
            }
        )

    def mean(key: str, scores: list[dict]) -> float:
        return round(statistics.mean(s[key] for s in scores), 4)

    write(
        "quality.json",
        {
            "ruler": "unicode_generic@v2 (frozen)",
            "dataset": "IndicVoices hindi valid (real speech, pinned manifest), first "
            f"{len(rows)} clips of 3-15 s",
            "gpu_mean": {"wer": mean("wer", gpu_scores), "cer": mean("cer", gpu_scores)},
            "cpu_mean": {"wer": mean("wer", cpu_scores), "cer": mean("cer", cpu_scores)},
            "identical_text_clips": f"{agree}/{len(rows)}",
            "per_clip": per_clip,
        },
    )
    print(
        "quality: gpu",
        mean("wer", gpu_scores),
        mean("cer", gpu_scores),
        "| cpu",
        mean("wer", cpu_scores),
        mean("cer", cpu_scores),
        "| identical",
        agree,
        "/",
        len(rows),
    )


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "cpu-baseline":
        mode_cpu_baseline()
    elif mode == "gpu-ladder":
        mode_gpu_ladder()
    elif mode == "windows":
        mode_windows(sys.argv[2])
    elif mode == "sim":
        mode_sim(
            sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]) if len(sys.argv) > 5 else 500
        )
    elif mode == "memory":
        mode_memory()
    elif mode == "concurrency":
        mode_concurrency()
    elif mode == "quality":
        mode_quality()
    else:
        raise SystemExit(f"unknown mode {mode}")
