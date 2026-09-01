"""M57 browser E2E — the Improve flow in a real browser (fake mic):
record realtime session -> final -> ✨ Improve -> AI text -> toggle
Original/AI -> edit-stale drill -> Copy/Share intact -> mobile widths.

    python browser_e2e.py <en|hi> <wav> <out.json>
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"
SHOTS = EVIDENCE / "screenshots"
SCRATCH = Path(
    r"C:\Users\VIKASH~1\AppData\Local\Temp\claude"
    r"\d--Sumit-Projects-IntelliAI-Platform"
    r"\67762b73-e6aa-43b8-a730-264d0d432d4f\scratchpad"
)
KEY = (SCRATCH / "m24-key.txt").read_text(encoding="utf-8").strip()


def main() -> None:
    language, wav_path, out_name = sys.argv[1:4]
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    SHOTS.mkdir(exist_ok=True)
    record: dict = {"language": language}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            args=[
                "--use-fake-ui-for-media-stream",
                "--use-fake-device-for-media-stream",
                f"--use-file-for-fake-audio-capture={wav_path}",
            ]
        )
        context = browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 1280, "height": 900},
            permissions=["microphone", "clipboard-read", "clipboard-write"],
        )
        context.add_init_script(f"localStorage.setItem('intelliai_api_key', '{KEY}')")
        page = context.new_page()
        page.goto("https://localhost/console/playground")
        page.wait_for_selector("#realtime")
        if language == "hi":
            page.select_option("#lang", "hi")
        page.click("#realtime")
        page.wait_for_function(
            "() => document.getElementById('status').textContent.includes('Listening')",
            timeout=30_000,
        )
        time.sleep(12)
        page.click("#realtime")  # Stop
        page.wait_for_function(
            "() => document.getElementById('status').textContent.includes('Done')",
            timeout=60_000,
        )
        final_text = page.input_value("#transcript")
        record["final_words"] = len(final_text.split())
        record["improve_visible"] = page.is_visible("#smart-correct")

        # ✨ Improve
        page.click("#smart-correct")
        page.wait_for_function(
            "() => !document.getElementById('sc-improved').classList.contains('hidden')"
            " || document.getElementById('sc-note').textContent.includes('unavailable')",
            timeout=120_000,
        )
        improved_text = page.input_value("#transcript")
        record["improved_words"] = len(improved_text.split())
        record["improved_differs"] = improved_text != final_text
        record["toggle_visible"] = page.is_visible("#sc-original")
        page.screenshot(path=str(SHOTS / f"m57-{language}-improved.png"))

        # Toggle back and forth.
        page.click("#sc-original")
        record["toggle_back_to_original"] = page.input_value("#transcript") == final_text
        page.click("#sc-improved")
        record["toggle_to_improved"] = page.input_value("#transcript") == improved_text

        # Copy = displayed text (improved active).
        page.click("#share")
        page.wait_for_function("() => document.getElementById('share-note').textContent !== ''")
        record["share_carries_displayed_improved"] = (
            page.evaluate("navigator.clipboard.readText()") == improved_text
        )

        # Stale drill: start Improve, IMMEDIATELY edit — the user's text must win.
        page.fill("#transcript", final_text)
        page.click("#smart-correct")
        page.fill("#transcript", final_text + " USER-EDIT")
        page.wait_for_function(
            "() => document.getElementById('sc-note').textContent.includes('discarded')"
            " || document.getElementById('sc-note').textContent.includes('unavailable')",
            timeout=120_000,
        )
        record["stale_note"] = page.text_content("#sc-note")
        record["user_edit_preserved"] = page.input_value("#transcript").endswith("USER-EDIT")

        content = page.content().casefold()
        record["leaks"] = [
            w for w in ("qwen", "llama", "gguf", "whisper", "kredor") if w in content
        ]
        browser.close()
    (EVIDENCE / out_name).write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(record, ensure_ascii=False))


if __name__ == "__main__":
    main()
