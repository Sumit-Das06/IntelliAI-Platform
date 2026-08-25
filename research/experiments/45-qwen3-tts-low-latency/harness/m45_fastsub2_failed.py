# M45 Phase 8 — EXPERIMENTAL fastsub v2: the manual sub-talker loop
# from fastsub.py, now with a StaticCache and a torch.compile
# (reduce-overhead / CUDA-graph) step function. Same weights, same
# math, same sampling law; outputs cloned out of the graph buffers.
import argparse
import json
import time
import types
from pathlib import Path

import numpy as np
import torch
from transformers.cache_utils import StaticCache
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


def install_fast_subtalker_v2(talker, top_k=50, top_p=1.0, temperature=0.9, compile_steps=True):
    cp = talker.code_predictor
    n_steps = cp.config.num_code_groups - 1  # 15
    dev = next(cp.parameters()).device

    warpers = LogitsProcessorList()
    if temperature is not None and temperature != 1.0:
        warpers.append(TemperatureLogitsWarper(temperature))
    if top_k is not None and top_k > 0:
        warpers.append(TopKLogitsWarper(top_k))
    if top_p is not None and top_p < 1.0:
        warpers.append(TopPLogitsWarper(top_p))

    embeds = cp.model.get_input_embeddings()
    cache = StaticCache(
        config=cp.model.config,
        max_batch_size=1,
        max_cache_len=n_steps + 4,
        device=dev,
        dtype=next(cp.parameters()).dtype,
    )

    def _step(emb, cache_position):
        out = cp.model(
            inputs_embeds=emb, past_key_values=cache, use_cache=True, cache_position=cache_position
        )
        return out.last_hidden_state

    step_fn = torch.compile(_step, mode="reduce-overhead") if compile_steps else _step

    pos_pre = torch.arange(2, device=dev)
    pos_steps = [torch.tensor([2 + i], device=dev) for i in range(n_steps)]

    @torch.no_grad()
    def fast_generate(self, inputs_embeds=None, **kwargs):
        cache.reset()
        emb = self.small_to_mtp_projection(inputs_embeds)
        torch.compiler.cudagraph_mark_step_begin()
        h = step_fn(emb, pos_pre).clone()[:, -1:, :]
        toks = []
        for step in range(n_steps):
            logits = self.lm_head[step](h)[:, -1, :].float()
            logits = warpers(None, logits)
            tok = torch.multinomial(logits.softmax(-1), 1)
            toks.append(tok)
            if step == n_steps - 1:
                break
            emb1 = self.small_to_mtp_projection(embeds[step](tok))
            torch.compiler.cudagraph_mark_step_begin()
            h = step_fn(emb1, pos_steps[step]).clone()
        return types.SimpleNamespace(sequences=torch.cat(toks, dim=-1))

    cp.generate = types.MethodType(fast_generate, cp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--texts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-compile", action="store_true")
    ap.add_argument("--audio-dir", default=None)
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
    gd = tts.generate_defaults
    install_fast_subtalker_v2(
        tts.model.talker,
        top_k=gd.get("subtalker_top_k", 50),
        top_p=gd.get("subtalker_top_p", 1.0),
        temperature=gd.get("subtalker_temperature", 0.9),
        compile_steps=not args.no_compile,
    )
    prompt = tts.create_voice_clone_prompt(ref_audio=REF_AUDIO, ref_text=REF_TEXT)

    if args.audio_dir:
        Path(args.audio_dir).mkdir(parents=True, exist_ok=True)

    rows = []
    for i, case in enumerate(texts):
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        wavs, sr = tts.generate_voice_clone(
            text=case["text"], language="English", voice_clone_prompt=prompt
        )
        torch.cuda.synchronize()
        total = time.perf_counter() - t0
        audio_s = len(wavs[0]) / sr
        row = {
            "id": case["id"],
            "chars": len(case["text"]),
            "opt": "fastsub2" + ("" if args.no_compile else "+cudagraph"),
            "warmup_run": i == 0,
            "total_s": round(total, 3),
            "audio_s": round(audio_s, 3),
            "rtf": round(total / max(audio_s, 1e-6), 4),
            "vram_peak_alloc_mib": round(torch.cuda.max_memory_allocated() / 1024**2, 1),
        }
        rows.append(row)
        print(json.dumps(row), flush=True)
        if args.audio_dir:
            import soundfile as sf

            sf.write(
                f"{args.audio_dir}/{case['id']}.wav", np.asarray(wavs[0], dtype=np.float32), sr
            )

    out = {
        "experiment": "45-qwen3-tts-low-latency",
        "instrument": "m45_fastsub2.py (EXPERIMENTAL; StaticCache + CUDA-graph step)",
        "identity": {
            "model_dir": MODEL_DIR,
            "revision": REVISION,
            "dtype": "bf16",
            "attn": "sdpa",
            "seeded": "torch.manual_seed(0); AR sampling stochastic",
        },
        "rows": rows,
    }
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("FASTSUB2-DONE", args.out)


if __name__ == "__main__":
    main()
