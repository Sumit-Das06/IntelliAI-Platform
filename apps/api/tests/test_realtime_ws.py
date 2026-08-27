"""M53 realtime WebSocket route: the gateway boundary laws.

Unit-level: the runtime bridge and the auth/collection seams are
patched, so these tests prove the ROUTE's own obligations — flag-off
refusal, auth-before-audio, language policy, event relay, one-sample
collection with contribution honored, and clean failure when the
runtime is unreachable. Real end-to-end sessions run in the M53
staging battery, not here.
"""

from __future__ import annotations

import json
from types import SimpleNamespace, TracebackType
from typing import Any, Self
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from intelliai_api.core.config import RuntimeSettings, Settings
from intelliai_api.main import create_app

MODULE = "intelliai_api.api.v1.audio.realtime"


def _settings(settings: Settings, *, realtime_url: str) -> Settings:
    return settings.model_copy(
        update={"runtimes": RuntimeSettings(_env_file=None, stt_realtime_ws_url=realtime_url)}
    )


def _auth_context() -> Any:
    return SimpleNamespace(organization_public_id="org_x", key_public_id="key_x")


class FakeRuntime:
    """A scripted runtime session: async context manager + duplex."""

    def __init__(self) -> None:
        self.received: list[Any] = []
        self._events: list[str] = []
        self._done = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    async def send(self, payload: Any) -> None:
        self.received.append(payload)
        if isinstance(payload, str):
            message = json.loads(payload)
            if message.get("event") == "start":
                self._events.append(json.dumps({"event": "session.started", "session_id": "rt1"}))
            elif message.get("event") == "end":
                self._events.extend(
                    [
                        json.dumps(
                            {
                                "event": "transcript.final",
                                "session_id": "rt1",
                                "sequence": 2,
                                "text": "hello world.",
                                "raw_text": "hello world",
                                "language": "en",
                                "duration_seconds": 1.0,
                                "is_final": True,
                            }
                        ),
                        json.dumps({"event": "session.completed", "session_id": "rt1"}),
                    ]
                )
                self._done = True
        else:
            self._events.append(
                json.dumps(
                    {
                        "event": "transcript.partial",
                        "session_id": "rt1",
                        "sequence": 1,
                        "text": "hello",
                        "is_final": False,
                    }
                )
            )

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> str:
        import asyncio

        while not self._events:
            if self._done:
                raise StopAsyncIteration
            await asyncio.sleep(0.01)
        return self._events.pop(0)


def test_flag_off_refuses_the_handshake(settings: Settings) -> None:
    app = create_app(_settings(settings, realtime_url=""))
    with (
        TestClient(app) as client,
        pytest.raises(WebSocketDisconnect) as excinfo,
        client.websocket_connect("/v1/audio/realtime"),
    ):
        pass
    assert excinfo.value.code == 4404


def test_auth_failure_refuses_before_any_audio(settings: Settings) -> None:
    app = create_app(_settings(settings, realtime_url="ws://runtime.invalid/v1/realtime"))
    with (
        patch(f"{MODULE}._authenticate", new=AsyncMock(return_value=None)),
        TestClient(app) as client,
        client.websocket_connect("/v1/audio/realtime") as ws,
    ):
        ws.send_text(json.dumps({"event": "auth", "api_key": "ik_bad", "language": "en"}))
        event = json.loads(ws.receive_text())
        assert event["event"] == "session.error"
        assert event["code"] == "invalid_api_key"
        with pytest.raises(WebSocketDisconnect) as excinfo:
            ws.receive_text()
        assert excinfo.value.code == 4401


def test_unsupported_language_is_refused(settings: Settings) -> None:
    app = create_app(_settings(settings, realtime_url="ws://runtime.invalid/v1/realtime"))
    with TestClient(app) as client, client.websocket_connect("/v1/audio/realtime") as ws:
        ws.send_text(json.dumps({"event": "auth", "api_key": "ik_x", "language": "fr"}))
        event = json.loads(ws.receive_text())
        assert event["code"] == "unsupported_language"


