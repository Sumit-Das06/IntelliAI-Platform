"""M55 Phase 14 — mixed workload: EN realtime + HI realtime + HI batch
hammering its own GPU instance, all at once.

    python mixed_workload.py mixed-workload.json

Realtime rides llama-server :8797 (HI) + in-process whisper; batch
rides its OWN instance :8798 — the isolation design under test: batch
must not starve realtime.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import rt55_client as client

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"
SCRATCH = Path(
    r"C:\Users\VIKASH~1\AppData\Local\Temp\claude"
    r"\d--Sumit-Projects-IntelliAI-Platform"
    r"\67762b73-e6aa-43b8-a730-264d0d432d4f\scratchpad"
)
URL = "ws://127.0.0.1:8000/v1/audio/realtime"
KEY = (SCRATCH / "m24-key.txt").read_text(encoding="utf-8").strip()


def batch_once(path: Path) -> dict:
    boundary = uuid.uuid4().hex
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\n'
        "intelliai-stt\r\n"
        f'--{boundary}\r\nContent-Disposition: form-data; name="language"\r\n\r\nhi\r\n'
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{path.name}"\r\nContent-Type: application/octet-stream\r\n\r\n'
    ).encode()
    body += path.read_bytes() + b"\r\n" + f"--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        "http://127.0.0.1:8000/v1/audio/transcriptions",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Authorization": f"Bearer {KEY}",
        },
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=900) as response:  # noqa: S310
        text = str(json.loads(response.read())["text"])
    return {"latency_s": round(time.perf_counter() - started, 2), "words": len(text.split())}


async def batch_loop(stop: asyncio.Event, rows: list[dict]) -> None:
    clip = SCRATCH / "m52hclips" / "real30s.wav"
    while not stop.is_set():
        rows.append(await asyncio.to_thread(batch_once, clip))


async def main() -> None:
    out_name = sys.argv[1]
    stop = asyncio.Event()
    batch_rows: list[dict] = []
    batch_task = asyncio.create_task(batch_loop(stop, batch_rows))
    realtime = await asyncio.gather(
        client.run(
            URL, str(SCRATCH / "m52clips" / "boss30.wav"), "en", "realtime", f"{out_name}.en.json"
        ),
        client.run(
            URL, str(SCRATCH / "m52hclips" / "real30s.wav"), "hi", "realtime", f"{out_name}.hi.json"
        ),
        return_exceptions=True,
    )
    stop.set()
    await batch_task
    sessions = []
    for row in realtime:
        if isinstance(row, BaseException):
            sessions.append({"error": type(row).__name__})
        else:
            sessions.append(
                {
                    k: row.get(k)
                    for k in (
                        "language",
                        "first_partial_at_s",
                        "partial_gap_p50_s",
                        "partial_gap_p95_s",
                        "finalization_ms",
                        "degraded",
                    )
                }
            )
    result = {
        "design": "batch on its OWN llama-server (:8798); realtime on :8797 + in-process whisper",
        "realtime_sessions_during_batch_hammer": sessions,
        "batch_calls_completed": len(batch_rows),
        "batch_latency_p50_s": round(statistics.median(r["latency_s"] for r in batch_rows), 2)
        if batch_rows
        else None,
        "batch_words": sorted({r["words"] for r in batch_rows}),
    }
    (EVIDENCE / f"{out_name}.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
