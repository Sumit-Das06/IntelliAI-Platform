"""M19 Phase 15: long audio through the REAL Studio in a real browser.

Chromium (Playwright) drives /console/playground on the staging
gateway exactly as a user would: seed the stored key, upload the file,
press Transcribe, read the transcript and the Developer Details pane.
The Studio itself requests verbose_json, so the raw response pane
carries the multi-window segments for a chunked request.

Steps: 300 s Hindi with contribution ON (then a correction through the
Studio's own button), 600 s Hindi with contribution OFF. Checks: the
transcript is Devanagari and complete-sized, the UI stays responsive
during the long decode (the tab strip still switches), sample id
present/absent as the toggle says, zero internal names anywhere in the
page or the raw response.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

LEAK_MARKERS = ("qwen", "llama", "gguf", "ggml", "whisper", "ctranslate", "faster")
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def leak_scan(text: str) -> list[str]:
    lowered = text.lower()
    return [marker for marker in LEAK_MARKERS if marker in lowered]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--audio-dir", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    key = os.environ["INTELLIAI_M19_KEY"]

    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {
        "verification": "19-web-long-audio",
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "steps": [],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"{args.base_url}/console/playground")
        page.evaluate("key => localStorage.setItem('intelliai_api_key', key)", key)
        page.reload()

        def transcribe_via_studio(
            wav: Path, *, contribute: bool, label: str, timeout_s: float
        ) -> dict[str, Any]:
            page.evaluate("document.getElementById('transcript').value = ''")
            page.select_option("#lang", "hi")
            checkbox = page.locator("#contribute")
            if checkbox.is_checked() != contribute:
                checkbox.click()
            page.set_input_files("#file", str(wav))
            page.click("#transcribe")
            started = time.monotonic()

            # UI responsiveness DURING the decode: the tab strip must
            # still respond while the request is in flight.
            time.sleep(3.0)
            page.click("#tab-python")
            python_tab_active = "is-active" in (page.get_attribute("#tab-python", "class") or "")
            page.click("#tab-curl")

            # Settled = transcript filled or an error status shown.
            deadline = time.monotonic() + timeout_s
            transcript = ""
            status = ""
            while time.monotonic() < deadline:
                transcript = page.input_value("#transcript")
                status = page.text_content("#status") or ""
                if transcript.strip() or "err" in (page.get_attribute("#status", "class") or ""):
                    break
                time.sleep(2.0)
            elapsed = round(time.monotonic() - started, 1)

            raw_response = page.text_content("#dev-response") or ""
            body: dict[str, Any] = {}
            with contextlib.suppress(json.JSONDecodeError):
                body = json.loads(raw_response)
            segments = body.get("segments", [])
            joined = " ".join(s.get("text", "") for s in segments)
            page.screenshot(path=str(args.evidence_dir / f"web-{label}.png"), full_page=True)
            page_text = page.content()
            return {
                "step": label,
                "elapsed_seconds": elapsed,
                "status_line": status.strip(),
                "transcript_chars": len(transcript),
                "devanagari": bool(DEVANAGARI.search(transcript)),
                "ui_responsive_during_decode": python_tab_active,
                "request_id": (page.text_content("#dev-request") or "").strip(),
                "sample_id": (page.text_content("#dev-sample") or "").strip(),
                "response_segments": len(segments),
                "segments_join_equals_text": bool(body) and joined == body.get("text", ""),
                "duration_reported": body.get("duration"),
                "leaks_in_raw_response": leak_scan(raw_response),
                "ui_leaks": leak_scan(page_text),
            }

        record["steps"].append(
            transcribe_via_studio(
                args.audio_dir / "concat-300s.wav",
                contribute=True,
                label="300s-contribute-on",
                timeout_s=460,
            )
        )

        # Correction through the Studio's own Save button.
        page.fill("#transcript", page.input_value("#transcript") + " [सुधार]")
        page.click("#save")
        page.wait_for_timeout(2500)
        record["steps"].append(
            {
                "step": "correction-300s",
                "thanks": (page.text_content("#thanks") or "").strip(),
            }
        )

        record["steps"].append(
            transcribe_via_studio(
                args.audio_dir / "concat-600s.wav",
                contribute=False,
                label="600s-contribute-off",
                timeout_s=460,
            )
        )
        browser.close()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
