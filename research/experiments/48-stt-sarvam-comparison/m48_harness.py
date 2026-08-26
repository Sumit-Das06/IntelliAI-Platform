# M48 — reproducible head-to-head harness with pluggable system
# adapters. IntelliAI runs today; the Sarvam adapter is a stub that
# refuses with BLOCKED - CREDENTIALS REQUIRED until legitimate API
# access exists (no fabrication, no auth bypass — the stub is the
# honest placeholder the rerun plugs into).
#
# Usage (from the repo root):
#   uv run --package intelliai-evaluation python \
#     research/experiments/48-stt-sarvam-comparison/m48_harness.py \
#     --clips <dir with audio+refs> --out results.json \
#     [--systems intelliai,sarvam] [--api-key-file <intelliai key file>]
#
# Clip convention: for every audio file X.(wav|ogg|mp3) an optional
# reference transcript X-ref.txt beside it; clips without a reference
# are transcribed and recorded but not WER-scored.
import argparse
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, "ml/evaluation/src")
from intelliai_evaluation.wer import word_error_rate

AUDIO_SUFFIXES = (".wav", ".ogg", ".mp3", ".m4a", ".webm")


class BlockedError(RuntimeError):
    """A system that cannot legitimately run yet."""


class IntelliAIAdapter:
    """The production gateway — measurable today."""

    name = "intelliai-stt"

    def __init__(self, base_url: str, api_key: str) -> None:
        self._client = httpx.Client(timeout=600.0)
        self._base = base_url
        self._headers = {
            "Authorization": "Bearer " + api_key,
            "X-IntelliAI-Client": "research-m48",
            # Research traffic never contributes to data collection.
            "X-IntelliAI-Contribution": "off",
        }

    def transcribe(self, path: Path, language: str = "en") -> dict:
        t0 = time.perf_counter()
        response = self._client.post(
            self._base + "/v1/audio/transcriptions",
            headers=self._headers,
            files={"file": (path.name, path.read_bytes())},
            data={"model": "intelliai-stt", "language": language},
        )
        wall = time.perf_counter() - t0
        response.raise_for_status()
        return {"text": response.json()["text"], "wall_s": round(wall, 3)}


class SarvamAdapter:
    """PLACEHOLDER — Sarvam API credentials are not available.

    When legitimate access exists, implement `transcribe` against
    Sarvam's documented STT endpoint with an api key from their
    dashboard, record model id + settings into the result dict, and
    the rest of this harness reruns unchanged. Until then every call
    refuses loudly instead of fabricating numbers.
    """

    name = "sarvam"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    def transcribe(self, path: Path, language: str = "en") -> dict:
        raise BlockedError("BLOCKED - CREDENTIALS REQUIRED (Sarvam API key not available)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clips", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--systems", default="intelliai,sarvam")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--api-key-file", default=None)
    parser.add_argument("--language", default="en")
    args = parser.parse_args()

    adapters = []
    for name in args.systems.split(","):
        if name.strip() == "intelliai":
            key = Path(args.api_key_file).read_text().strip() if args.api_key_file else ""
            adapters.append(IntelliAIAdapter(args.base_url, key))
        elif name.strip() == "sarvam":
            adapters.append(SarvamAdapter())

    clips = sorted(
        p
        for p in Path(args.clips).iterdir()
        if p.suffix.lower() in AUDIO_SUFFIXES and not p.stem.endswith("-ref")
    )
    results: dict = {"clips": [str(c.name) for c in clips], "systems": {}}
    for adapter in adapters:
        rows = []
        for clip in clips:
            ref_path = clip.with_name(clip.stem + "-ref.txt")
            try:
                got = adapter.transcribe(clip, language=args.language)
                row = {"clip": clip.name, **got}
                if ref_path.exists():
                    breakdown = word_error_rate(ref_path.read_text(encoding="utf-8"), got["text"])
                    row["wer"] = round(breakdown.wer, 4)
            except BlockedError as blocked:
                row = {"clip": clip.name, "status": str(blocked)}
            rows.append(row)
            print(adapter.name, row.get("clip"), row.get("wer", row.get("status", "")), flush=True)
        results["systems"][adapter.name] = rows

    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print("HARNESS-DONE", args.out)


if __name__ == "__main__":
    main()
