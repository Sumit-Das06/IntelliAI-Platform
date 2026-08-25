# M45 Phase 16-17 — GPU concurrency ladder + repeated-request memory
# check on the official runtime (one process, one model, thread pool —
# the shape our runtime would serve in). LOCAL HARDWARE MEASUREMENT,
# not production capacity.
import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import torch

MODEL_DIR = str(Path.home() / "m44/models/qwen3-tts-0.6b-base")
REF_AUDIO = str(Path.home() / "m44/data/LJSpeech-1.1/wavs/LJ001-0004.wav")
REF_TEXT = (
    "produced the block books, which were the immediate predecessors of the true printed book,"
)
TEXT = "Thank you for calling IntelliAI support. How can I help you today?"


def rss_mib():
    import psutil

    return psutil.Process().memory_info().rss / 1024**2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--fastsub", action="store_true")
    ap.add_argument("--ladder", default="1,2,4,8")
    ap.add_argument("--repeat", type=int, default=50)
    args = ap.parse_args()

    from qwen_tts import Qwen3TTSModel

    torch.manual_seed(0)
    tts = Qwen3TTSModel.from_pretrained(
        MODEL_DIR,
        device_map="cuda:0",
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
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

    lock_stats = {"fail": 0}
    lock = threading.Lock()

    def one_call():
        t0 = time.perf_counter()
        try:
            wavs, sr = tts.generate_voice_clone(
                text=TEXT, language="English", voice_clone_prompt=prompt
            )
            dur = len(wavs[0]) / sr
        except Exception:
            with lock:
                lock_stats["fail"] += 1
            return None
        return (time.perf_counter() - t0, dur)

    # warm-up
    one_call()

    ladder_rows = []
    for c in [int(x) for x in args.ladder.split(",")]:
        lock_stats["fail"] = 0
        torch.cuda.reset_peak_memory_stats()
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=c) as ex:
            outs = list(ex.map(lambda _: one_call(), range(c * 2)))
        wall = time.perf_counter() - t0
        oks = [o for o in outs if o]
        lat = sorted(o[0] for o in oks)
        row = {
            "concurrency": c,
            "requests": c * 2,
            "ok": len(oks),
            "failures": lock_stats["fail"],
            "wall_s": round(wall, 2),
            "p50_s": round(lat[len(lat) // 2], 2) if lat else None,
            "p95_s": round(lat[max(0, int(len(lat) * 0.95) - 1)], 2) if lat else None,
            "throughput_rps": round(len(oks) / wall, 3),
            "audio_s_each": round(oks[0][1], 2) if oks else None,
            "vram_peak_alloc_mib": round(torch.cuda.max_memory_allocated() / 1024**2, 1),
        }
        ladder_rows.append(row)
        print(json.dumps(row), flush=True)

    # repeated-request growth (Phase 17)
    mem_rows = []
    torch.cuda.empty_cache()
    for i in range(args.repeat):
        one_call()
        if i + 1 in (1, 10, 25, 50, 100) or i == args.repeat - 1:
            mem_rows.append(
                {
                    "request": i + 1,
                    "vram_alloc_mib": round(torch.cuda.memory_allocated() / 1024**2, 1),
                    "vram_reserved_mib": round(torch.cuda.memory_reserved() / 1024**2, 1),
                    "rss_mib": round(rss_mib(), 1),
                }
            )
            print(json.dumps(mem_rows[-1]), flush=True)

    out = {
        "experiment": "45-qwen3-tts-low-latency",
        "instrument": "m45_conc.py (thread-pool concurrency on one model)",
        "note": "local hardware measurement, NOT production capacity",
        "fastsub": bool(args.fastsub),
        "text_chars": len(TEXT),
        "ladder": ladder_rows,
        "repeated_requests": mem_rows,
    }
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("CONC-DONE", args.out)


if __name__ == "__main__":
    main()
