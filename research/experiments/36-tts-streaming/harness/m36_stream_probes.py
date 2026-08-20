"""M36 quality regression capture: the M33 probe set through stream=true.

Saves each streamed response as a proper WAV (real sizes, from the
delivered PCM) so the standard roundtrip judge compares stream-mode
audio against the M35 whole-body result on identical texts.
"""

from __future__ import annotations

import argparse
import json
import struct
import time
from pathlib import Path

import httpx


def wav_from_pcm(pcm: bytes, sample_rate: int = 24_000) -> bytes:
    header = b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
    header += b"data" + struct.pack("<I", len(pcm))
    return header + pcm


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gateway-url", default="http://localhost:8000")
    parser.add_argument("--api-key-file", required=True)
    parser.add_argument("--probes", required=True)
    parser.add_argument("--audio-dir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    key = Path(args.api_key_file).read_text(encoding="utf-8").strip()
    probes = [
        case
        for case in json.loads(Path(args.probes).read_text(encoding="utf-8"))["cases"]
        if case["language"] == "en"
    ]
    audio_dir = Path(args.audio_dir)
    audio_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    with httpx.Client(base_url=args.gateway_url, timeout=300.0) as client:
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        for case in probes:
            started = time.perf_counter()
            received = bytearray()
            ttfa_ms = None
            with client.stream(
                "POST",
                "/v1/audio/speech",
                json={
                    "model": "intelliai-tts",
                    "input": case["text"],
                    "voice": "english-female",
                    "stream": True,
                },
                headers=headers,
            ) as response:
                if response.status_code != 200:
                    rows.append({"id": case["id"], "error": response.status_code})
                    continue
                for chunk in response.iter_bytes():
                    received.extend(chunk)
                    if ttfa_ms is None and len(received) > 44:
                        ttfa_ms = round((time.perf_counter() - started) * 1000.0, 1)
            pcm = bytes(received[44:])
            (audio_dir / f"{case['id']}.wav").write_bytes(wav_from_pcm(pcm))
            rows.append(
                {
                    "id": case["id"],
                    "ttfa_ms": ttfa_ms,
                    "total_ms": round((time.perf_counter() - started) * 1000.0, 1),
                    "audio_seconds": round(len(pcm) / 2 / 24_000, 3),
                }
            )
            print(f"  {case['id']:<24} ttfa {ttfa_ms} ms")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {"experiment": "36-tts-streaming", "instrument": "m36_stream_probes.py", "rows": rows},
            indent=2,
        ),
        encoding="utf-8",
    )
    failures = [row for row in rows if "error" in row]
    print(f"captured {len(rows) - len(failures)}/{len(rows)} streamed probes")


if __name__ == "__main__":
    main()
