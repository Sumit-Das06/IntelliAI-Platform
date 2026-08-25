# M45 Phase 10-13 — EXPERIMENTAL true-streaming harness for the
# official qwen-tts runtime. No weight changes; no upstream edits:
#   * a forward hook on the talker collects each frame's 16-codebook
#     code the moment it is sampled (the official loop already returns
#     it per step in hidden_states[1]);
#   * a consumer thread decodes incremental chunks through the CAUSAL
#     codec decoder with a left-context window, emitting only new PCM.
# "True streaming" per the M45 definition: first PCM exists while the
# talker is still generating later frames — measured, not claimed.
# Continuity proof: streamed concat vs one-shot decode of the SAME
# codes (identical codes => any difference is decode-boundary error).
import argparse
import json
import queue
import threading
import time
from pathlib import Path

import numpy as np
import torch

MODEL_DIR = str(Path.home() / "m44/models/qwen3-tts-0.6b-base")
REVISION = "5d83992436eae1d760afd27aff78a71d676296fc"
REF_AUDIO = str(Path.home() / "m44/data/LJSpeech-1.1/wavs/LJ001-0004.wav")
REF_TEXT = (
    "produced the block books, which were the immediate predecessors of the true printed book,"
)
FRAME_SR = 12  # codec frames per second
OUT_SR = 24000
HOP = OUT_SR // FRAME_SR  # samples per frame (2000)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--texts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--first-chunk-frames", type=int, default=12)
    ap.add_argument("--chunk-frames", type=int, default=24)
    ap.add_argument("--left-context-frames", type=int, default=72)
    ap.add_argument("--fastsub", action="store_true")
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
    core = tts.model
    talker = core.talker
    eos_id = core.config.talker_config.codec_eos_token_id

    if args.fastsub:
        import fastsub as fs

        gd = tts.generate_defaults
        fs.install_fast_subtalker(
            talker,
            top_k=gd.get("subtalker_top_k", 50),
            top_p=gd.get("subtalker_top_p", 1.0),
            temperature=gd.get("subtalker_temperature", 0.9),
        )

    prompt = tts.create_voice_clone_prompt(ref_audio=REF_AUDIO, ref_text=REF_TEXT)
    ref_code = prompt[0].ref_code  # (T_ref, 16)

    st = core.speech_tokenizer

    def decode_codes(codes_2d):
        wavs, sr = st.decode([{"audio_codes": codes_2d}])
        return np.asarray(wavs[0], dtype=np.float32), sr

    if args.audio_dir:
        Path(args.audio_dir).mkdir(parents=True, exist_ok=True)

    results = []
    for case in texts:
        frame_q: queue.Queue = queue.Queue()

        def hook(module, inp, out, frame_q=frame_q):
            codes = out.hidden_states[1]  # (1,16) per generate step; None at prefill
            if codes is not None:
                frame_q.put((time.perf_counter(), codes.detach()[0].clone()))

        h = talker.register_forward_hook(hook)

        # Incremental strategy: decode the GROWING PREFIX (ref + all
        # frames so far) each flush and emit only the new samples,
        # holding back a small right-edge guard until the final flush.
        # The codec decoder is causal, so earlier samples are stable;
        # the guard absorbs the only unstable region (conv right edge).
        # Continuity vs the final full decode is then exact by
        # construction wherever emitted samples exist.
        pcm_parts = []
        frames_buf = []  # accumulated code rows (torch [16])
        decoded_frames = 0  # frames included in emitted PCM so far
        emitted_samples = 0  # samples already emitted
        ref_cut = None  # samples occupied by the ref clip prefix
        guard = 2 * HOP  # right-edge hold-back except final flush
        stream_done = threading.Event()
        gen_result = {}

        def producer(case=case, gen_result=gen_result, stream_done=stream_done):
            torch.manual_seed(0)
            wavs, sr = tts.generate_voice_clone(
                text=case["text"],
                language="English",
                voice_clone_prompt=prompt,
            )
            gen_result["oneshot"] = np.asarray(wavs[0], dtype=np.float32)
            gen_result["sr"] = sr
            stream_done.set()

        torch.cuda.synchronize()
        t0 = time.perf_counter()
        th = threading.Thread(target=producer)
        th.start()

        ttfa = None
        chunk_marks = []
        while True:
            try:
                _t_arr, code = frame_q.get(timeout=0.05)
                if int(code[0]) == eos_id:
                    continue
                frames_buf.append(code)
            except queue.Empty:
                if stream_done.is_set() and frame_q.empty():
                    pass
                else:
                    continue
            n = len(frames_buf)
            need = args.first_chunk_frames if decoded_frames == 0 else args.chunk_frames
            flush_all = stream_done.is_set() and frame_q.empty()
            if (n - decoded_frames >= need) or (flush_all and n > decoded_frames):
                seg = torch.stack(frames_buf[:n], dim=0)
                if ref_cut is None:
                    ref_wav, _ = decode_codes(ref_code)
                    ref_cut = len(ref_wav)
                full = torch.cat([ref_code.to(seg.device), seg], dim=0)
                wav_prefix, _ = decode_codes(full)
                wav_gen = wav_prefix[ref_cut:]
                cut_end = len(wav_gen) if flush_all else max(0, len(wav_gen) - guard)
                new = wav_gen[emitted_samples:cut_end]
                if len(new) > 0 or flush_all:
                    pcm_parts.append(new)
                    emitted_samples = cut_end
                    t_ready = time.perf_counter()
                    if ttfa is None:
                        ttfa = t_ready - t0
                    chunk_marks.append(
                        {
                            "frames": n - decoded_frames,
                            "t_s": round(t_ready - t0, 3),
                            "samples": len(new),
                        }
                    )
                    decoded_frames = n
            if flush_all and decoded_frames >= len(frames_buf):
                break
        th.join()
        h.remove()
        total = time.perf_counter() - t0

        streamed = np.concatenate(pcm_parts) if pcm_parts else np.zeros(1, np.float32)
        # continuity gold = ONE decode of the same ref+codes with the
        # same exact ref cut (the wrapper's own output uses a
        # proportional cut, so it is kept separately as oneshot).
        gen_codes = torch.stack(frames_buf, dim=0)
        full = torch.cat([ref_code.to(gen_codes.device), gen_codes], dim=0)
        gold_wav, _ = decode_codes(full)
        gold = gold_wav[ref_cut:]
        oneshot = gen_result["oneshot"]

        # continuity: same codes decoded once vs chunk-emitted
        seg_len = min(len(streamed), len(gold))
        diff = np.abs(streamed[:seg_len] - gold[:seg_len])
        row = {
            "id": case["id"],
            "chars": len(case["text"]),
            "fastsub": bool(args.fastsub),
            "first_chunk_frames": args.first_chunk_frames,
            "chunk_frames": args.chunk_frames,
            "left_context_frames": args.left_context_frames,
            "ttfa_s": round(ttfa, 3) if ttfa else None,
            "total_s": round(total, 3),
            "audio_s": round(len(streamed) / OUT_SR, 3),
            "n_chunks": len(chunk_marks),
            "chunks": chunk_marks[:8],
            "len_streamed": len(streamed),
            "len_gold": len(gold),
            "len_oneshot_wrapper": len(oneshot),
            "len_delta_vs_gold": int(len(streamed) - len(gold)),
            "continuity_max_abs_diff": float(diff.max()) if seg_len else None,
            "continuity_rms_diff": float(np.sqrt((diff**2).mean())) if seg_len else None,
        }
        results.append(row)
        print(json.dumps(row), flush=True)
        if args.audio_dir:
            import soundfile as sf

            sf.write(f"{args.audio_dir}/{case['id']}-streamed.wav", streamed, OUT_SR)
            sf.write(f"{args.audio_dir}/{case['id']}-oneshot.wav", oneshot, OUT_SR)

    out = {
        "experiment": "45-qwen3-tts-low-latency",
        "instrument": "m45_stream.py (EXPERIMENTAL hook streaming; weights untouched)",
        "identity": {
            "model_dir": MODEL_DIR,
            "revision": REVISION,
            "dtype": "bf16",
            "attn": "sdpa",
            "true_streaming_definition": "PCM chunk exists before total synthesis completes",
        },
        "rows": results,
    }
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("STREAM-DONE", args.out)


if __name__ == "__main__":
    main()
