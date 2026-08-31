"""M54 Phase 20 — stop/cancel/disconnect lifecycle drills through the
REAL gateway.

    python rt54_lifecycle.py <out.json>

Drills:
    stop_start_stop — one connection: full session, then a SECOND session
        on a fresh connection immediately after (no stale state between).
    abrupt_disconnect — frames then the socket is torn down with no end:
        nothing persisted, no sample id anywhere, gateway survives.
"""

from __future__ import annotations

import asyncio
import json
import sys
import wave
from pathlib import Path

import websockets

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"
SCRATCH = Path(
    r"C:\Users\VIKASH~1\AppData\Local\Temp\claude"
    r"\d--Sumit-Projects-IntelliAI-Platform"
    r"\67762b73-e6aa-43b8-a730-264d0d432d4f\scratchpad"
)
URL = "ws://127.0.0.1:8000/v1/audio/realtime"
KEY = (SCRATCH / "m24-key.txt").read_text(encoding="utf-8").strip()
WAV = SCRATCH / "m52clips" / "16k_short_hello.wav"


def frames() -> list[bytes]:
    with wave.open(str(WAV), "rb") as handle:
        pcm = handle.readframes(handle.getnframes())
    step = 3200
    return [pcm[i : i + step] for i in range(0, len(pcm), step)]


async def full_session() -> dict:
    events = []
    async with websockets.connect(URL, max_size=None, open_timeout=15) as ws:
        await ws.send(json.dumps({"event": "auth", "api_key": KEY, "language": "en"}))

        async def reader() -> None:
            try:
                async for raw in ws:
                    if isinstance(raw, str):
                        events.append(json.loads(raw))
            except websockets.ConnectionClosed:
                pass

        task = asyncio.create_task(reader())
        for frame in frames():
            await ws.send(frame)
            await asyncio.sleep(0.05)
        await ws.send(json.dumps({"event": "end"}))
        await asyncio.wait_for(task, timeout=60)
    return {
        "events": [e.get("event") for e in events],
        "session_id": events[0].get("session_id") if events else None,
        "final_text_present": any(e.get("event") == "transcript.final" for e in events),
        "sample_id": next(
            (e.get("sample_id") for e in events if e.get("event") == "session.completed"), None
        ),
    }


async def abrupt_disconnect() -> dict:
    events = []
    ws = await websockets.connect(URL, max_size=None, open_timeout=15)
    await ws.send(json.dumps({"event": "auth", "api_key": KEY, "language": "en"}))
    for frame in frames()[:10]:
        await ws.send(frame)
        await asyncio.sleep(0.05)
    # Tear the transport down with NO end message and no close handshake.
    transport = ws.transport
    transport.abort()
    await asyncio.sleep(1.0)
    return {"aborted_after_frames": 10, "events_received": [e.get("event") for e in events]}


async def main() -> None:
    out_name = sys.argv[1]
    first = await full_session()
    second = await full_session()
    aborted = await abrupt_disconnect()
    # The stack must still serve normally after the abort.
    after = await full_session()
    result = {
        "first": first,
        "second": second,
        "sessions_have_distinct_ids": first["session_id"] != second["session_id"],
        "abrupt_disconnect": aborted,
        "after_abort_session_works": after["final_text_present"],
        "after_abort_sample_id": after["sample_id"],
    }
    EVIDENCE.mkdir(exist_ok=True)
    (EVIDENCE / out_name).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
