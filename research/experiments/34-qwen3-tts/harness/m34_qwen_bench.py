"""M34 — Qwen3-TTS 0.6B (CustomVoice) research runner. Research only.

Identity discipline: the model revision is resolved ONCE (HF API), snapshot-
downloaded to a local pinned directory, and recorded in the output JSON; after
initialization no network is touched (HF_HUB_OFFLINE honored if set by the
caller for repeat runs). No production integration anywhere.

Measurement core mirrors M32/M33 (same row schema, min-of-N repetitions, WAVs
outside git). TTFA: the runner probes the installed `qwen-tts` API for a
streaming generate; if none exists, ttfa_ms stays null and the report says
whole-shot honestly. GPU runs record VRAM (torch peak allocated + reserved)
separately from CPU RSS — never mixed.

Usage (inside venv-qwen, WSL):
    python m34_qwen_bench.py --device cuda --speaker Ryan --language English \
        --probes .../probe-texts-en-v1.json --audio-dir ~/m34/audio/qwen-gpu \
        --out .../evidence/qwen-gpu-bench.json --repetitions 2
"""

from __future__ import annotations

import argparse
import json
import time
import wave
from pathlib import Path

REPO_ID = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"


def _rss_mib() -> float:
    with open("/proc/self/status", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024.0
    return 0.0


def _peak_rss_mib() -> float:
    with open("/proc/self/status", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) / 1024.0
    return 0.0


def _write_wav(path: Path, pcm: bytes, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(sample_rate)
        fh.writeframes(pcm)


def _to_pcm16(audio: object) -> bytes:
    import numpy as np

    arr = audio
    if hasattr(arr, "detach"):
        arr = arr.detach().cpu().numpy()
    arr = np.asarray(arr, dtype=np.float32).reshape(-1)
    arr = np.clip(arr, -1.0, 1.0)
    return (arr * 32767.0).astype("<i2").tobytes()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probes", required=True)
    parser.add_argument("--audio-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--speaker", default="Ryan")
    parser.add_argument("--language", default="English")
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--limit", type=int, default=0, help="probe cap (CPU feasibility runs)")
    args = parser.parse_args()

    import torch
    from huggingface_hub import model_info, snapshot_download

    revision = str(model_info(REPO_ID).sha)
    local_dir = snapshot_download(REPO_ID, revision=revision)

    probes = json.loads(Path(args.probes).read_text(encoding="utf-8"))["cases"]
    probes = [case for case in probes if case.get("language", "en") == "en"]
    if args.limit:
        probes = probes[: args.limit]

    torch.manual_seed(0)
    rss_before = _rss_mib()
    load_started = time.perf_counter()
    from qwen_tts import Qwen3TTSModel

    kwargs: dict[str, object] = {}
    if args.device == "cuda":
        kwargs = {"device_map": "cuda:0", "dtype": torch.bfloat16}
    else:
        kwargs = {"device_map": "cpu", "dtype": torch.float32}
    model = Qwen3TTSModel.from_pretrained(local_dir, **kwargs)
    load_seconds = time.perf_counter() - load_started
    rss_after_load = _rss_mib()
    vram_after_load = (
        round(torch.cuda.memory_allocated() / 2**20, 1) if args.device == "cuda" else None
    )

    stream_method = next(
        (
            name
            for name in ("generate_custom_voice_stream", "generate_stream", "stream_generate")
            if hasattr(model, name)
        ),
        None,
    )

    def synthesize(text: str) -> tuple[bytes, int, float | None]:
        started = time.perf_counter()
        ttfa: float | None = None
        if stream_method is not None:
            pieces: list[bytes] = []
            rate_holder = 24000
            for chunk in getattr(model, stream_method)(
                text=text, language=args.language, speaker=args.speaker
            ):
                audio, rate_holder = chunk if isinstance(chunk, tuple) else (chunk, rate_holder)
                if ttfa is None:
                    ttfa = time.perf_counter() - started
                pieces.append(_to_pcm16(audio))
            return b"".join(pieces), int(rate_holder), ttfa
        wavs, sample_rate = model.generate_custom_voice(
            text=text, language=args.language, speaker=args.speaker
        )
        audio = wavs[0] if isinstance(wavs, (list, tuple)) else wavs
        return _to_pcm16(audio), int(sample_rate), None

    if args.device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    synthesize("Warm up run.")

    audio_dir = Path(args.audio_dir).expanduser()
    rows: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    sample_rate_seen = 0
    for case in probes:
        text = case["text"]
        best: dict[str, object] | None = None
        pcm = b""
        for _ in range(max(1, args.repetitions)):
            started = time.perf_counter()
            try:
                pcm, sample_rate_seen, ttfa = synthesize(text)
            except Exception as exc:
                failures.append({"id": case["id"], "error": f"{exc.__class__.__name__}: {exc}"})
                break
            wall = time.perf_counter() - started
            seconds = (len(pcm) // 2) / sample_rate_seen if pcm else 0.0
            row = {
                "id": case["id"],
                "language": "en",
                "category": case.get("category"),
                "chars": len(text),
                "wall_ms": round(wall * 1000.0, 1),
                "ttfa_ms": round(ttfa * 1000.0, 1) if ttfa is not None else None,
                "audio_seconds": round(seconds, 3),
                "rtf": round(wall / seconds, 4) if seconds > 0 else None,
            }
            if best is None or row["wall_ms"] < best["wall_ms"]:  # type: ignore[operator]
                best = row
        if best is None:
            continue
        if pcm:
            _write_wav(audio_dir / f"{case['id']}.wav", pcm, sample_rate_seen)
        rows.append(best)

    ok = [row for row in rows if row["rtf"] is not None]
    rtfs = sorted(float(row["rtf"]) for row in ok)  # type: ignore[arg-type]
    report = {
        "experiment": "34-qwen3-tts",
        "instrument": "m34_qwen_bench.py",
        "engine": "Qwen3-TTS-12Hz-0.6B-CustomVoice",
        "identity": {
            "hub_repo": REPO_ID,
            "hub_revision": revision,
            "speaker": args.speaker,
            "language_param": args.language,
            "device": args.device,
            "dtype": "bfloat16" if args.device == "cuda" else "float32",
            "streaming_api_found": stream_method,
            "seeded": "torch.manual_seed(0) (AR sampling may remain stochastic)",
        },
        "sample_rate_hz": sample_rate_seen,
        "repetitions": args.repetitions,
        "load_seconds": round(load_seconds, 2),
        "rss_before_load_mib": round(rss_before, 1),
        "rss_after_load_mib": round(rss_after_load, 1),
        "rss_peak_mib": round(_peak_rss_mib(), 1),
        "vram_after_load_mib": vram_after_load,
        "vram_peak_alloc_mib": (
            round(__import__("torch").cuda.max_memory_allocated() / 2**20, 1)
            if args.device == "cuda"
            else None
        ),
        "vram_peak_reserved_mib": (
            round(__import__("torch").cuda.max_memory_reserved() / 2**20, 1)
            if args.device == "cuda"
            else None
        ),
        "probe_count": len(rows),
        "failure_count": len(failures),
        "failures": failures,
        "rtf_median": rtfs[len(rtfs) // 2] if rtfs else None,
        "rtf_p95": rtfs[min(len(rtfs) - 1, int(0.95 * len(rtfs)))] if rtfs else None,
        "rows": rows,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"qwen3-tts[{args.device}] {args.speaker}: {len(rows)} probes, {len(failures)} failures, "
        f"median RTF {report['rtf_median']}, ttfa_supported={stream_method is not None}, "
        f"peak RSS {report['rss_peak_mib']} MiB, vram_peak {report['vram_peak_alloc_mib']} MiB"
    )


if __name__ == "__main__":
    main()
