"""M50 service-level E2E: real audio through the real runtime service.

POSTs an audio file to a locally running stt-runtime instance
(uvicorn, whisper slot) and records the full response envelope —
the exact bytes the gateway would consume.

    python m50_service_e2e.py <port> <audio_path> <language> <out_name>
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"


def post_multipart(url: str, audio: Path, params: dict) -> tuple[dict, float]:
    if not url.startswith("http://127.0.0.1:"):  # loopback-only harness
        msg = f"E2E harness only talks to loopback, got {url!r}"
        raise ValueError(msg)
    boundary = uuid.uuid4().hex
    body = b""
    body += (
        f'--{boundary}\r\nContent-Disposition: form-data; name="params"\r\n\r\n'
        f"{json.dumps(params)}\r\n"
    ).encode()
    body += (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{audio.name}"\r\nContent-Type: application/octet-stream\r\n\r\n'
    ).encode()
    body += audio.read_bytes() + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    request = urllib.request.Request(  # noqa: S310 — loopback http only, guarded above
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=600) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    elapsed = time.perf_counter() - started
    return payload, elapsed


def main() -> None:
    port, audio_path, language, out_name = sys.argv[1:5]
    audio = Path(audio_path)
    envelope, elapsed = post_multipart(
        f"http://127.0.0.1:{port}/v1/transcribe", audio, {"language": language}
    )
    EVIDENCE.mkdir(exist_ok=True)
    record = {
        "audio_file": audio.name,
        "language": language,
        "wall_seconds": round(elapsed, 2),
        "envelope": envelope,
    }
    out = EVIDENCE / out_name
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    output = envelope.get("output", {})
    print(f"wrote {out.name}  wall={elapsed:.2f}s")
    print("TEXT:", output.get("text", "")[:300])
    print("RAW :", (output.get("raw_text") or "")[:300])
    print("STAGES:", envelope.get("timing", {}).get("stages", {}))


if __name__ == "__main__":
    main()
