"""M19 Phase 13: the chunked long-audio path proven THROUGH the engine.

NOT ledger evidence. The research probe (longaudio_probe.py) measured
the chunking STRATEGY with hand-rolled windowing; this proof runs the
IMPLEMENTATION — ``load_qwen3_asr`` with the pinned binary and verified
GGUF bytes, then ``Qwen3AsrEngine.transcribe()`` — the exact code path
a runtime request takes below the slot layer. The only divergence from
the committed defaults is the sanctioned proof override: the request
ceiling is raised to 600 s FOR THIS PROCESS while the committed default
stays 120 until the whole battery passes.

Per duration {120, 180, 300, 600} x repeats it records:
  - completeness (ruler characters, hypothesis/reference) and CER/WER
    with the evaluation plane's own ruler — read beside the research
    probe's concatenated-clip rows, never entered in the ledger
  - determinism: greedy decode must yield IDENTICAL text across repeats
  - the segment contract: ' '.join(segment texts) == text, offsets are
    real window starts, monotonic, first at 0.0
  - dispatch: 120 s must produce ONE segment (direct path); longer must
    produce the windowed shape
  - peak llama-server RSS (the ctx-4096 class, no context growth)
"""

from __future__ import annotations

import argparse
import datetime
import itertools
import json
import sys
import time
import wave
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from longaudio_probe import RssSampler, build_concat

from intelliai_evaluation.accuracy import score
from intelliai_evaluation.normalization import profile_for
from intelliai_runtime_contract import TranscriptionRequest
from intelliai_stt_runtime.engines.qwen3_asr import load_qwen3_asr
from intelliai_stt_runtime.pipeline import DecodedAudio

#: Repeats per duration: enough to prove greedy determinism without
#: doubling the battery's wall clock (600 s decodes cost ~3 min each).
REPEATS = {120: 2, 180: 2, 300: 3, 600: 3}


def decoded_audio(wav_path: Path) -> DecodedAudio:
    """The probe wavs are already canonical 16 kHz mono s16le."""
    with wave.open(str(wav_path)) as reader:
        shape = (reader.getframerate(), reader.getnchannels(), reader.getsampwidth())
        if shape != (16000, 1, 2):
            msg = f"probe wav must be canonical 16 kHz mono s16le, got {shape}"
            raise ValueError(msg)
        frames = reader.getnframes()
        pcm = reader.readframes(frames)
    return DecodedAudio(
        pcm=pcm,
        sample_rate_hz=16000,
        channels=1,
        sample_width_bytes=2,
        duration_seconds=frames / 16000,
    )


def run_once(engine: Any, audio: DecodedAudio, reference: str, profile: Any) -> dict[str, Any]:
    sampler = RssSampler()
    started = time.perf_counter()
    failure = None
    result = None
    try:
        result = engine.transcribe(audio, TranscriptionRequest(language="hi"))
    except Exception as exc:
        failure = f"{type(exc).__name__}: {exc}"[:200]
    wall = round(time.perf_counter() - started, 1)
    peak_rss = sampler.stop()
    row: dict[str, Any] = {"failure": failure, "wall_seconds": wall, "peak_rss_mib": peak_rss}
    if result is None:
        return row

    scored = score(reference, result.text, profile)
    ref_chars = len(profile.characters(reference))
    hyp_chars = len(profile.characters(result.text))
    segments = list(result.segments)
    joined = " ".join(s.text for s in segments)
    row.update(
        {
            "text": result.text,
            "language": result.language,
            "cer_unicode": round(scored.cer, 4),
            "wer_unicode": round(scored.wer, 4),
            "completeness_chars": round(hyp_chars / ref_chars, 3) if ref_chars else None,
            "segments": len(segments),
            "segment_spans": [
                [round(s.start_seconds, 2), round(s.end_seconds, 2)] for s in segments
            ],
            "segment_join_equals_text": joined == result.text,
            "segment_offsets_monotonic": all(
                a.start_seconds < b.start_seconds for a, b in itertools.pairwise(segments)
            ),
            "seams": [f"…{a.text[-45:]} ⇢ {b.text[:45]}…" for a, b in itertools.pairwise(segments)],
        }
    )
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest", type=Path, default=Path("ml/evaluation/manifests/research.json")
    )
    parser.add_argument("--data-root", type=Path, default=Path("ml/datasets/data"))
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument(
        "--weights",
        type=Path,
        default=Path("weights/qwen3-asr-spike"),
        help="directory holding the two verified GGUFs",
    )
    parser.add_argument(
        "--server-binary",
        type=Path,
        default=Path("weights/qwen3-asr-spike/llama-cpp/llama-server.exe"),
    )
    parser.add_argument("--durations", default="120,180,300,600")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    args.work.mkdir(parents=True, exist_ok=True)
    profile = profile_for("hi")

    print("loading engine (pinned binary verified at load) …", flush=True)
    engine = load_qwen3_asr(
        args.weights,
        server_binary=args.server_binary,
        context_tokens=4096,
        max_audio_seconds=600.0,  # the sanctioned proof override; committed default stays 120
    )
    rows: dict[str, Any] = {}
    try:
        for seconds in (int(s) for s in args.durations.split(",")):
            wav_path, reference = build_concat(args.manifest, args.data_root, seconds, args.work)
            audio = decoded_audio(wav_path)
            runs = [
                run_once(engine, audio, reference, profile) for _ in range(REPEATS.get(seconds, 2))
            ]
            texts = {r.get("text") for r in runs if r.get("failure") is None}
            rows[f"{seconds}s"] = {
                "audio_seconds": round(audio.duration_seconds, 2),
                "deterministic_across_repeats": len(texts) == 1,
                "runs": runs,
            }
            summary = {
                k: rows[f"{seconds}s"]["runs"][0].get(k)
                for k in (
                    "failure",
                    "wall_seconds",
                    "cer_unicode",
                    "completeness_chars",
                    "segments",
                )
            }
            summary["deterministic"] = rows[f"{seconds}s"]["deterministic_across_repeats"]
            print(
                f"[engine-proof] {seconds}s -> {json.dumps(summary, ensure_ascii=False)}",
                flush=True,
            )
    finally:
        engine.close()

    payload = {
        "probe": "19-long-audio-engine-proof",
        "NOT_LEDGER_EVIDENCE": (
            "concatenated-clip sandbox proof THROUGH Qwen3AsrEngine.transcribe(); "
            "read beside the frozen benchmark, never entered in it"
        ),
        "ceiling_override": "max_audio_seconds=600.0 in-process; committed default remains 120.0",
        "engine_decode_params": dict(engine.describe().decode_params),
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
