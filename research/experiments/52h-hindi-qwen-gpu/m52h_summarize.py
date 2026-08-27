"""M52H post-processing.

1. Per-clip offline GPU baseline for each long-session's material: the
   constituent IndicVoices clips decoded INDIVIDUALLY (E3's ideal
   serving shape), concatenated, scored against ground truth — this
   separates "streaming penalty" from "material difficulty".
2. The spec-named summary evidence files (fpt / partial-cadence /
   finalization / stability / vad / long-speech / cpu-vs-gpu),
   synthesized from the sim evidence already on disk.

    python m52h_summarize.py baseline   # needs the GPU server up
    python m52h_summarize.py summarize  # pure post-processing
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "ml/evaluation/src"))

from m52h_bench import H, gpu_decode, hindi_score, wav_bytes_of  # noqa: E402


def load(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def mode_baseline() -> None:
    """Decode each constituent clip of the long sessions individually."""
    manifest = json.loads(
        (ROOT / "ml/datasets/manifests/candidates-indicvoices-hindi-valid.json").read_text(
            encoding="utf-8"
        )
    )
    by_path = {row["path"]: row for row in manifest["candidates"]}
    out = {}
    for session in ("real2min", "real5min", "real10min"):
        listing = (H / f"{session}.txt").read_text(encoding="utf-8")
        texts = []
        times = []
        for line in listing.splitlines():
            flac = Path(line.split("'", 2)[1])
            rel = flac.as_posix().split("ml/datasets/data/")[-1]
            by_path[rel]  # asserts the clip is manifest-known
            import subprocess

            wav = H / "b.wav"
            subprocess.run(  # noqa: S603
                [  # noqa: S607 — PATH ffmpeg (repo law)
                    "ffmpeg",
                    "-y",
                    "-loglevel",
                    "error",
                    "-i",
                    str(flac),
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    str(wav),
                ],
                check=True,
            )
            text, ms = gpu_decode(wav_bytes_of(wav))
            texts.append(text)
            times.append(ms)
        reference = (H / f"{session}.ref.txt").read_text(encoding="utf-8")
        joined = " ".join(texts)
        out[session] = {
            "clips": len(texts),
            "per_clip_offline_vs_truth": hindi_score(reference, joined),
            "decode_ms_total": round(sum(times), 1),
        }
        print(session, out[session]["per_clip_offline_vs_truth"])
    (EVIDENCE / "long-offline-per-clip-baseline.json").write_text(
        json.dumps(
            {
                "note": "each constituent real clip decoded INDIVIDUALLY on GPU "
                "(E3's ideal serving shape), texts joined, scored vs ground truth — "
                "the honest offline baseline for the same long-session material",
                **out,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print("wrote long-offline-per-clip-baseline.json")


def mode_summarize() -> None:
    sims = {
        "real30s_growing": load("sim-real30s-growing.json"),
        "real2min_rolling": load("sim-real2min-rolling.json"),
        "real5min_rolling": load("sim-real5min-rolling.json"),
        "real10min_rolling": load("sim-real10min-rolling.json"),
    }
    write = lambda name, payload: (  # noqa: E731
        (EVIDENCE / name).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        ),
        print("wrote", name),
    )
    write(
        "fpt.json",
        {
            "definition": "first non-empty partial, measured from VAD speech start",
            "sessions": {
                key: {
                    "fpt_ms_from_speech_start": sim["fpt_ms_from_speech_start"],
                    "fpt_ms_from_session_start": sim["fpt_ms_from_session_start"],
                }
                for key, sim in sims.items()
            },
            "proposed_gate": "<=1000 ms acceptable",
        },
    )
    write(
        "partial-cadence.json",
        {
            key: {
                "update_latency_ms": sim["update_latency_ms"],
                "cadence_s_p50": sim["cadence_s_p50"],
                "updates": sim["updates"],
            }
            for key, sim in sims.items()
        },
    )
    write(
        "finalization.json",
        {
            "definition": "latency of the last decode after all audio arrived "
            "(sim upper bound; an end-triggered final in a product session "
            "starts immediately)",
            "sessions": {key: sim["finalization_ms"] for key, sim in sims.items()},
            "proposed_gate": "<=1000 ms",
        },
    )
    write(
        "stability.json",
        {key: {**sim["stability"], "la2": sim["la2"]} for key, sim in sims.items()},
    )
    long_quality = load("long-quality-vs-truth.json")
    baseline = load("long-offline-per-clip-baseline.json")
    write(
        "long-speech.json",
        {
            "sessions": {
                key: {
                    "audio_seconds": sim["audio_seconds"],
                    "updates": sim["updates"],
                    "final_words": len(sim["final_text"].split()),
                    "cadence_s_p50": sim["cadence_s_p50"],
                    "finalization_ms": sim["finalization_ms"],
                }
                for key, sim in sims.items()
            },
            "streamed_vs_ground_truth": {
                k: v for k, v in long_quality.items() if k.startswith("real")
            },
            "offline_per_clip_baseline": {
                k: v["per_clip_offline_vs_truth"]
                for k, v in baseline.items()
                if k.startswith("real")
            },
        },
    )
    cpu = load("cpu-baseline.json")["rows"]
    gpu = load("gpu-baseline.json")["rows"]
    quality = load("quality.json")
    memory = load("gpu-memory.json")
    conc = load("concurrency.json")["results"]
    sim30 = sims["real30s_growing"]
    write(
        "cpu-vs-gpu.json",
        {
            "prefix_ladder_ms": {
                name: {"cpu": cpu[name]["inference_ms"], "gpu": gpu[name]["inference_ms_median"]}
                for name in cpu
            },
            "fpt_ms_from_speech_start_gpu": sim30["fpt_ms_from_speech_start"],
            "fpt_cpu": "not achievable (1 s audio costs ~874-1307 ms; cadence collapses)",
            "partial_p50_ms": {"gpu": sim30["update_latency_ms"]["p50"], "cpu": "n/a (blocked)"},
            "partial_p95_ms": {"gpu": sim30["update_latency_ms"]["p95"], "cpu": "n/a (blocked)"},
            "finalization_ms": {"gpu": sim30["finalization_ms"], "cpu": "n/a (blocked)"},
            "rtf_20s": {
                "cpu": round(cpu["full"]["inference_ms"] / 1000.0 / 19.93, 3),
                "gpu": round(gpu["full"]["inference_ms_median"] / 1000.0 / 19.93, 3),
            },
            "quality_30_real_clips": {
                "gpu": quality["gpu_mean"],
                "cpu": quality["cpu_mean"],
                "identical_texts": quality["identical_text_clips"],
            },
            "vram_mib": memory["after"]["vram_used_mib"],
            "ram": "server RSS ~1.1 GiB (model in VRAM; host copy + runtime)",
            "concurrency_gpu": {k: v["p50_ms"] for k, v in conc.items()},
            "stability_gpu": sims["real5min_rolling"]["stability"]["stable_token_ratio_mean"],
            "long_session_gpu": "10 min bounded, see long-speech.json",
        },
    )
    silence = load("silence.json")
    write(
        "vad.json",
        {
            "detector": "production EnergyVad (annotation-only, deterministic)",
            "verdicts": {
                name: {
                    "vad_has_speech": row["vad_has_speech"],
                    "bare_model_output": row.get("bare_model_output", ""),
                }
                for name, row in silence["results"].items()
            },
            "law": "every realtime window decode is VAD-gated; silence never reaches the model",
        },
    )


if __name__ == "__main__":
    {"baseline": mode_baseline, "summarize": mode_summarize}[sys.argv[1]]()
