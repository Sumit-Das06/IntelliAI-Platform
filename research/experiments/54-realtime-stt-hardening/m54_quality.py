"""M54 Phase 17 — quality regression: baseline vs hardened finals.

Hindi finals score against IndicVoices GROUND TRUTH (the frozen M52H
ruler); English boss30 finals score against the batch pipeline's text
for the same clip. Both prefixes run through the SAME rulers so the
comparison is exact.

    python m54_quality.py
"""

from __future__ import annotations

import json
import sys
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EVIDENCE = HERE / "evidence"
sys.path.insert(0, str(ROOT / "ml/evaluation/src"))

from intelliai_evaluation.accuracy import score  # noqa: E402
from intelliai_evaluation.normalization import UNICODE_GENERIC_V2  # noqa: E402
from intelliai_evaluation.wer import word_error_rate  # noqa: E402

H = Path(
    r"C:\Users\VIKASH~1\AppData\Local\Temp\claude"
    r"\d--Sumit-Projects-IntelliAI-Platform"
    r"\67762b73-e6aa-43b8-a730-264d0d432d4f\scratchpad\m52hclips"
)
KEY = (H.parent / "m24-key.txt").read_text(encoding="utf-8").strip()


def load(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def batch_text(path: Path, language: str) -> str:
    """The batch pipeline's own text for a clip, via the real gateway."""
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
    result: dict = {"rulers": "unicode_generic@v2 + frozen wer.py (unchanged)"}

    # ── Hindi vs ground truth, both prefixes ─────────────────────────────
    hindi: dict = {}
    for clip, session_suffix in (
        ("real30s", "hi-real30s-r1.json"),
        ("real2min", "hi-2min.json"),
        ("real5min", "hi-5min.json"),
        ("real10min", "hi-10min.json"),
    ):
        reference = (H / f"{clip}.ref.txt").read_text(encoding="utf-8")
        row: dict = {"ref_words": len(reference.split())}
        for prefix in ("baseline", "hardened"):
            name = f"{prefix}-{session_suffix}"
            if not (EVIDENCE / name).exists():
                continue
            final = str(load(name).get("final_text") or "")
            scores = score(reference, final, UNICODE_GENERIC_V2)
            row[prefix] = {
                "wer": round(scores.wer, 4),
                "cer": round(scores.cer, 4),
                "words": len(final.split()),
            }
        hindi[clip] = row
        print(clip, json.dumps(row, ensure_ascii=False))
    result["hindi_vs_ground_truth"] = hindi

    # ── English boss30 vs the batch pipeline ─────────────────────────────
    batch = batch_text(H.parent / "m52clips" / "boss30.wav", "en")
    english: dict = {"reference": "batch pipeline text, same stack, same clip"}
    for prefix in ("baseline", "hardened"):
        finals = []
        for i in (1, 2, 3, 4, 5):
            name = f"{prefix}-en-boss30-r{i}.json"
            if (EVIDENCE / name).exists():
                finals.append(str(load(name).get("final_text") or ""))
        if finals:
            wers = [round(word_error_rate(batch, final).wer, 4) for final in finals]
            english[prefix] = {"runs": len(finals), "wer_vs_batch": wers}
    result["english_boss30"] = english
    print(
        "english",
        json.dumps(english.get("baseline"), ensure_ascii=False),
        json.dumps(english.get("hardened"), ensure_ascii=False),
    )

    (EVIDENCE / "quality.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("quality.json written")


if __name__ == "__main__":
    main()
