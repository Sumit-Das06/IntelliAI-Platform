"""M44 — Qwen3-TTS research runner: Base (voice-clone) or fine-tuned
checkpoint (custom-voice). Research only; no production integration.

Two modes, one measurement core (the M32/M33/M34 schema — min-of-N
repetitions, WAVs outside git, GPU VRAM separated from CPU RSS):

- ``--mode clone``  : the 0.6B *Base* model. Every generation carries
  the SAME pinned reference audio+text (the fine-tuning target
  speaker), so Base vs Fine-Tuned is an apples-to-apples comparison on
  one voice.
- ``--mode custom`` : a fine-tuned checkpoint directory, spoken through
  ``generate_custom_voice`` with the speaker name the SFT registered.

Streaming honesty (Phase 14): the runner probes the installed API for
a streaming generate; if none exists, ttfa_ms stays null and the
report says whole-shot. `non_streaming_mode=False` in the released
0.1.1 signature does NOT return an incremental iterator — verified by
type: the call returns the complete waveform list either way.

Usage (inside venv-qwen, WSL):
  python m44_qwen_bench.py --mode clone \
    --model-path <base snapshot dir> --revision <sha> \
    --ref-audio ~/m44/data/ref.wav --ref-text "<its transcript>" \
    --probes probe file --audio-dir ~/m44/audio/base-gpu \
    --out evidence/qwen-base-gpu.json --device cuda
"""

from __future__ import annotations

import argparse
import json
import time
import wave
from pathlib import Path


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
    parser.add_argument("--mode", choices=("clone", "custom"), required=True)
    parser.add_argument("--model-path", required=True, help="local snapshot/checkpoint dir")
    parser.add_argument("--revision", default="local", help="identity string for the record")
    parser.add_argument("--ref-audio", default=None, help="clone mode: pinned reference wav")
    parser.add_argument("--ref-text", default=None, help="clone mode: reference transcript")
    parser.add_argument("--speaker", default=None, help="custom mode: SFT speaker name")
    parser.add_argument("--language", default="English")
    parser.add_argument("--probes", required=True)
    parser.add_argument("--audio-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--limit", type=int, default=0, help="probe cap (CPU feasibility runs)")
    args = parser.parse_args()
    if args.mode == "clone" and not (args.ref_audio and args.ref_text):
        parser.error("--mode clone requires --ref-audio and --ref-text")
    if args.mode == "custom" and not args.speaker:
        parser.error("--mode custom requires --speaker")

    import torch

    probes = json.loads(Path(args.probes).read_text(encoding="utf-8"))["cases"]
    probes = [case for case in probes if case.get("language", "en") == "en"]
    if args.limit:
        probes = probes[: args.limit]

    torch.manual_seed(0)
    rss_before = _rss_mib()
    load_started = time.perf_counter()
    from qwen_tts import Qwen3TTSModel

    kwargs: dict[str, object] = (
        {"device_map": "cuda:0", "dtype": torch.bfloat16}
        if args.device == "cuda"
        else {"device_map": "cpu", "dtype": torch.float32}
    )
    model = Qwen3TTSModel.from_pretrained(args.model_path, **kwargs)
    load_seconds = time.perf_counter() - load_started
    rss_after_load = _rss_mib()
    vram_after_load = (
        round(torch.cuda.memory_allocated() / 2**20, 1) if args.device == "cuda" else None
    )

    stream_method = next(
        (
            name
            for name in (
                "generate_voice_clone_stream",
                "generate_custom_voice_stream",
                "generate_stream",
                "stream_generate",
            )
            if hasattr(model, name)
        ),
        None,
    )

    def synthesize(text: str) -> tuple[bytes, int, float | None]:
        if args.mode == "clone":
            wavs, sample_rate = model.generate_voice_clone(
                text=text,
                language=args.language,
                ref_audio=args.ref_audio,
                ref_text=args.ref_text,
            )
        else:
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
        "experiment": "44-qwen3-tts-finetuning",
        "instrument": "m44_qwen_bench.py",
        "engine": f"qwen3-tts-12hz-0.6b ({args.mode})",
        "identity": {
            "model_path": args.model_path,
            "revision": args.revision,
            "mode": args.mode,
            "speaker": args.speaker,
            "ref_audio": Path(args.ref_audio).name if args.ref_audio else None,
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
            round(torch.cuda.max_memory_allocated() / 2**20, 1) if args.device == "cuda" else None
        ),
        "vram_peak_reserved_mib": (
            round(torch.cuda.max_memory_reserved() / 2**20, 1) if args.device == "cuda" else None
        ),
        "probe_count": len(rows),
        "failure_count": len(failures),
        "failures": failures,
        "rtf_median": rtfs[len(rtfs) // 2] if rtfs else None,
        "rtf_p95": rtfs[min(len(rtfs) - 1, int(0.95 * len(rtfs)))] if rtfs else None,
        "rows": rows,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"qwen-{args.mode}: {len(rows)} probes, {len(failures)} failures, "
        f"median RTF {report['rtf_median']}, VRAM peak {report['vram_peak_alloc_mib']} MiB"
    )


if __name__ == "__main__":
    main()
