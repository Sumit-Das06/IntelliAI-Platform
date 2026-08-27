"""M53 battery client — a microphone-shaped WebSocket session through
the REAL gateway (auth message → PCM frames at 1:1 pace → end), timing
every event the way a browser would see it.

    python rt_client.py <ws_url> <wav> <language> <mode> <out.json>

Modes: realtime (1:1 pace) | flood (8x) | nopace (as fast as possible).
The API key is read from the scratchpad key file and NEVER printed.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import statistics
import sys
import time
import wave
from pathlib import Path

import websockets

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"
FRAME_MS = 100
SAMPLE_RATE = 16_000
KEY = (
    Path(
        r"C:\Users\VIKASH~1\AppData\Local\Temp\claude"
        r"\d--Sumit-Projects-IntelliAI-Platform"
        r"\67762b73-e6aa-43b8-a730-264d0d432d4f\scratchpad\m24-key.txt"
    )
    .read_text(encoding="utf-8")
    .strip()
)


def frames(path: Path) -> list[bytes]:
    with wave.open(str(path), "rb") as handle:
        if handle.getframerate() != SAMPLE_RATE or handle.getnchannels() != 1:
            msg = "need 16 kHz mono WAV"
            raise ValueError(msg)
        pcm = handle.readframes(handle.getnframes())
    step = SAMPLE_RATE * 2 * FRAME_MS // 1000
    return [pcm[i : i + step] for i in range(0, len(pcm), step)]


async def main() -> None:
    url, wav_path, language, mode, out_name = sys.argv[1:6]
    clip = frames(Path(wav_path))
    pace = {"realtime": 1.0, "flood": 8.0, "nopace": 1000.0}[mode]
    events: list[dict] = []
    started = time.perf_counter()
    async with websockets.connect(url, max_size=None, open_timeout=15) as ws:
        await ws.send(
            json.dumps(
                {"event": "auth", "api_key": KEY, "language": language, "contribution": "on"}
            )
        )

        async def reader() -> None:
            try:
                async for raw in ws:
                    if isinstance(raw, bytes):
                        continue
                    events.append(
                        {"at_s": round(time.perf_counter() - started, 3), **json.loads(raw)}
                    )
            except websockets.ConnectionClosed:
                pass

        reader_task = asyncio.create_task(reader())
        for frame in clip:
            await ws.send(frame)
            await asyncio.sleep((FRAME_MS / 1000.0) / pace)
        end_sent = time.perf_counter() - started
        await ws.send(json.dumps({"event": "end"}))
        await asyncio.wait_for(reader_task, timeout=180)

    partials = [e for e in events if e.get("event") == "transcript.partial" and e.get("text")]
    final = next((e for e in events if e.get("event") == "transcript.final"), None)
    completed = next((e for e in events if e.get("event") == "session.completed"), None)
    audio_seconds = len(clip) * FRAME_MS / 1000.0
    # Partial latency proxy at the client: event arrival minus the audio
    # timeline position implied by 1:1 pacing (mode realtime only).
    if mode == "realtime":
        gaps = [b["at_s"] - a["at_s"] for a, b in itertools.pairwise(partials)]
    else:
        gaps = []
    result = {
        "url_path": url.split("/", 3)[-1],
        "wav": Path(wav_path).name,
        "language": language,
        "mode": mode,
        "audio_seconds": audio_seconds,
        "session_id": events[0].get("session_id") if events else None,
        "events_total": len(events),
        "first_partial_at_s": partials[0]["at_s"] if partials else None,
        "partial_count": len(partials),
        "partial_gap_p50_s": round(statistics.median(gaps), 2) if gaps else None,
        "sequences_monotonic": all(
            a.get("sequence", 0) < b.get("sequence", 1) for a, b in itertools.pairwise(partials)
        ),
        "end_sent_at_s": round(end_sent, 2),
        "final_at_s": final["at_s"] if final else None,
        "finalization_ms": round((final["at_s"] - end_sent) * 1000.0, 1) if final else None,
        "final_text": final.get("text") if final else None,
        "final_raw_text": final.get("raw_text") if final else None,
        "sample_id_present": bool(completed and completed.get("sample_id")),
        "degraded": any(e.get("event") == "session.degraded" for e in events),
        "errors": [e for e in events if e.get("event") == "session.error"],
    }
    EVIDENCE.mkdir(exist_ok=True)
    (EVIDENCE / out_name).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    safe = {k: v for k, v in result.items() if k not in ("final_text", "final_raw_text")}
    print(json.dumps(safe, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
