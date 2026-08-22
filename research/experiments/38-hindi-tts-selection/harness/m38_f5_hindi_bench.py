"""M38 — SPRINGLab F5-Hindi-24KHz CPU/GPU spike (research instrument only).

The only permissive (CC-BY-4.0, trained-from-scratch per card) dedicated
Hindi TTS found in the 2026-08-22 sweep. F5 is a flow-matching model with
a CLONING-STYLE interface: every generation needs a reference audio +
reference text. For this research run the reference is one of OUR OWN
Kokoro-hi synthesized WAVs (a synthetic voice — no human speaker, no
consent surface). HONESTY NOTE recorded in the output: a robotic
synthetic reference biases naturalness DOWNWARD; intelligibility (round
trip) and RTF remain fair measurements.

Run inside the f5 venv (WSL):
    python m38_f5_hindi_bench.py --probes probe-texts-hi-v1.json \
        --model-dir ~/m38/f5-hindi --ref-audio <wav> --ref-text "<text>" \
        --audio-dir ~/m38/audio/f5-hindi --out f5-hindi-m38-bench.json
"""

from __future__ import annotations

import argparse
import json
import time
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probes", required=True)
    parser.add_argument("--model-dir", required=True, help="dir with model safetensors + vocab.txt")
    parser.add_argument("--ref-audio", required=True)
    parser.add_argument("--ref-text", required=True)
    parser.add_argument("--audio-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--languages", default="hi,mixed,mixed-roman,en")
    parser.add_argument("--device", default=None, help="None=auto, or cpu / cuda")
    parser.add_argument("--nfe-step", type=int, default=32)
    parser.add_argument("--limit", type=int, default=0, help="probe cap for smoke runs")
    args = parser.parse_args()

    probes = json.loads(Path(args.probes).read_text(encoding="utf-8"))["cases"]
    wanted = {piece.strip() for piece in args.languages.split(",") if piece.strip()}
    probes = [case for case in probes if case["language"] in wanted]
    if args.limit:
        probes = probes[: args.limit]

    model_dir = Path(args.model_dir).expanduser()
    ckpt = model_dir / "model_2500000.safetensors"
    vocab = model_dir / "vocab.txt"

    # The research venv's torchaudio delegates load/save to torchcodec,
    # which needs ffmpeg shared libraries this WSL lacks (no sudo). Patch
    # the two entry points to soundfile — bit-exact for WAV, which is the
    # only format this instrument touches.
    import soundfile as sf
    import torch
    import torchaudio

    def _sf_load(path, *args, **kwargs):
        data, rate = sf.read(str(path), dtype="float32", always_2d=True)
        return torch.from_numpy(data.T), rate

    def _sf_save(path, tensor, sample_rate, *args, **kwargs):
        sf.write(str(path), tensor.detach().cpu().numpy().T, sample_rate)

    torchaudio.load = _sf_load
    torchaudio.save = _sf_save

    rss_before = _rss_mib()
    load_started = time.perf_counter()
    from f5_tts.api import F5TTS

    tts = F5TTS(
        model="F5TTS_Small",
        ckpt_file=str(ckpt),
        vocab_file=str(vocab),
        device=args.device,
    )
    load_seconds = time.perf_counter() - load_started
    rss_after = _rss_mib()

    audio_dir = Path(args.audio_dir).expanduser()
    audio_dir.mkdir(parents=True, exist_ok=True)

    # warm-up, excluded
    tts.infer(
        ref_file=args.ref_audio,
        ref_text=args.ref_text,
        gen_text="नमस्ते।",
        nfe_step=args.nfe_step,
        remove_silence=False,
    )

    rows: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    for case in probes:
        started = time.perf_counter()
        try:
            wav, sr, _ = tts.infer(
                ref_file=args.ref_audio,
                ref_text=args.ref_text,
                gen_text=case["text"],
                nfe_step=args.nfe_step,
                remove_silence=False,
                file_wave=str(audio_dir / f"{case['id']}.wav"),
            )
        except Exception as exc:
            failures.append({"id": case["id"], "error": f"{exc.__class__.__name__}: {exc}"[:300]})
            continue
        wall = time.perf_counter() - started
        seconds = len(wav) / float(sr) if wav is not None else 0.0
        rows.append(
            {
                "id": case["id"],
                "language": case["language"],
                "category": case.get("category"),
                "chars": len(case["text"]),
                "wall_ms": round(wall * 1000.0, 1),
                "ttfa_ms": None,
                "audio_seconds": round(seconds, 3),
                "rtf": round(wall / seconds, 4) if seconds > 0 else None,
                "sample_rate_hz": sr,
            }
        )
        print(rows[-1])

    ok = [row for row in rows if row["rtf"] is not None]
    rtfs = sorted(float(row["rtf"]) for row in ok)
    report = {
        "experiment": "38-hindi-tts-selection",
        "instrument": "m38_f5_hindi_bench.py",
        "engine": "f5-hindi-24khz (SPRINGLab, F5TTS_Small 151M, flow matching)",
        "identity": {
            "hub_repo": "SPRINGLab/F5-Hindi-24KHz",
            "checkpoint": ckpt.name,
            "license": "CC-BY-4.0 (card, verified 2026-08-22); card: trained from scratch",
            "device": args.device or "auto",
            "nfe_step": args.nfe_step,
            "reference_interface": (
                "cloning-style: ref audio+text required per generation; reference here is an "
                "IntelliAI-synthesized Kokoro-hi WAV (synthetic voice, no human speaker) - "
                "naturalness is biased DOWN by the robotic reference; RTF and round-trip "
                "intelligibility remain fair"
            ),
            "ref_audio": Path(args.ref_audio).name,
        },
        "load_seconds": round(load_seconds, 2),
        "rss_before_load_mib": round(rss_before, 1),
        "rss_after_load_mib": round(rss_after, 1),
        "rss_peak_mib": round(_peak_rss_mib(), 1),
        "probe_count": len(rows),
        "failure_count": len(failures),
        "failures": failures,
        "rtf_median": rtfs[len(rtfs) // 2] if rtfs else None,
        "rtf_p95": rtfs[min(len(rtfs) - 1, int(0.95 * len(rtfs)))] if rtfs else None,
        "rows": rows,
    }
    Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"f5-hindi: {len(rows)} probes, {len(failures)} failures, "
        f"median RTF {report['rtf_median']}, peak RSS {report['rss_peak_mib']} MiB"
    )


if __name__ == "__main__":
    main()
