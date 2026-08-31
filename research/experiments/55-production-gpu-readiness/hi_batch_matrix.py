"""M55 Phases 12-13 — Hindi BATCH through GPU serving, via the REAL
public gateway route (the path customers use).

    python hi_batch_matrix.py <out.json> <label>

n=5 per clip; measures word count, latency, and run-to-run determinism
(sha256 of the text). WER/CER vs ground truth where refs exist.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
import time
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "ml/evaluation/src"))
from intelliai_evaluation.accuracy import score  # noqa: E402
from intelliai_evaluation.normalization import UNICODE_GENERIC_V2  # noqa: E402

SCRATCH = Path(
    r"C:\Users\VIKASH~1\AppData\Local\Temp\claude"
    r"\d--Sumit-Projects-IntelliAI-Platform"
    r"\67762b73-e6aa-43b8-a730-264d0d432d4f\scratchpad"
)
KEY = (SCRATCH / "m24-key.txt").read_text(encoding="utf-8").strip()
CLIPS = SCRATCH / "m52hclips"


def transcribe(path: Path) -> tuple[str, float]:
    boundary = uuid.uuid4().hex
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\n'
        "intelliai-stt\r\n"
        f'--{boundary}\r\nContent-Disposition: form-data; name="language"\r\n\r\nhi\r\n'
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
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=900) as response:  # noqa: S310
        text = str(json.loads(response.read())["text"])
    return text, round(time.perf_counter() - started, 2)


def main() -> None:
    out_name, label = sys.argv[1], sys.argv[2]
    clips = {
        "real30s_multi": (CLIPS / "real30s.wav", CLIPS / "real30s.ref.txt"),
        "real60s_multi": (CLIPS / "real60s.wav", None),
        "short_single": (SCRATCH / "m52clips" / "16k_hindi_short.wav", None),
        "real2min_multi": (CLIPS / "real2min.wav", CLIPS / "real2min.ref.txt"),
    }
    result: dict = {"label": label}
    for name, (path, ref_path) in clips.items():
        runs = []
        for _ in range(5):
            text, latency = transcribe(path)
            runs.append(
                {
                    "words": len(text.split()),
                    "latency_s": latency,
                    "sha16": hashlib.sha256(text.encode()).hexdigest()[:16],
                }
            )
        words = [r["words"] for r in runs]
        shas = {r["sha16"] for r in runs}
        entry: dict = {
            "runs": runs,
            "words_spread": f"{min(words)}-{max(words)}",
            "latency_p50_s": round(statistics.median(r["latency_s"] for r in runs), 2),
            "deterministic": len(shas) == 1,
            "stable": max(words) - min(words) <= max(2, round(0.05 * max(words))),
        }
        if ref_path is not None and ref_path.exists():
            reference = ref_path.read_text(encoding="utf-8")
            text, _ = transcribe(path)
            scores = score(reference, text, UNICODE_GENERIC_V2)
            entry["wer_vs_truth"] = round(scores.wer, 4)
            entry["cer_vs_truth"] = round(scores.cer, 4)
        result[name] = entry
        print(name, json.dumps({k: v for k, v in entry.items() if k != "runs"}, ensure_ascii=False))
    EVIDENCE.mkdir(exist_ok=True)
    (EVIDENCE / out_name).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(out_name, "written")


if __name__ == "__main__":
    main()