def test_session_relays_events_and_collects_exactly_one_sample(settings: Settings) -> None:
    app = create_app(_settings(settings, realtime_url="ws://runtime.invalid/v1/realtime"))
    runtime = FakeRuntime()
    collect = AsyncMock(return_value="smp_123")

    def fake_connect(url: str, **kwargs: Any) -> FakeRuntime:
        del url, kwargs
        return runtime

    with (
        patch(f"{MODULE}._authenticate", new=AsyncMock(return_value=_auth_context())),
        patch(f"{MODULE}._collect_final_sample", new=collect),
        patch(f"{MODULE}.websockets") as ws_module,
    ):
        ws_module.connect = fake_connect
        with TestClient(app) as client, client.websocket_connect("/v1/audio/realtime") as ws:
            ws.send_text(json.dumps({"event": "auth", "api_key": "ik_x", "language": "en"}))
            frame = b"\x00\x01" * 1600  # one 100 ms PCM16 frame
            ws.send_bytes(frame)
            events = [json.loads(ws.receive_text())]  # started
            events.append(json.loads(ws.receive_text()))  # partial
            ws.send_text(json.dumps({"event": "end"}))
            events.append(json.loads(ws.receive_text()))  # final
            events.append(json.loads(ws.receive_text()))  # completed
    names = [event["event"] for event in events]
    assert names == [
        "session.started",
        "transcript.partial",
        "transcript.final",
        "session.completed",
    ]
    assert events[-1]["sample_id"] == "smp_123"
    assert collect.await_count == 1
    assert collect.await_args is not None
    kwargs = collect.await_args.kwargs
    assert kwargs["pcm"] == frame  # the buffered session audio, byte-for-byte
    assert kwargs["contribute"] is True
    assert kwargs["final"]["text"] == "hello world."
    # The runtime saw the start message, the frame, and the end message.
    assert json.loads(runtime.received[0])["event"] == "start"
    assert frame in runtime.received


def test_contribution_off_is_honored(settings: Settings) -> None:
    app = create_app(_settings(settings, realtime_url="ws://runtime.invalid/v1/realtime"))
    collect = AsyncMock(return_value=None)
    with (
        patch(f"{MODULE}._authenticate", new=AsyncMock(return_value=_auth_context())),
        patch(f"{MODULE}._collect_final_sample", new=collect),
        patch(f"{MODULE}.websockets") as ws_module,
    ):
        ws_module.connect = lambda url, **kwargs: FakeRuntime()
        with TestClient(app) as client, client.websocket_connect("/v1/audio/realtime") as ws:
            ws.send_text(
                json.dumps(
                    {
                        "event": "auth",
                        "api_key": "ik_x",
                        "language": "en",
                        "contribution": "off",
                    }
                )
            )
            ws.send_text(json.dumps({"event": "end"}))
            for _ in range(3):
                json.loads(ws.receive_text())
    assert collect.await_args is not None
    assert collect.await_args.kwargs["contribute"] is False


def test_unreachable_runtime_is_an_explicit_safe_error(settings: Settings) -> None:
    app = create_app(_settings(settings, realtime_url="ws://127.0.0.1:1/v1/realtime"))
    with (
        patch(f"{MODULE}._authenticate", new=AsyncMock(return_value=_auth_context())),
        TestClient(app) as client,
        client.websocket_connect("/v1/audio/realtime") as ws,
    ):
        ws.send_text(json.dumps({"event": "auth", "api_key": "ik_x", "language": "en"}))
        event = json.loads(ws.receive_text())
        assert event["event"] == "session.error"
        assert event["code"] == "realtime_unavailable"
        assert "ws://" not in json.dumps(event)  # no topology leaks


def test_batch_transcriptions_route_is_untouched_by_the_flag(settings: Settings) -> None:
    # The additive-feature law: with realtime OFF the HTTP surface is
    # byte-identical — the batch route exists and the WS path 404s away.
    app = create_app(_settings(settings, realtime_url=""))
    with TestClient(app) as client:
        response = client.post("/v1/audio/transcriptions")
        assert response.status_code in (400, 401, 422)  # auth/validation, not 404
