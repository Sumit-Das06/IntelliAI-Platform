# M45 Phase 12 — sentence-chunked progressive playback (fallback).
# NOT model-native streaming: each sentence is a separate generate
# call; playback of sentence 1 overlaps generation of sentence 2.
# TTFA = wall of sentence 1. Seam risk: prosody reset + join clicks.
import argparse
import json
import re
import time
from pathlib import Path

import numpy as np
import torch

MODEL_DIR = str(Path.home() / "m44/models/qwen3-tts-0.6b-base")
REF_AUDIO = str(Path.home() / "m44/data/LJSpeech-1.1/wavs/LJ001-0004.wav")
REF_TEXT = (
    "produced the block books, which were the immediate predecessors of the true printed book,"
)
SPLIT = re.compile(r"(?<=[.!?])\s+")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--texts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fastsub", action="store_true")
    ap.add_argument("--audio-dir", default=None)
    args = ap.parse_args()

    texts = json.loads(Path(args.texts).read_text(encoding="utf-8"))
    from qwen_tts import Qwen3TTSModel

    torch.manual_seed(0)
    tts = Qwen3TTSModel.from_pretrained(
        MODEL_DIR, device_map="cuda:0", dtype=torch.bfloat16, attn_implementation="sdpa"
    )
    if args.fastsub:
        import fastsub as fs

        gd = tts.generate_defaults
        fs.install_fast_subtalker(
            tts.model.talker,
            top_k=gd.get("subtalker_top_k", 50),
            top_p=gd.get("subtalker_top_p", 1.0),
            temperature=gd.get("subtalker_temperature", 0.9),
        )
    prompt = tts.create_voice_clone_prompt(ref_audio=REF_AUDIO, ref_text=REF_TEXT)
    if args.audio_dir:
        Path(args.audio_dir).mkdir(parents=True, exist_ok=True)

    rows = []
    for case in texts:
        sentences = [s for s in SPLIT.split(case["text"]) if s.strip()]
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        parts, marks = [], []
        sr = 24000
        for si, sent in enumerate(sentences):
            wavs, sr = tts.generate_voice_clone(
                text=sent, language="English", voice_clone_prompt=prompt
            )
            torch.cuda.synchronize()
            t_done = time.perf_counter() - t0
            parts.append(np.asarray(wavs[0], dtype=np.float32))
            marks.append(
                {
                    "sentence": si,
                    "chars": len(sent),
                    "t_done_s": round(t_done, 3),
                    "audio_s": round(len(wavs[0]) / sr, 3),
                }
            )
        total = time.perf_counter() - t0
        joined = np.concatenate(parts)
        row = {
            "id": case["id"],
            "chars": len(case["text"]),
            "mode": "sentence-chunked",
            "fastsub": bool(args.fastsub),
            "n_sentences": len(sentences),
            "ttfa_s": marks[0]["t_done_s"] if marks else None,
            "total_s": round(total, 3),
            "audio_s": round(len(joined) / sr, 3),
            "rtf": round(total / max(len(joined) / sr, 1e-6), 4),
            "sentences": marks,
        }
        rows.append(row)
        print(json.dumps(row), flush=True)
        if args.audio_dir:
            import soundfile as sf

            sf.write(f"{args.audio_dir}/{case['id']}-sentchunk.wav", joined, sr)

    Path(args.out).write_text(
        json.dumps(
            {
                "experiment": "45-qwen3-tts-low-latency",
                "instrument": "m45_sentchunk.py (sentence-chunked progressive playback)",
                "note": "NOT model-native streaming; prosody resets at seams",
                "rows": rows,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print("SENTCHUNK-DONE", args.out)


if __name__ == "__main__":
    main()
