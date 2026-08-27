"""M52 ISOLATED realtime-STT prototype server — research only.

Lives entirely outside production: its own process, its own port, its
own shared-secret auth. It exists to prove/measure the PROPOSED
transport + event contract:

    client → binary frames: 16 kHz mono s16le PCM chunks
    client → text frame  : {"event": "end"}
    server → session.started   {session_id}
    server → transcript.partial {session_id, text, sequence, is_final: false}
    server → transcript.final   {session_id, text, sequence, is_final: true}
    server → session.completed  {session_id}
    server → session.degraded   {reason}   (backpressure policy: loud, never silent)

Decode = the CURRENT engine style (faster-whisper whisper-small INT8,
greedy partials, beam-5 final, rolling 25 s window with 5 s commit
margin), VAD = the production EnergyVad, so silence never reaches the
model. No state is shared between sessions; a session id is minted per
connection and stamped on every event.

    M52_WS_TOKEN=<secret> python ws_server.py [port]
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import secrets
import sys
from pathlib import Path

import numpy as np
import uvicorn
from fastapi import FastAPI, WebSocket

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "services/stt-runtime/src"))
sys.path.insert(0, str(ROOT / "packages/runtime-contract/src"))
sys.path.insert(0, str(ROOT / "packages/runtime-core/src"))

from intelliai_stt_runtime.pipeline.audio import DecodedAudio  # noqa: E402
from intelliai_stt_runtime.pipeline.vad import EnergyVad  # noqa: E402

MODEL_DIR = ROOT / "models" / "whisper-small" / "v1"
SAMPLE_RATE = 16_000
MIN_STEP_S = 0.5  # decode only when this much NEW audio arrived
MAX_WINDOW_S = 25.0
COMMIT_MARGIN_S = 5.0
MAX_BUFFER_S = 60.0  # backpressure ceiling: loud degrade, never silent drop

app = FastAPI()
_model = None
_vad = EnergyVad()


def model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        _model = WhisperModel(str(MODEL_DIR), device="cpu", compute_type="int8")
    return _model


def decode(window: np.ndarray, language: str, beam: int) -> tuple[str, list]:
    segments, _ = model().transcribe(
        window,
        task="transcribe",
        language=language,
        beam_size=beam,
        vad_filter=False,
        condition_on_previous_text=False,
    )
    rows = [(segment.start, segment.end, segment.text) for segment in segments]
    return "".join(row[2] for row in rows).strip(), rows


def has_speech(window: np.ndarray) -> bool:
    pcm = (window * 32768.0).astype(np.int16).tobytes()
    audio = DecodedAudio(
        pcm=pcm,
        sample_rate_hz=SAMPLE_RATE,
        duration_seconds=len(window) / SAMPLE_RATE,
        channels=1,
        sample_width_bytes=2,
    )
    return _vad.analyze(audio).has_speech


@app.websocket("/ws")
async def realtime(ws: WebSocket) -> None:
    # Auth BEFORE any audio is accepted (M52 security law).
    token = ws.query_params.get("token", "")
    if not secrets.compare_digest(token, os.environ.get("M52_WS_TOKEN", "")):
        await ws.close(code=4401)
        return
    await ws.accept()
    session_id = secrets.token_hex(8)
    language = ws.query_params.get("language", "en")
    await ws.send_text(json.dumps({"event": "session.started", "session_id": session_id}))

    chunks: list[np.ndarray] = []
    committed = ""
    window_start = 0.0
    decoded_to = 0.0
    sequence = 0
    ended = False
    gone = False
    degraded = False
    loop = asyncio.get_running_loop()

    async def receiver() -> None:
        """Drains the socket CONTINUOUSLY so decoding never blocks intake."""
        nonlocal ended, gone
        try:
            while not ended:
                message = await ws.receive()
                if message.get("type") == "websocket.disconnect":
                    gone = True
                    return
                if (data := message.get("bytes")) is not None:
                    chunks.append(np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0)
                elif (text := message.get("text")) is not None and (
                    json.loads(text).get("event") == "end"
                ):
                    ended = True
        except Exception:
            gone = True

    async def emit(event: str, **fields: object) -> None:
        await ws.send_text(
            json.dumps({"event": event, "session_id": session_id, **fields}, ensure_ascii=False)
        )

    receiver_task = asyncio.create_task(receiver())
    try:
        while True:
            if gone:
                return  # client vanished — the session dies with it, nothing leaks
            buffer = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
            available = len(buffer) / SAMPLE_RATE

            if available - decoded_to > MAX_BUFFER_S and not degraded:
                degraded = True
                await emit(
                    "session.degraded",
                    reason="audio arriving faster than realtime processing; "
                    "buffer bounded, transcription continues lagged",
                )

            # `ended` can flip DURING a decode (the executor await yields to
            # the receiver) — capture the pass's finality NOW so a partial
            # can never be mislabeled final and the true final always
            # decodes the complete buffer.
            is_final_pass = ended
            if is_final_pass or (available - decoded_to >= MIN_STEP_S):
                window = buffer[int(window_start * SAMPLE_RATE) :]
                decoded_to = available
                if len(window) and has_speech(window):
                    beam = 5 if is_final_pass else 1
                    text, rows = await loop.run_in_executor(None, decode, window, language, beam)
                    sequence += 1
                    partial = (committed + " " + text).strip()
                    await emit(
                        "transcript.final" if is_final_pass else "transcript.partial",
                        text=partial,
                        sequence=sequence,
                        is_final=is_final_pass,
                    )
                    if not is_final_pass and (available - window_start) > MAX_WINDOW_S:
                        cutoff = (available - window_start) - COMMIT_MARGIN_S
                        commit_rows = [row for row in rows if row[1] <= cutoff]
                        if commit_rows and len(commit_rows) == len(rows):
                            commit_rows = rows[:-1]
                        if commit_rows:
                            committed = (committed + "".join(r[2] for r in commit_rows)).strip()
                            window_start += commit_rows[-1][1]
                elif is_final_pass:
                    sequence += 1
                    await emit("transcript.final", text=committed, sequence=sequence, is_final=True)
            if is_final_pass:
                await emit(
                    "session.completed",
                    chunks_received=len(chunks),
                    audio_seconds_received=round(available, 2),
                )
                await ws.close()
                return
            await asyncio.sleep(0.05)
    except Exception:
        # Research prototype: die quietly, leak nothing to the client.
        with contextlib.suppress(Exception):
            await ws.close(code=1011)
    finally:
        receiver_task.cancel()


if __name__ == "__main__":
    if not os.environ.get("M52_WS_TOKEN"):
        sys.exit("refusing to start without M52_WS_TOKEN (no unauthenticated audio endpoints)")
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8794
    model()  # load + warm before accepting sessions
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
