"""Milestone 18 Phase 4: the Android keyboard's contract, replayed live.

HONEST SCOPE: no Android SDK, emulator, or device exists on this
machine, so this is NOT a device run and is never reported as one.
What it IS: byte-faithful replays of the requests the shipped keyboard
client builds (IntelliAIApiClient.kt — same multipart fields, same
filename, same headers, same correction payload) against the REAL
staging gateway, with the responses checked against the exact parsing
contract `interpret()` applies (error.type is the contract; `text`
must be a non-blank JSON field; the sample id arrives in the
X-IntelliAI-Sample header). Every branch the APK would take for these
scenarios is exercised against live Qwen-served Hindi.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import json
import os
from pathlib import Path
from typing import Any

import httpx

LEAK_MARKERS = ("qwen", "llama", "gguf", "ggml", "ctranslate", "faster")


def keyboard_request(
    client: httpx.Client,
    wav: bytes,
    *,
    key: str | None,
    language: str | None,
    contribute: bool = True,
) -> httpx.Response:
    """EXACTLY what IntelliAIApiClient.transcribe() sends."""
    headers = {"X-IntelliAI-Client": "keyboard/1.0"}
    if key is not None:
        headers["Authorization"] = f"Bearer {key}"
    if not contribute:
        headers["X-IntelliAI-Contribution"] = "off"
    data = {"model": "intelliai-stt"}
    if language is not None:
        data["language"] = language
    return client.post(
        "/v1/audio/transcriptions",
        headers=headers,
        files={"file": ("dictation.wav", wav, "audio/wav")},
        data=data,
    )


def keyboard_parse(response: httpx.Response) -> dict[str, Any]:
    """EXACTLY the outcome IntelliAIApiClient.interpret() would produce."""
    body = response.text
    if 200 <= response.status_code < 300:
        text = ""
        with contextlib.suppress(ValueError):
            text = json.loads(body).get("text", "")
        if not text.strip():
            return {"outcome": "NO_SPEECH"}
        return {
            "outcome": "SUCCESS",
            "inserted_text_preview": text[:60],
            "sample_id": response.headers.get("X-IntelliAI-Sample"),
        }
    error: dict[str, Any] = {}
    with contextlib.suppress(ValueError):
        error = json.loads(body).get("error", {})
    kind_by_type = {
        "authentication_error": "BAD_API_KEY",
        "quota_exceeded_error": "QUOTA",
        "rate_limit_error": "RATE_LIMITED",
        "service_unavailable_error": "UNAVAILABLE",
        "invalid_request_error": "REJECTED",
        "resource_not_found_error": "REJECTED",
    }
    outcome = kind_by_type.get(str(error.get("type", "")))
    if outcome is None:
        outcome = "SERVER" if response.status_code >= 500 else "REJECTED"
    row: dict[str, Any] = {"outcome": outcome, "error_type": error.get("type")}
    if outcome == "REJECTED":
        row["surfaced_message"] = error.get("message")
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--audio-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    key = os.environ["INTELLIAI_M18_KEY"]
    hi = (args.audio_dir / "hi-short.wav").read_bytes()
    long_clip = (args.audio_dir / "hi-121s.wav").read_bytes()

    record: dict[str, Any] = {
        "replay": "18-android-contract",
        "NOT_A_DEVICE_RUN": (
            "no Android SDK/emulator/device available on this machine; byte-faithful "
            "client-contract replays against the live staging gateway"
        ),
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
    }
    with httpx.Client(base_url=args.base_url, timeout=300.0) as client:
        # Hindi dictation, contribution ON — the keyboard's happy path.
        response = keyboard_request(client, hi, key=key, language="hi")
        parsed = keyboard_parse(response)
        record["hindi_dictation_on"] = {
            **parsed,
            "leaks": [m for m in LEAK_MARKERS if m in response.text.lower()],
        }
        sample_id = parsed.get("sample_id")

        # The keyboard's correction call, verbatim payload.
        if sample_id:
            corrected = client.post(
                f"/v1/audio/transcriptions/{sample_id}/correction",
                headers={
                    "Authorization": f"Bearer {key}",
                    "X-IntelliAI-Client": "keyboard/1.0",
                    # okhttp's toRequestBody("application/json") sets this;
                    # the first replay omitted it and earned a 400 — the
                    # gateway correctly requires the declared media type.
                    "Content-Type": "application/json",
                },
                content=json.dumps({"corrected_text": "कीबोर्ड सुधार परीक्षण"}),
            )
            record["correction"] = {"status": corrected.status_code}

        # Contribution OFF: transcript yes, sample no.
        response = keyboard_request(client, hi, key=key, language="hi", contribute=False)
        parsed = keyboard_parse(response)
        record["hindi_dictation_off"] = {**parsed, "no_sample": parsed.get("sample_id") is None}

        # Auto mode (no language part): the keyboard sends nothing.
        response = keyboard_request(client, hi, key=key, language=None)
        record["auto_mode_default_route"] = keyboard_parse(response)

        # Key states the keyboard distinguishes.
        record["missing_key"] = keyboard_parse(
            keyboard_request(client, hi, key=None, language="hi")
        )
        record["bad_key"] = keyboard_parse(
            keyboard_request(client, hi, key="ik_live_wrongwrongwrong", language="hi")
        )

        # 121 s: the keyboard surfaces invalid_request_error messages.
        response = keyboard_request(client, long_clip, key=key, language="hi")
        parsed = keyboard_parse(response)
        record["ceiling_121s"] = {
            **parsed,
            "message_useful": "120 seconds" in str(parsed.get("surfaced_message", "")),
            "leaks": [m for m in LEAK_MARKERS if m in response.text.lower()],
        }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
