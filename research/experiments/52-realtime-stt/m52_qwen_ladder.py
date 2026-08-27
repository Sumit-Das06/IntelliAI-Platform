"""M52 Qwen3-ASR E3 incremental-cost ladder — the honest realtime cost
of the CURRENT Hindi engine (llama.cpp llama-server, CPU, staging
container on 127.0.0.1:8001).

Repo-verified: the engine sends one WAV per completion request and
keeps NO audio state between requests, so a streaming session that
wants an updated partial must re-submit the WHOLE window. This ladder
measures exactly that curve: inference_ms as a function of audio
length, on real prefixes of one continuous Hindi clip.

    python m52_qwen_ladder.py
"""

from __future__ import annotations

import json
import time
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"
SCRATCH = Path(
    r"C:\Users\VIKASH~1\AppData\Local\Temp\claude"
    r"\d--Sumit-Projects-IntelliAI-Platform"
    r"\67762b73-e6aa-43b8-a730-264d0d432d4f\scratchpad"
)
CLIPS = SCRATCH / "m52clips"
RUNTIME = "http://127.0.0.1:8001/v1/transcribe"


def transcribe(audio: Path, language: str | None) -> dict:
    boundary = uuid.uuid4().hex
    params = json.dumps({"language": language} if language else {})
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="params"\r\n\r\n{params}\r\n'
    ).encode()
    body += (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{audio.name}"\r\nContent-Type: application/octet-stream\r\n\r\n'
    ).encode()
    body += audio.read_bytes() + b"\r\n" + f"--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        RUNTIME,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=900) as response:  # noqa: S310
        envelope = json.loads(response.read())
    wall = time.perf_counter() - started
    output = envelope["output"]
    stages = envelope["timing"]["stages"]
    return {
        "duration_s": round(output["duration_seconds"], 2),
        "inference_ms": round(stages["inference"], 1),
        "rtf": round(stages["inference"] / 1000.0 / max(output["duration_seconds"], 0.01), 3),
        "wall_s": round(wall, 2),
        "text": output["text"],
    }


def main() -> None:
    EVIDENCE.mkdir(exist_ok=True)

    # warm the slot once (the first request after idle pays start-up costs)
    transcribe(CLIPS / "hindi_pre_1s.wav", "hi")

    ladder = {}
    for name in ("1s", "2s", "3s", "5s", "8s", "12s", "16s", "full"):
        runs = [transcribe(CLIPS / f"hindi_pre_{name}.wav", "hi") for _ in range(3)]
        times = sorted(run["inference_ms"] for run in runs)
        ladder[name] = {
            "duration_s": runs[0]["duration_s"],
            "inference_ms_median": times[1],
            "rtf_median": round(times[1] / 1000.0 / max(runs[0]["duration_s"], 0.01), 3),
            "text": runs[-1]["text"],
        }
        print(
            name,
            ladder[name]["duration_s"],
            "s ->",
            times[1],
            "ms (rtf",
            ladder[name]["rtf_median"],
            ")",
        )

    # Chunk-cadence verdict: with no state reuse, an update at time T
    # costs inference(T). Realtime keeps up only while inference(T) stays
    # under the update interval — compute where the curve crosses 0.5 s
    # and 1.0 s.
    crossings = {}
    for budget_ms in (500.0, 1000.0, 2000.0):
        feasible = [
            row["duration_s"] for row in ladder.values() if row["inference_ms_median"] <= budget_ms
        ]
        crossings[f"window_seconds_decodable_in_{int(budget_ms)}ms"] = (
            max(feasible) if feasible else 0.0
        )

    # Language-mix behavior through the CURRENT hi route (E3), n=1 each,
    # qualitative: what does the engine do with English/mixed audio?
    mixed = {
        "hindi_short_hi_route": transcribe(CLIPS / "16k_hindi_short.wav", "hi"),
        "english_hi_route": transcribe(CLIPS / "16k_en_report.wav", "hi"),
        "hinglish_hi_route": transcribe(CLIPS / "hinglish.wav", "hi"),
        "hinglish_en_route_whisper": transcribe(CLIPS / "hinglish.wav", "en"),
    }

    payload = {
        "engine": "qwen3-asr-0.6b-hi-ft-e3 via llama.cpp llama-server (staging container, CPU)",
        "state_reuse": "NONE — repo-verified: one WAV per completion request, "
        "full re-inference per update",
        "ladder": ladder,
        "cadence_crossings": crossings,
        "language_mix_qualitative_n1": mixed,
    }
    (EVIDENCE / "qwen-ladder.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("crossings:", crossings)


if __name__ == "__main__":
    main()
