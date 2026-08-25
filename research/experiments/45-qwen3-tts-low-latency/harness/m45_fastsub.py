# M45 Phase 8 — EXPERIMENTAL runtime optimization: replace the per-frame
# HF generate() call into the sub-talker (code predictor) with a manual
# 15-step sampling loop. SAME weights, SAME forward math, SAME sampling
# law (temperature + top-k + top-p via HF warpers, multinomial).
# One variable at a time: --opt none|fastsub|fastsub+compile
import argparse
import json
import time
import types
from pathlib import Path

import numpy as np
import torch
from transformers.cache_utils import DynamicCache
from transformers.generation.logits_process import (
    LogitsProcessorList,
    TemperatureLogitsWarper,
    TopKLogitsWarper,
    TopPLogitsWarper,
)

MODEL_DIR = str(Path.home() / "m44/models/qwen3-tts-0.6b-base")
REVISION = "5d83992436eae1d760afd27aff78a71d676296fc"
REF_AUDIO = str(Path.home() / "m44/data/LJSpeech-1.1/wavs/LJ001-0004.wav")
REF_TEXT = (
    "produced the block books, which were the immediate predecessors of the true printed book,"
)


def install_fast_subtalker(talker, top_k=50, top_p=1.0, temperature=0.9):
    """Monkeypatch code_predictor.generate with a manual loop.

    The official path calls HF GenerationMixin.generate() once per audio
    frame to sample 15 codebook tokens. This wrapper reproduces exactly:
      prefill  : inputs_embeds [1,2,D]  -> lm_head[0] -> sample
      step i   : embed_(i-1)(tok) -> 1-token forward -> lm_head[i] -> sample
    with the same warper chain HF applies for do_sample=True.
    """
    cp = talker.code_predictor
    n_steps = cp.config.num_code_groups - 1  # 15

    warpers = LogitsProcessorList()
    if temperature is not None and temperature != 1.0:
        warpers.append(TemperatureLogitsWarper(temperature))
    if top_k is not None and top_k > 0:
        warpers.append(TopKLogitsWarper(top_k))
    if top_p is not None and top_p < 1.0:
        warpers.append(TopPLogitsWarper(top_p))

    embeds = cp.model.get_input_embeddings()

    @torch.inference_mode()
    def fast_generate(self, inputs_embeds=None, **kwargs):
        emb = self.small_to_mtp_projection(inputs_embeds)
        cache = DynamicCache()
        cache_pos = torch.arange(emb.shape[1], device=emb.device)
        out = self.model(
            inputs_embeds=emb,
            past_key_values=cache,
            use_cache=True,
            cache_position=cache_pos,
        )
        h = out.last_hidden_state[:, -1:, :]
        toks = []
        pos = emb.shape[1]
        for step in range(n_steps):
            logits = self.lm_head[step](h)[:, -1, :].float()
            logits = warpers(None, logits)
            tok = torch.multinomial(logits.softmax(-1), 1)
            toks.append(tok)
            if step == n_steps - 1:
                break
            emb1 = self.small_to_mtp_projection(embeds[step](tok))
            out = self.model(
                inputs_embeds=emb1,
                past_key_values=cache,
                use_cache=True,
                cache_position=torch.tensor([pos], device=emb.device),
            )
            h = out.last_hidden_state
            pos += 1
        return types.SimpleNamespace(sequences=torch.cat(toks, dim=-1))

    cp.generate = types.MethodType(fast_generate, cp)
    return cp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--opt", default="none", choices=["none", "fastsub", "fastsub+compile", "compile"]
    )
    ap.add_argument("--texts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--audio-dir", default=None)
    ap.add_argument("--reps", type=int, default=1)
    args = ap.parse_args()

    texts = json.loads(Path(args.texts).read_text(encoding="utf-8"))
    from qwen_tts import Qwen3TTSModel

    torch.manual_seed(0)
    tts = Qwen3TTSModel.from_pretrained(
        MODEL_DIR,
        device_map="cuda:0",
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
    )
    talker = tts.model.talker

    gd = tts.generate_defaults
    if "fastsub" in args.opt:
        install_fast_subtalker(
            talker,
            top_k=gd.get("subtalker_top_k", 50),
            top_p=gd.get("subtalker_top_p", 1.0),
            temperature=gd.get("subtalker_temperature", 0.9),
        )
    if "compile" in args.opt:
        talker.model = torch.compile(talker.model, mode="reduce-overhead")
        talker.code_predictor.model = torch.compile(
            talker.code_predictor.model, mode="reduce-overhead"
        )

    prompt = tts.create_voice_clone_prompt(ref_audio=REF_AUDIO, ref_text=REF_TEXT)

    if args.audio_dir:
        Path(args.audio_dir).mkdir(parents=True, exist_ok=True)

    rows = []
    for case in texts:
        for rep in range(args.reps):
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()
            t0 = time.perf_counter()
            wavs, sr = tts.generate_voice_clone(
                text=case["text"],
                language="English",
                voice_clone_prompt=prompt,
            )
            torch.cuda.synchronize()
            total = time.perf_counter() - t0
            audio_s = len(wavs[0]) / sr
            row = {
                "id": case["id"],
                "chars": len(case["text"]),
                "opt": args.opt,
                "rep": rep,
                "total_s": round(total, 3),
                "audio_s": round(audio_s, 3),
                "rtf": round(total / max(audio_s, 1e-6), 4),
                "vram_peak_alloc_mib": round(torch.cuda.max_memory_allocated() / 1024**2, 1),
            }
            rows.append(row)
            print(json.dumps(row), flush=True)
            if args.audio_dir and rep == 0:
                import soundfile as sf

                sf.write(
                    f"{args.audio_dir}/{case['id']}.wav", np.asarray(wavs[0], dtype=np.float32), sr
                )

    out = {
        "experiment": "45-qwen3-tts-low-latency",
        "instrument": "m45_fastsub.py (EXPERIMENTAL runtime; weights untouched)",
        "identity": {
            "model_dir": MODEL_DIR,
            "revision": REVISION,
            "dtype": "bf16",
            "attn": "sdpa",
            "opt": args.opt,
            "sampling": "official defaults via generate_config",
            "seeded": "torch.manual_seed(0); AR sampling stochastic",
        },
        "rows": rows,
    }
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("FASTSUB-DONE", args.out)


if __name__ == "__main__":
    main()
