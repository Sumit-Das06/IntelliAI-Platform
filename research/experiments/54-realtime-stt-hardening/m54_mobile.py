"""M54 Phase 25 — mobile-width UI: 390 px, 820 px, desktop."""

from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"
SHOTS = EVIDENCE / "screenshots"

result: dict = {}
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    sizes = (("mobile390", 390, 844), ("tablet820", 820, 1180), ("desktop", 1280, 900))
    for name, width, height in sizes:
        context = browser.new_context(
            ignore_https_errors=True, viewport={"width": width, "height": height}
        )
        page = context.new_page()
        page.goto("https://localhost/console/playground")
        page.wait_for_selector("#realtime")
        result[name] = {
            "realtime_button_visible": page.is_visible("#realtime"),
            "no_horizontal_scroll": page.evaluate(
                "() => document.documentElement.scrollWidth <= window.innerWidth + 1"
            ),
        }
        SHOTS.mkdir(exist_ok=True, parents=True)
        page.screenshot(path=str(SHOTS / f"m54-{name}.png"))
        context.close()
    browser.close()
(EVIDENCE / "mobile-ui.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result))
