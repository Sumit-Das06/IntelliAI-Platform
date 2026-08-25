# M45 Phase 2-6 — latency profile of Qwen3-TTS 0.6B Base (clone mode).
# READ-ONLY instrumentation: timing wrappers around existing methods;
# model weights and behavior untouched. Frozen identity = M44 pins.
import argparse
import json
import time
from pathlib import Path

import torch

MODEL_DIR = str(Path.home() / "m44/models/qwen3-tts-0.6b-base")
REVISION = "5d83992436eae1d760afd27aff78a71d676296fc"
REF_AUDIO = str(Path.home() / "m44/data/LJSpeech-1.1/wavs/LJ001-0004.wav")
REF_TEXT = (
    "produced the block books, which were the immediate predecessors of the true printed book,"
)


class Acc:
    """Accumulating timing wrapper for a bound method (GPU-synced)."""

    def __init__(self, obj, name):
        self.obj, self.name = obj, name
        self.orig = getattr(obj, name)
        self.total = 0.0
        self.calls = 0

    def install(self):
        def wrapped(*a, **k):
            torch.cuda.synchronize()
            t0 = time.perf_counter()
            out = self.orig(*a, **k)
            torch.cuda.synchronize()
            self.total += time.perf_counter() - t0
            self.calls += 1
            return out

        setattr(self.obj, self.name, wrapped)
        return self

    def reset(self):
        self.total, self.calls = 0.0, 0

    def snap(self):
        return {"seconds": round(self.total, 4), "calls": self.calls}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dtype", default="bf16", choices=["bf16", "fp16", "fp32"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--texts", required=True, help="json file: [{id,text},...]")
    ap.add_argument("--warm-reps", type=int, default=3)
    ap.add_argument("--max-new-tokens", type=int, default=2048)
    args = ap.parse_args()

    dtype = {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}[args.dtype]
    texts = json.loads(Path(args.texts).read_text(encoding="utf-8"))

    from qwen_tts import Qwen3TTSModel

    torch.manual_seed(0)
    t0 = time.perf_counter()
    tts = Qwen3TTSModel.from_pretrained(
        MODEL_DIR, device_map="cuda:0", dtype=dtype, attn_implementation="sdpa"
    )
    torch.cuda.synchronize()
    load_s = time.perf_counter() - t0

    core = tts.model  # Qwen3TTSForConditionalGeneration
    talker = core.talker

    # timing wrappers (behavior-neutral)
    acc_sub = Acc(talker.code_predictor, "generate").install()
    acc_trunk = Acc(talker.model, "forward").install()
    acc_dec = Acc(core.speech_tokenizer, "decode").install()
    acc_enc = Acc(core.speech_tokenizer, "encode").install()
    acc_spk = Acc(core, "extract_speaker_embedding").install()
    accs = [acc_sub, acc_trunk, acc_dec, acc_enc, acc_spk]

    # ---- prompt build: uncached vs cached (Phase 6) ----
    torch.cuda.reset_peak_memory_stats()
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    prompt = tts.create_voice_clone_prompt(ref_audio=REF_AUDIO, ref_text=REF_TEXT)
    torch.cuda.synchronize()
    prompt_build_s = time.perf_counter() - t0
    prompt_detail = {
        "prompt_build_s": round(prompt_build_s, 4),
        "ref_codec_encode": acc_enc.snap(),
        "ref_spk_embedding": acc_spk.snap(),
        "ref_code_frames": int(prompt[0].ref_code.shape[0]),
    }

    results = []
    for i, case in enumerate(texts):
        for mode in (
            (["cold"] if i == 0 else [])
            + ["warm"] * (args.warm_reps if i == 0 else 1)
            + (["warm-cachedprompt"] if True else [])
        ):
            for a in accs:
                a.reset()
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()
            t0 = time.perf_counter()
            if mode == "warm-cachedprompt":
                wavs, sr = tts.generate_voice_clone(
                    text=case["text"],
                    language="English",
                    voice_clone_prompt=prompt,
                    max_new_tokens=args.max_new_tokens,
                )
            else:
                wavs, sr = tts.generate_voice_clone(
                    text=case["text"],
                    language="English",
                    ref_audio=REF_AUDIO,
                    ref_text=REF_TEXT,
                    max_new_tokens=args.max_new_tokens,
                )
            torch.cuda.synchronize()
            total_s = time.perf_counter() - t0
            audio_s = len(wavs[0]) / sr
            trunk = acc_trunk.snap()
            sub = acc_sub.snap()
            dec = acc_dec.snap()
            frames = max(sub["calls"], 1)  # one code_predictor.generate per AR frame
            row = {
                "id": case["id"],
                "chars": len(case["text"]),
                "mode": mode,
                "total_s": round(total_s, 3),
                "audio_s": round(audio_s, 3),
                "rtf": round(total_s / max(audio_s, 1e-6), 4),
                "frames": frames,
                "talker_trunk": trunk,
                "code_predictor": sub,
                "codec_decode": dec,
                "prompt_rebuild": {
                    "encode": acc_enc.snap(),
                    "spk": acc_spk.snap(),
                },
                "per_frame_ms": round(1000.0 * (trunk["seconds"] + sub["seconds"]) / frames, 2),
                "unaccounted_s": round(
                    total_s
                    - trunk["seconds"]
                    - sub["seconds"]
                    - dec["seconds"]
                    - acc_enc.total
                    - acc_spk.total,
                    3,
                ),
                "vram_peak_alloc_mib": round(torch.cuda.max_memory_allocated() / 1024**2, 1),
            }
            results.append(row)
            print(json.dumps(row), flush=True)

    out = {
        "experiment": "45-qwen3-tts-low-latency",
        "instrument": "m45_profile.py (timing wrappers only; weights untouched)",
        "identity": {
            "model_dir": MODEL_DIR,
            "revision": REVISION,
            "dtype": args.dtype,
            "attn": "sdpa",
            "device": "cuda:0",
            "ref_audio": "LJ001-0004.wav",
            "mode": "clone/icl",
            "seeded": "torch.manual_seed(0); AR sampling stochastic",
        },
        "load_seconds": round(load_s, 2),
        "prompt": prompt_detail,
        "rows": results,
    }
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("PROFILE-DONE", args.out)


if __name__ == "__main__":
    main()
