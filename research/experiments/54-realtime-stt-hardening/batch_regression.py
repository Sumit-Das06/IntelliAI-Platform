"""M54 Phase 14 — batch regression: the API's batch path must be
byte-identical run-to-run and untouched by realtime hardening.

    python batch_regression.py

Runs each clip TWICE through the real gateway and records sha256 of the
returned text. EN boss30 exercises punctuation_en; HI short exercises
the Hindi stage; EN 2min exercises long-audio chunking.
(The long multi-speaker HI instability is the SEPARATE Phase 15 finding
— stability there is measured in service-anomaly.json, not here.)
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"
SCRATCH = Path(
    r"C:\Users\VIKASH~1\AppData\Local\Temp\claude"
    r"\d--Sumit-Projects-IntelliAI-Platform"
    r"\67762b73-e6aa-43b8-a730-264d0d432d4f\scratchpad"
)
KEY = (SCRATCH / "m24-key.txt").read_text(encoding="utf-8").strip()


def transcribe(path: Path, language: str) -> str:
    boundary = uuid.uuid4().hex
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\n'
        "intelliai-stt\r\n"
        f'--{boundary}\r\nContent-Disposition: form-data; name="language"\r\n\r\n'
        f"{language}\r\n"
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
    with urllib.request.urlopen(request, timeout=900) as response:  # noqa: S310
        return str(json.loads(response.read())["text"])


def main() -> None:
    clips = (
        ("en_boss30_punctuated", SCRATCH / "m52clips" / "boss30.wav", "en"),
        ("hi_short", SCRATCH / "m52clips" / "16k_hindi_short.wav", "hi"),
        ("en_2min_long_audio", SCRATCH / "m51long" / "2min.wav", "en"),
    )
    result: dict = {}
    for name, path, language in clips:
        first = transcribe(path, language)
        second = transcribe(path, language)
        sha1 = hashlib.sha256(first.encode("utf-8")).hexdigest()
        sha2 = hashlib.sha256(second.encode("utf-8")).hexdigest()
        result[name] = {
            "sha256_run1": sha1,
            "sha256_run2": sha2,
            "byte_identical": sha1 == sha2,
            "words": len(first.split()),
        }
        print(name, "identical" if sha1 == sha2 else "DIFFERENT", len(first.split()), "words")
    EVIDENCE.mkdir(exist_ok=True)
    (EVIDENCE / "batch-regression.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("batch-regression.json written")


if __name__ == "__main__":
    main()
