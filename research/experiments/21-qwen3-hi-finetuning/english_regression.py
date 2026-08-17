"""M21 Phase 12 + 15 (probes): did Hindi SFT damage anything else?

The 15E regression discipline, HF-side, base vs the selected
checkpoint: the two pinned JFK English clips (WER against the seed
reference), silence and tone probes generated in memory (the correct
transcription of silence is NOTHING), and one Hindi clip as a
language-id spot check. Not an English benchmark — a tripwire.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import time
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np

from intelliai_evaluation.accuracy import score
from intelliai_evaluation.normalization import profile_for
from intelliai_training.qwen_trainer import load_wrapper

JFK_REFERENCE = (
    "And so, my fellow Americans: ask not what your country can do for you; "
    "ask what you can do for your country."
)
CLIPS = (
    (
        "jfk-flac",
        "https://github.com/openai/whisper/raw/v20250625/tests/jfk.flac",
        "63a4b1e4c1dc655ac70961ffbf518acd249df237e5a0152faae9a4a836949715",
    ),
    (
        "jfk-wav",
        "https://github.com/ggml-org/whisper.cpp/raw/v1.9.1/samples/jfk.wav",
        "59dfb9a4acb36fe2a2affc14bacbee2920ff435cb13cc314a08c13f66ba7860e",
    ),
)
HINDI_SPOT = "indicvoices/hindi/valid/indicvoices-hindi-valid-0-000034.flac"


def fetch(url: str, sha256: str, target: Path) -> Path:
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == sha256:
        return target
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310
                data = response.read()
            break
        except OSError:
            if attempt == 4:
                raise
            time.sleep(20)
    digest = hashlib.sha256(data).hexdigest()
    if digest != sha256:
        msg = f"{url}: sha {digest} != pinned {sha256}"
        raise ValueError(msg)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target


def probe_set(model_dir: Path, work: Path, data_root: Path) -> dict[str, Any]:
    import torch

    wrapper = load_wrapper(model_dir, device_map="cuda:0")
    profile = profile_for("en")
    out: dict[str, Any] = {}

    for clip_id, url, sha in CLIPS:
        path = fetch(url, sha, work / Path(url).name)
        result = wrapper.transcribe(str(path))
        text = str(result[0].text) if result else ""
        out[clip_id] = {
            "wer": round(score(JFK_REFERENCE, text, profile).wer, 4),
            "text_head": text[:80],
        }

    silence = np.zeros(16000 * 10, dtype=np.float32)
    tone = (0.3 * np.sin(2 * np.pi * 440 * np.arange(16000 * 5) / 16000)).astype(np.float32)
    for name, wave in (("silence-10s", silence), ("tone-440hz-5s", tone)):
        result = wrapper.transcribe((wave, 16000))
        text = str(result[0].text) if result else ""
        out[name] = {"empty": not text.strip(), "text_head": text[:60]}

    result = wrapper.transcribe(str(data_root / HINDI_SPOT))
    text = str(result[0].text) if result else ""
    devanagari = any("ऀ" <= ch <= "ॿ" for ch in text)
    out["hindi-language-id"] = {"devanagari": devanagari, "text_head": text[:60]}

    del wrapper
    torch.cuda.empty_cache()
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=Path("ml/datasets/data"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    payload = {
        "experiment": "21-qwen3-hi-finetuning",
        "phase": "english-regression + probes (HF-side tripwire, not a benchmark)",
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "base": probe_set(args.base, args.work, args.data_root),
        "candidate": probe_set(args.candidate, args.work, args.data_root),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
