# M45 Phase 9-10 — vLLM-Omni serving bench for Qwen3-TTS 0.6B Base.
# Measures TRUE streaming through POST /v1/audio/speech
# (stream=true, response_format=pcm): TTFA = first PCM chunk on the
# wire, chunk cadence, total wall, derived RTF; plus a non-stream run.
import argparse
import json
import time
import wave
from pathlib import Path

import httpx

REF_AUDIO = str(Path.home() / "m44/data/LJSpeech-1.1/wavs/LJ001-0004.wav")
REF_TEXT = (
    "produced the block books, which were the immediate predecessors of the true printed book,"
)
SR = 24000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8091")
    ap.add_argument("--texts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--audio-dir", default=None)
    ap.add_argument("--reps", type=int, default=1)
    args = ap.parse_args()

    texts = json.loads(Path(args.texts).read_text(encoding="utf-8"))
    if args.audio_dir:
        Path(args.audio_dir).mkdir(parents=True, exist_ok=True)

    rows = []
    with httpx.Client(timeout=600.0) as client:
        for case in texts:
            for rep in range(args.reps):
                payload = {
                    "input": case["text"],
                    "task_type": "Base",
                    "ref_audio": f"file://{REF_AUDIO}",
                    "ref_text": REF_TEXT,
                    "language": "English",
                    "stream": True,
                    "response_format": "pcm",
                }
                chunks = []
                t0 = time.perf_counter()
                ttfa = None
                with client.stream("POST", f"{args.base_url}/v1/audio/speech", json=payload) as r:
                    r.raise_for_status()
                    for chunk in r.iter_bytes():
                        if chunk:
                            now = time.perf_counter()
                            if ttfa is None:
                                ttfa = now - t0
                            chunks.append((now - t0, chunk))
                total = time.perf_counter() - t0
                pcm = b"".join(c for _, c in chunks)
                audio_s = len(pcm) / 2 / SR
                marks = [{"t_s": round(t, 3), "bytes": len(c)} for t, c in chunks[:10]]
                row = {
                    "id": case["id"],
                    "chars": len(case["text"]),
                    "rep": rep,
                    "runtime": "vllm-omni-0.26.0 (vllm 0.26.0)",
                    "stream": True,
                    "ttfa_s": round(ttfa, 3) if ttfa else None,
                    "total_s": round(total, 3),
                    "audio_s": round(audio_s, 3),
                    "rtf": round(total / max(audio_s, 1e-6), 4),
                    "n_chunks": len(chunks),
                    "first_chunks": marks,
                    "true_streaming": bool(ttfa is not None and ttfa < 0.8 * total),
                }
                rows.append(row)
                print(json.dumps(row), flush=True)
                if args.audio_dir and rep == 0:
                    with wave.open(f"{args.audio_dir}/{case['id']}.wav", "wb") as fh:
                        fh.setnchannels(1)
                        fh.setsampwidth(2)
                        fh.setframerate(SR)
                        fh.writeframes(pcm)

        # one non-stream comparison on the short text
        case = texts[0]
        payload = {
            "input": case["text"],
            "task_type": "Base",
            "ref_audio": f"file://{REF_AUDIO}",
            "ref_text": REF_TEXT,
            "language": "English",
            "stream": False,
            "response_format": "wav",
        }
        t0 = time.perf_counter()
        r = client.post(f"{args.base_url}/v1/audio/speech", json=payload)
        total = time.perf_counter() - t0
        rows.append(
            {
                "id": case["id"],
                "stream": False,
                "total_s": round(total, 3),
                "bytes": len(r.content),
                "status": r.status_code,
            }
        )
        print(json.dumps(rows[-1]), flush=True)

    Path(args.out).write_text(
        json.dumps(
            {
                "experiment": "45-qwen3-tts-low-latency",
                "instrument": "m45_vllm_bench.py (client-side wire measurement)",
                "rows": rows,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print("VLLM-BENCH-DONE", args.out)


if __name__ == "__main__":
    main()
