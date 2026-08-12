"""Milestone 18: the REAL product path, drilled end to end, locally.

Every request here goes through POST /v1/audio/transcriptions on a
REAL gateway process (staging registry profile) backed by the REAL
multi-slot runtime executing the REAL pinned models — no research
endpoint, no fakes, no mocks. The API key arrives via the
INTELLIAI_M18_KEY environment variable and never enters this file or
its output; response bodies are scanned for internal-name leaks before
being summarized into the evidence record.
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

LEAK_MARKERS = ("qwen", "llama", "gguf", "ggml", "whisper", "ctranslate", "faster")
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def leak_scan(text: str) -> list[str]:
    lowered = text.lower()
    return [marker for marker in LEAK_MARKERS if marker in lowered]


class Drills:
    def __init__(self, base_url: str, key: str, audio_dir: Path) -> None:
        self.client = httpx.Client(base_url=base_url, timeout=300.0)
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
        headers: dict[str, str] = {"X-IntelliAI-Client": "m18-drill/1.0"}
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
        wav = (self.audio / clip).read_bytes()
        started = time.perf_counter()
        response = self.client.post(
            "/v1/audio/transcriptions",
            headers=headers,
            files={"file": (clip, wav, "audio/wav")},
            data=data,
        )
        elapsed = round(time.perf_counter() - started, 2)
        self.rows.setdefault("_timings", []).append({clip: elapsed})
        return response

    def summarize(self, name: str, response: httpx.Response, **extra: Any) -> dict[str, Any]:
        body_text = response.text
        row: dict[str, Any] = {
            "status": response.status_code,
            "request_id_header": response.headers.get("X-Request-ID"),
            "sample_header": response.headers.get("X-IntelliAI-Sample"),
            "leaks": leak_scan(body_text),
            **extra,
        }
        self.rows[name] = row
        return row

    def usage_summary(self) -> dict[str, Any]:
        response = self.client.get(
            "/v1/usage/summary", headers={"Authorization": f"Bearer {self.key}"}
        )
        response.raise_for_status()
        body: dict[str, Any] = response.json()
        body["_leaks"] = leak_scan(response.text)
        return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--audio-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    key = os.environ["INTELLIAI_M18_KEY"]

    d = Drills(args.base_url, key, args.audio_dir)
    usage_before = d.usage_summary()

    # ── Auth matrix ──────────────────────────────────────────────────
    d.summarize("auth_missing_key", d.post("hi-short.wav", auth=None, language="hi"))
    d.summarize("auth_invalid_key", d.post("hi-short.wav", auth="invalid", language="hi"))

    # ── Routing + transcription through the real models ─────────────
    r = d.post("hi-short.wav", language="hi")
    d.summarize(
        "hindi_explicit",
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
        "english_explicit",
        r,
        ask_not=("ask not" in r.json().get("text", "").lower()),
        text_preview=r.json().get("text", "")[:80],
    )
    # No declared language = the DEFAULT route (declaration-first law):
    # served honestly by the incumbent, not auto-detected onto Qwen.
    r = d.post("hi-short.wav")
    d.summarize(
        "hindi_undeclared_default_route",
        r,
        devanagari=bool(DEVANAGARI.search(r.json().get("text", ""))),
    )

    # ── verbose_json (Phase 9) ───────────────────────────────────────
    r = d.post("hi-short.wav", language="hi", response_format="verbose_json")
    body = r.json()
    d.summarize(
        "verbose_json_hindi",
        r,
        segment_count=len(body.get("segments", [])),
        segment_keys=sorted(body.get("segments", [{}])[0]) if body.get("segments") else [],
        spans_full_clip=(
            bool(body.get("segments"))
            and body["segments"][0]["start"] == 0.0
            and abs(body["segments"][0]["end"] - body.get("duration", 0)) < 0.01
        ),
    )
    r = d.post("en-jfk.wav", language="en", response_format="verbose_json")
    d.summarize("verbose_json_english", r, segment_count=len(r.json().get("segments", [])))

    # ── Collection + correction (Phases 7-8) ─────────────────────────
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

    # ── The 120-second ceiling, through the gateway (Phase 10) ──────
    for clip, name in (
        ("hi-119s.wav", "ceiling_119s"),
        ("hi-120s.wav", "ceiling_120s"),
        ("hi-121s.wav", "ceiling_121s"),
    ):
        r = d.post(clip, language="hi")
        extra: dict[str, Any] = {}
        if r.status_code == 200:
            extra["output_chars"] = len(r.json().get("text", ""))
        else:
            error = r.json().get("error", {})
            extra["error_param"] = error.get("param")
            extra["error_names_limit"] = "120 seconds" in str(error.get("message", ""))
        d.summarize(name, r, **extra)

    usage_after = d.usage_summary()
    payload = {
        "drill": "18-gateway-product-path",
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "base_url": args.base_url,
        "usage_before": usage_before,
        "usage_after": usage_after,
        "results": d.rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(d.rows, ensure_ascii=False, indent=2)[:4000])
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
