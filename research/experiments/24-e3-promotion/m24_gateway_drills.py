"""M24 Phases 6-8: the REAL product path to E3, drilled end to end.

Every request goes through POST /v1/audio/transcriptions on a REAL
gateway process (staging registry profile: hi -> qwen3-asr-0.6b-hi-ft-e3,
everything else -> whisper-small) backed by the REAL multi-slot runtime
executing the REAL pinned models. The API key arrives via
INTELLIAI_M24_KEY and never enters this file or its output; response
bodies are scanned for internal-name leaks before being summarized.

Beyond the M18 drill: the ceiling is the M19 600 s law (300 s and
600 s CHUNK internally and stay one customer request; 602 s refuses
naming the limit), verbose_json on long audio must satisfy the
segment space-join law with real offsets, usage deltas are asserted
per long request (+300 s / +600 s; refusals bill zero), and the
malformed/empty/tiny/unsupported-language inputs from the milestone's
Phase 5 list run through the same gateway.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx

LEAK_MARKERS = ("qwen", "llama", "gguf", "ggml", "whisper", "ctranslate", "faster", "hi-ft-e3")
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def leak_scan(text: str) -> list[str]:
    lowered = text.lower()
    return [marker for marker in LEAK_MARKERS if marker in lowered]


class Drills:
    def __init__(self, base_url: str, key: str, audio_dir: Path) -> None:
        self.client = httpx.Client(base_url=base_url, timeout=600.0)
        self.key = key
        self.audio = audio_dir
        self.rows: dict[str, Any] = {}

    def post(
        self,
        clip: str,
        *,
        auth: str | None = "valid",
        language: str | None = None,
        response_format: str | None = None,
        contribution: str | None = None,
    ) -> httpx.Response:
        headers: dict[str, str] = {"X-IntelliAI-Client": "m24-drill/1.0"}
        if auth == "valid":
            headers["Authorization"] = f"Bearer {self.key}"
        elif auth == "invalid":
            headers["Authorization"] = "Bearer ik_live_notARealKeyAtAll123456"
        if contribution is not None:
            headers["X-IntelliAI-Contribution"] = contribution
        data: dict[str, str] = {"model": "intelliai-stt"}
        if language is not None:
            data["language"] = language
        if response_format is not None:
            data["response_format"] = response_format
        payload = (self.audio / clip).read_bytes()
        started = time.perf_counter()
        response = self.client.post(
            "/v1/audio/transcriptions",
            headers=headers,
            files={"file": (clip, payload, "audio/wav")},
            data=data,
        )
        response.elapsed_wall = time.perf_counter() - started  # type: ignore[attr-defined]
        return response

    def summarize(self, name: str, response: httpx.Response, **extra: Any) -> None:
        row: dict[str, Any] = {
            "status": response.status_code,
            "wall_seconds": round(getattr(response, "elapsed_wall", 0.0), 2),
            "leaks": leak_scan(response.text),
        }
        row.update(extra)
        self.rows[name] = row

    def usage_total(self) -> float:
        response = self.client.get(
            "/v1/usage/summary", headers={"Authorization": f"Bearer {self.key}"}
        )
        response.raise_for_status()
        # The public summary reports speech MINUTES (2 decimals) — the
        # public surface never exposes raw quantities or artifact names.
        return float(response.json()["totals"]["speech_minutes"]) * 60.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--audio-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    key = os.environ["INTELLIAI_M24_KEY"]

    d = Drills(args.base_url, key, args.audio_dir)

    # ── Auth matrix (unchanged laws) ─────────────────────────────────
    d.summarize("auth_missing_key", d.post("hi-short.wav", auth=None, language="hi"))
    d.summarize("auth_invalid_key", d.post("hi-short.wav", auth="invalid", language="hi"))

    # ── Routing through the real models ──────────────────────────────
    r = d.post("hi-short.wav", language="hi")
    d.summarize(
        "hindi_explicit_to_e3",
        r,
        devanagari=bool(DEVANAGARI.search(r.json().get("text", ""))),
        text_preview=r.json().get("text", "")[:80],
    )
    r = d.post("hi-short.wav", language="hi-IN")
    d.summarize(
        "hindi_regional_tag", r, devanagari=bool(DEVANAGARI.search(r.json().get("text", "")))
    )
    r = d.post("en-jfk.wav", language="en")
    d.summarize(
        "english_stays_on_incumbent",
        r,
        ask_not=("ask not" in r.json().get("text", "").lower()),
    )
    # No declared language = the DEFAULT route (declaration-first law).
    r = d.post("hi-short.wav")
    d.summarize(
        "hindi_undeclared_default_route",
        r,
        devanagari=bool(DEVANAGARI.search(r.json().get("text", ""))),
    )
    # Unsupported language hint: no route -> default (incumbent) which
    # refuses the unknown code cleanly; never a 500, never a leak.
    r = d.post("hi-short.wav", language="xx")
    d.summarize("unsupported_language_hint", r, error_param=r.json().get("error", {}).get("param"))

    # ── verbose_json: short = one clean segment ──────────────────────
    r = d.post("hi-short.wav", language="hi", response_format="verbose_json")
    body = r.json()
    d.summarize(
        "verbose_json_short",
        r,
        segment_count=len(body.get("segments", [])),
        segment_keys=sorted(body.get("segments", [{}])[0]) if body.get("segments") else [],
        spans_full_clip=(
            bool(body.get("segments"))
            and body["segments"][0]["start"] == 0.0
            and abs(body["segments"][-1]["end"] - body.get("duration", 0)) < 0.01
        ),
    )

    # ── Collection + correction + contribution ───────────────────────
    r = d.post("hi-short.wav", language="hi")
    sample_id = r.headers.get("X-IntelliAI-Sample")
    d.summarize("collection_consented", r, sample_created=bool(sample_id))
    correction_row: dict[str, Any] = {"skipped": "no sample id"}
    if sample_id:
        original = r.json()["text"]
        corrected = d.client.post(
            f"/v1/audio/transcriptions/{sample_id}/correction",
            headers={"Authorization": f"Bearer {key}"},
            json={"corrected_text": original + " (सुधारा गया)"},
        )
        sample = d.client.get(
            f"/v1/speech-samples/{sample_id}", headers={"Authorization": f"Bearer {key}"}
        )
        correction_row = {
            "correction_status": corrected.status_code,
            "sample_fetch_status": sample.status_code,
            "sample_leaks": leak_scan(sample.text),
            "original_preserved": sample.json().get("original_transcript") == original,
            "current_is_corrected": sample.json()
            .get("current_transcript", "")
            .endswith("(सुधारा गया)"),
        }
    d.rows["correction"] = correction_row

    r = d.post("hi-short.wav", language="hi", contribution="off")
    d.summarize(
        "contribution_off",
        r,
        no_sample=r.headers.get("X-IntelliAI-Sample") is None,
        transcript_still_returned=bool(r.json().get("text")),
    )

    # ── Malformed / empty / tiny inputs (Phase 5, items 13-15) ───────
    for clip, name in (
        ("garbage.wav", "malformed_audio"),
        ("empty.wav", "empty_audio"),
        ("tiny-malformed.wav", "tiny_malformed_audio"),
    ):
        r = d.post(clip, language="hi")
        d.summarize(name, r, error_param=r.json().get("error", {}).get("param"))

    # ── The 600 s law through the gateway, with usage deltas ─────────
    for clip, name, seconds in (
        ("hi-300s.wav", "long_300s_chunked", 300.0),
        ("hi-600s.wav", "long_600s_chunked", 600.0),
    ):
        before = d.usage_total()
        r = d.post(clip, language="hi", response_format="verbose_json")
        after = d.usage_total()
        body = r.json()
        segments = body.get("segments", [])
        join = " ".join(str(s.get("text", "")) for s in segments)
        d.summarize(
            name,
            r,
            segment_count=len(segments),
            join_equals_text=join == body.get("text", ""),
            first_start=segments[0]["start"] if segments else None,
            last_end=segments[-1]["end"] if segments else None,
            output_chars=len(body.get("text", "")),
            usage_delta_seconds=round(after - before, 3),
            # minutes are reported to 2 decimals -> 0.6 s resolution
            billed_exactly_once=abs((after - before) - seconds) <= 0.6,
        )
    before = d.usage_total()
    r = d.post("hi-602s.wav", language="hi")
    after = d.usage_total()
    error = r.json().get("error", {})
    d.summarize(
        "ceiling_602s_refused",
        r,
        error_param=error.get("param"),
        error_names_limit="600s" in str(error.get("message", "")),
        refusal_billed_zero=abs(after - before) < 0.001,
    )

    payload = {
        "drill": "24-gateway-product-path (E3 candidate)",
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "base_url": args.base_url,
        "results": d.rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(d.rows, ensure_ascii=False, indent=2)[:4500])
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
