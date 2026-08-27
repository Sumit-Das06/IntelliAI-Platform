"""Realtime STT over WebSocket (Milestone 53) — the PUBLIC boundary.

    Browser ── wss /v1/audio/realtime ── THIS route ── ws ── stt-runtime
                                                              session

The gateway owns exactly what it owns for batch: authentication,
consent/collection, and topology. The runtime owns inference. This
route therefore does three things and nothing else:

1. **Authenticates BEFORE any audio is accepted.** The first client
   message must be ``{"event": "auth", "api_key": "ik_…", "language":
   "en"}``; the key is verified through the same AuthService as every
   HTTP request. Wrong or missing key → one safe error event, close.
   The key is never logged; audio and transcripts are never logged.

2. **Pipes.** Binary PCM16@16k frames go up unchanged; session events
   come down unchanged. Partials remain EPHEMERAL — nothing about them
   is persisted anywhere.

3. **Collects ONE final sample** — batch-equivalent semantics: after
   ``transcript.final``, the buffered session audio (WAV-wrapped) and
   the final transcript go through the EXISTING DataCollectionService
   (same consent ceiling, same per-request opt-out via the auth
   message's ``"contribution": "off"``), yielding at most one stored
   sample per session, exactly like one batch upload. Its public id
   rides on ``session.completed`` as ``sample_id`` so Correction works
   unchanged.

Feature flag: ``INTELLIAI_RUNTIMES_STT_REALTIME_WS_URL`` empty (the
default everywhere, pinned empty in production) disables this route —
the handshake is refused before ``accept``, indistinguishable from the
feature not existing.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import time
import wave
from typing import TYPE_CHECKING, Any, Final

import structlog
import websockets
from fastapi import APIRouter, WebSocket

from intelliai_api.core.config import Settings
from intelliai_api.db.models import ClientSource
from intelliai_api.services.auth import AuthService
from intelliai_api.services.collection import DataCollectionService
from intelliai_api.services.transcription import TranscriptionOutcome
from intelliai_runtime_contract import TranscriptionResult

if TYPE_CHECKING:
    from intelliai_api.services.auth import AuthContext

logger = structlog.get_logger(__name__)
router = APIRouter()

SAMPLE_RATE: Final = 16_000
_AUTH_TIMEOUT_SECONDS: Final = 10.0
_MAX_FRAME_BYTES: Final = 64 * 1024
#: Hard ceiling on buffered session audio for collection (30 min PCM16).
_MAX_BUFFER_BYTES: Final = 30 * 60 * SAMPLE_RATE * 2

_SUPPORTED_LANGUAGES: Final = frozenset({"en", "en-us", "en-in", "hi", "hi-in"})

CLOSE_UNAVAILABLE: Final = 4404
CLOSE_UNAUTHENTICATED: Final = 4401
CLOSE_BAD_REQUEST: Final = 4400


def _wav_bytes(pcm: bytes) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        out.writeframes(pcm)
    return buffer.getvalue()


async def _authenticate(websocket: WebSocket, credential: str) -> AuthContext | None:
    """The SAME verification pipeline as HTTP, on a WS-carried credential."""
    settings: Settings = websocket.app.state.settings
    factory = websocket.app.state.session_factory
    async with factory() as session:
        service = AuthService(session, pepper=settings.auth.key_pepper.get_secret_value())
        try:
            return await service.authenticate(credential)
        except Exception:
            return None


async def _collect_final_sample(
    websocket: WebSocket,
    *,
    auth: AuthContext,
    pcm: bytes,
    final: dict[str, Any],
    language: str,
    contribute: bool,
    started: float,
) -> str | None:
    """One consented sample per session — the batch contract, verbatim.

    Collection can never fail the session (same law as batch: it rides
    after success and returns None on any refusal)."""
    text = str(final.get("text", ""))
    if not text or not pcm:
        return None
    raw_text = final.get("raw_text")
    raw = str(raw_text) if raw_text else text
    duration = float(final.get("duration_seconds", len(pcm) / (SAMPLE_RATE * 2)))
    result = TranscriptionResult(
        text=text,
        language=str(final.get("language", language)).split("-")[0].casefold() or "und",
        duration_seconds=max(duration, 0.0),
        raw_text=None if raw == text else raw,
    )
    outcome = TranscriptionOutcome(
        result=result, public_model_id="intelliai-stt", audio_seconds=result.duration_seconds
    )
    settings: Settings = websocket.app.state.settings
    factory = websocket.app.state.session_factory
    try:
        async with factory() as session:
            collection = DataCollectionService(
                session,
                websocket.app.state.object_storage,
                enabled=settings.collection.enabled,
            )
            sample_id = await collection.collect(
                auth=auth,
                audio=_wav_bytes(pcm),
                content_type="audio/wav",
                filename="realtime-session.wav",
                requested_language=language,
                idempotency_key=None,
                outcome=outcome,
                request_started=started,
                client_source=ClientSource.WEB,
                client_version=None,
                contribute=contribute,
            )
            await session.commit()
            return sample_id
    except Exception as exc:  # never fails the session
        logger.warning("realtime_collection_failed", reason=type(exc).__name__)
        return None


@router.websocket("/v1/audio/realtime")
async def realtime(websocket: WebSocket) -> None:
    settings: Settings = websocket.app.state.settings
    runtime_url = settings.runtimes.stt_realtime_ws_url.strip()
    if not runtime_url:
        # Flag OFF: refuse the handshake outright — no accept, no audio.
        await websocket.close(code=CLOSE_UNAVAILABLE)
        return

    await websocket.accept()
    try:
        first = json.loads(
            await asyncio.wait_for(websocket.receive_text(), timeout=_AUTH_TIMEOUT_SECONDS)
        )
    except Exception:
        await websocket.close(code=CLOSE_BAD_REQUEST)
        return
    if first.get("event") != "auth":
        await websocket.close(code=CLOSE_BAD_REQUEST)
        return
    language = str(first.get("language", "")).strip()
    contribute = str(first.get("contribution", "on")).strip().lower() != "off"
    credential = str(first.get("api_key", ""))
    if language.casefold() not in _SUPPORTED_LANGUAGES:
        await websocket.send_text(
            json.dumps(
                {
                    "event": "session.error",
                    "code": "unsupported_language",
                    "message": "Realtime transcription supports English and Hindi.",
                }
            )
        )
        await websocket.close(code=CLOSE_BAD_REQUEST)
        return
    auth = await _authenticate(websocket, credential)
    if auth is None:
        await websocket.send_text(
            json.dumps(
                {
                    "event": "session.error",
                    "code": "invalid_api_key",
                    "message": "The API key is missing, malformed, or not active.",
                }
            )
        )
        await websocket.close(code=CLOSE_UNAUTHENTICATED)
        return
    structlog.contextvars.bind_contextvars(
        organization_id=auth.organization_public_id, key_id=auth.key_public_id
    )

    started = time.time()
    pcm = bytearray()
    final_event: dict[str, Any] | None = None
    try:
        async with websockets.connect(runtime_url, max_size=None, open_timeout=10) as runtime:
            await runtime.send(json.dumps({"event": "start", "language": language}))

            async def uplink() -> None:
                """client → runtime; buffers audio for the ONE final sample."""
                while True:
                    message = await websocket.receive()
                    if message.get("type") == "websocket.disconnect":
                        return
                    if (data := message.get("bytes")) is not None:
                        if len(data) > _MAX_FRAME_BYTES:
                            continue  # oversized frames are dropped, bounded
                        if len(pcm) + len(data) <= _MAX_BUFFER_BYTES:
                            pcm.extend(data)
                        await runtime.send(data)
                    elif (text := message.get("text")) is not None:
                        with contextlib.suppress(json.JSONDecodeError):
                            if json.loads(text).get("event") == "end":
                                await runtime.send(json.dumps({"event": "end"}))

            async def downlink() -> None:
                """runtime → client; intercepts final/completed for collection."""
                nonlocal final_event
                async for raw in runtime:
                    if isinstance(raw, bytes):
                        continue
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if event.get("event") == "transcript.final":
                        final_event = event
                    if event.get("event") == "session.completed" and final_event is not None:
                        logger.info("realtime_completed_intercepted")
                        sample_id = await _collect_final_sample(
                            websocket,
                            auth=auth,
                            pcm=bytes(pcm),
                            final=final_event,
                            language=language,
                            contribute=contribute,
                            started=started,
                        )
                        if sample_id is not None:
                            event = {**event, "sample_id": sample_id}
                    await websocket.send_text(json.dumps(event, ensure_ascii=False))
                    if event.get("event") == "session.completed":
                        logger.info("realtime_completed_relayed")
                        return  # the session is over; close both legs cleanly

            uplink_task = asyncio.create_task(uplink())
            downlink_task = asyncio.create_task(downlink())
            done, pending = await asyncio.wait(
                {uplink_task, downlink_task}, return_when=asyncio.FIRST_COMPLETED
            )
            if downlink_task in pending:
                # The uplink ended first (client stopped sending, or the
                # runtime stopped reading after `end`). The FINAL and
                # COMPLETED events are still in flight - give the downlink
                # a bounded window to drain them; never cancel a final out
                # from under the user.
                with contextlib.suppress(TimeoutError, asyncio.TimeoutError):
                    await asyncio.wait_for(downlink_task, timeout=60.0)
            for task in pending:
                task.cancel()
            for task in done:
                with contextlib.suppress(Exception):
                    task.result()
    except Exception:
        # Runtime unreachable or a pipe failed: one safe event, close.
        logger.warning("realtime_session_bridge_failed")
        with contextlib.suppress(Exception):
            await websocket.send_text(
                json.dumps(
                    {
                        "event": "session.error",
                        "code": "realtime_unavailable",
                        "message": "Realtime transcription is temporarily unavailable.",
                    }
                )
            )
    finally:
        structlog.contextvars.clear_contextvars()
        with contextlib.suppress(Exception):
            await websocket.close()
