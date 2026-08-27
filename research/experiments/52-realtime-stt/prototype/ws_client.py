"""M52 prototype client — streams a WAV over the WebSocket like a
microphone would and measures the experience end to end THROUGH the
real transport.

Modes:
    realtime     — 100 ms PCM frames paced 1:1 with the clock
    flood        — frames sent 8x faster than realtime (backpressure probe)
    restart      — half the clip, disconnect mid-stream, reconnect, full
                   second session (stale-event / session-isolation probe)

    M52_WS_TOKEN=<secret> python ws_client.py <ws_url> <wav> <mode> <out.json>
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import wave
from pathlib import Path

import websockets

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE.parent / "evidence"
FRAME_MS = 100
SAMPLE_RATE = 16_000


def frames(path: Path) -> list[bytes]:
    with wave.open(str(path), "rb") as handle:
        if handle.getframerate() != SAMPLE_RATE or handle.getnchannels() != 1:
            msg = "need 16 kHz mono WAV"
            raise ValueError(msg)
        pcm = handle.readframes(handle.getnframes())
    step = SAMPLE_RATE * 2 * FRAME_MS // 1000
    return [pcm[i : i + step] for i in range(0, len(pcm), step)]


async def session(url: str, clip: list[bytes], pace: float, label: str) -> dict:
    events: list[dict] = []
    started = time.perf_counter()
    sent_s = 0.0
    async with websockets.connect(url, max_size=None) as ws:

        async def reader() -> None:
            try:
                async for raw in ws:
                    events.append(
                        {"at_s": round(time.perf_counter() - started, 3), **json.loads(raw)}
                    )
            except websockets.ConnectionClosed:
                pass

        reader_task = asyncio.create_task(reader())
        for frame in clip:
            await ws.send(frame)
            sent_s += FRAME_MS / 1000.0
            await asyncio.sleep((FRAME_MS / 1000.0) / pace)
        end_sent = time.perf_counter() - started
        await ws.send(json.dumps({"event": "end"}))
        await asyncio.wait_for(reader_task, timeout=120)
    partials = [e for e in events if e.get("event") == "transcript.partial" and e.get("text")]
    final = next((e for e in events if e.get("event") == "transcript.final"), None)
    return {
        "label": label,
        "pace": pace,
        "audio_seconds": round(len(clip) * FRAME_MS / 1000.0, 1),
        "session_id": events[0].get("session_id") if events else None,
        "events_total": len(events),
        "first_partial_s": partials[0]["at_s"] if partials else None,
        "partial_count": len(partials),
        "partial_cadence_s": (
            round((partials[-1]["at_s"] - partials[0]["at_s"]) / max(len(partials) - 1, 1), 2)
            if len(partials) > 1
            else None
        ),
        "end_sent_s": round(end_sent, 2),
        "final_at_s": final["at_s"] if final else None,
        "finalization_ms": round((final["at_s"] - end_sent) * 1000.0, 1) if final else None,
        "final_text": final["text"] if final else None,
        "degraded": any(e.get("event") == "session.degraded" for e in events),
        "last_partial_text": partials[-1]["text"] if partials else None,
    }


async def main() -> None:
    url_base, wav, mode, out_name = sys.argv[1:5]
    token = os.environ["M52_WS_TOKEN"]
    url = f"{url_base}/ws?token={token}&language=en"
    clip = frames(Path(wav))

    if mode == "realtime":
        result: dict = await session(url, clip, 1.0, "realtime")
    elif mode == "flood":
        result = await session(url, clip, 8.0, "flood-8x")
    elif mode == "restart":
        # First session: half the clip, then hard disconnect (no end event).
        half = clip[: len(clip) // 2]
        first_events: list[dict] = []
        ws = await websockets.connect(url, max_size=None)

        async def reader() -> None:
            try:
                async for raw in ws:
                    first_events.append(json.loads(raw))
            except websockets.ConnectionClosed:
                pass

        task = asyncio.create_task(reader())
        for frame in half:
            await ws.send(frame)
            await asyncio.sleep(FRAME_MS / 1000.0)
        await ws.close()  # mid-session disconnect, nothing finalized
        await task
        # Immediate second session, full clip.
        second = await session(url, clip, 1.0, "after-restart")
        first_id = first_events[0].get("session_id") if first_events else None
        result = {
            "label": "restart",
            "first_session_id": first_id,
            "first_session_finalized": any(
                e.get("event") == "transcript.final" for e in first_events
            ),
            "second": second,
            "ids_differ": bool(
                first_id and second["session_id"] and first_id != second["session_id"]
            ),
            "stale_text_leaked": bool(
                second["final_text"]
                and first_events
                and any(
                    e.get("text")
                    and e["text"] == second["final_text"]
                    and e.get("session_id") != second["session_id"]
                    for e in first_events
                )
            ),
        }
    else:
        raise SystemExit(f"unknown mode {mode}")

    EVIDENCE.mkdir(exist_ok=True)
    (EVIDENCE / out_name).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in ("final_text", "last_partial_text")},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
