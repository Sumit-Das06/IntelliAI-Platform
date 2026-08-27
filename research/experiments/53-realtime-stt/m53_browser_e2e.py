"""M53 real-browser realtime E2E — Chromium with a FAKE MICROPHONE fed
by our real clips, against the staging HTTPS stack.

Chromium's ``--use-file-for-fake-audio-capture`` plays a WAV through
the getUserMedia path, so this exercises the ENTIRE product loop the
way a speaking user would: mic → AudioWorklet → wss → gateway →
runtime session → LA2 display → punctuated final → Share/Correction.

    python m53_browser_e2e.py en <wav> <out.json> [--correct]
    python m53_browser_e2e.py hi <wav> <out.json>
    python m53_browser_e2e.py offdrill <ignored> <out.json>
"""

from __future__ import annotations

import itertools
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"
SHOTS = EVIDENCE / "screenshots"
BASE = "https://localhost"
KEY = (
    Path(
        r"C:\Users\VIKASH~1\AppData\Local\Temp\claude"
        r"\d--Sumit-Projects-IntelliAI-Platform"
        r"\67762b73-e6aa-43b8-a730-264d0d432d4f\scratchpad\m24-key.txt"
    )
    .read_text(encoding="utf-8")
    .strip()
)


def main() -> None:
    language, wav_path, out_name = sys.argv[1:4]
    correct = "--correct" in sys.argv
    EVIDENCE.mkdir(exist_ok=True)
    SHOTS.mkdir(exist_ok=True)
    record: dict = {"language": language, "wav": Path(wav_path).name}

    with sync_playwright() as playwright:
        args = [
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
        ]
        if language != "offdrill":
            args.append(f"--use-file-for-fake-audio-capture={wav_path}")
        browser = playwright.chromium.launch(args=args)
        context = browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 1280, "height": 900},
            permissions=["microphone", "clipboard-read", "clipboard-write"],
        )
        context.add_init_script(f"localStorage.setItem('intelliai_api_key', '{KEY}')")
        page = context.new_page()
        page.goto(f"{BASE}/console/playground")
        page.wait_for_selector("#realtime")

        if language == "offdrill":
            # Rollback drill UI half: with the staging flag OFF the button
            # must explain kindly and batch must stay intact.
            page.click("#realtime")
            page.wait_for_function(
                "() => document.getElementById('status').textContent.includes('available')"
                " || document.getElementById('status').textContent.includes('failed')",
                timeout=15_000,
            )
            record["status_line"] = page.text_content("#status")
            record["upload_button_enabled"] = page.is_enabled("#upload")
            page.screenshot(path=str(SHOTS / "rollback-flag-off.png"), full_page=False)
            (EVIDENCE / out_name).write_text(
                json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            print(record)
            browser.close()
            return

        if language == "hi":
            page.select_option("#lang", "hi")

        started = time.perf_counter()
        page.click("#realtime")
        page.wait_for_function(
            "() => document.getElementById('status').textContent.includes('Listening')",
            timeout=30_000,
        )
        # Sample the DISPLAYED transcript growth (the LA2 surface itself).
        growth: list[dict] = []
        first_text_at = None
        deadline = time.perf_counter() + min(60.0, max(12.0, _wav_seconds(wav_path) + 4.0))
        mid_shot = False
        while time.perf_counter() < deadline:
            value = page.input_value("#transcript")
            now = round(time.perf_counter() - started, 2)
            if value and first_text_at is None:
                first_text_at = now
            growth.append({"t": now, "words": len(value.split())})
            if value and not mid_shot:
                page.screenshot(path=str(SHOTS / f"{language}-partials.png"), full_page=False)
                mid_shot = True
            time.sleep(0.25)
        page.click("#realtime")  # Stop
        page.wait_for_function(
            "() => document.getElementById('status').textContent.includes('Done')"
            " || document.getElementById('status').textContent.includes('unavailable')"
            " || document.getElementById('status').textContent.includes('ended')",
            timeout=60_000,
        )
        final_text = page.input_value("#transcript")
        page.screenshot(path=str(SHOTS / f"{language}-final.png"), full_page=False)

        # Monotonic display law, measured on what the USER saw.
        counts = [row["words"] for row in growth]
        record.update(
            {
                "status_line": page.text_content("#status"),
                "first_visible_text_at_s": first_text_at,
                "display_monotonic": all(a <= b for a, b in itertools.pairwise(counts)),
                "displayed_growth": counts[::4],
                "final_text": final_text,
                "final_word_count": len(final_text.split()),
            }
        )

        # Share (clipboard fallback in headless) must carry the FINAL text.
        page.click("#share")
        page.wait_for_function("() => document.getElementById('share-note').textContent !== ''")
        record["share_clipboard_equals_final"] = (
            page.evaluate("navigator.clipboard.readText()") == final_text
        )
        if correct and page.is_visible("#save"):
            corrected = final_text + " correction-check"
            page.fill("#transcript", corrected)
            page.click("#save")
            page.wait_for_function(
                "() => document.getElementById('thanks').textContent.length > 0",
                timeout=30_000,
            )
            record["correction_thanks"] = page.text_content("#thanks")
            page.screenshot(path=str(SHOTS / f"{language}-correction.png"), full_page=False)
        record["save_button_visible"] = page.is_visible("#save")

        # Leak scan of everything the browser saw.
        content = page.content().casefold()
        record["leaks"] = [
            word for word in ("kredor", "whisper", "qwen", "llama", "cuda") if word in content
        ]
        browser.close()

    (EVIDENCE / out_name).write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    safe = {k: v for k, v in record.items() if k != "final_text"}
    print(json.dumps(safe, ensure_ascii=False)[:600])


def _wav_seconds(path: str) -> float:
    import wave

    with wave.open(path, "rb") as handle:
        return handle.getnframes() / handle.getframerate()


if __name__ == "__main__":
    main()
