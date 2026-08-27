"""M51 real-browser E2E — Chromium (Playwright) against the local
production-shaped HTTPS stack (Caddy edge, https://localhost).

Drives the ACTUAL STT Playground (/console/playground): uploads real
audio, clicks the real Transcribe/Share/Save-correction controls, reads
the real DOM, and captures screenshots. Nothing is mocked.

    python m51_browser_e2e.py on   # staging flag ON battery
    python m51_browser_e2e.py off  # rollback verification (flag OFF)

Audio clips live OUTSIDE the repo (scratchpad); only text evidence and
screenshots are written here.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"
SHOTS = EVIDENCE / "screenshots"

BASE = "https://localhost"
SCRATCH = Path(
    r"C:\Users\VIKASH~1\AppData\Local\Temp\claude"
    r"\d--Sumit-Projects-IntelliAI-Platform"
    r"\67762b73-e6aa-43b8-a730-264d0d432d4f\scratchpad"
)
KEY = (SCRATCH / "m24-key.txt").read_text(encoding="utf-8").strip()
CLIPS = SCRATCH / "m51clips"
BOSS = Path(r"C:\Users\VIKASHAN TECHNOLOGIE\Downloads\WhatsApp Ptt 2026-08-26 at 7.58.05 PM.ogg")

#: Words the public DOM must never contain (internal-names law).
FORBIDDEN = ("kredor", "punctuate-all", "punct-en-kredor", "b0d8d68c", "whisper", "kokoro")


def transcribe(page: Page, audio: Path, lang: str) -> dict:
    """Upload a clip, click Transcribe, wait for the result, read the DOM."""
    page.select_option("#lang", lang)
    page.set_input_files("#file", str(audio))
    page.wait_for_function("() => !document.getElementById('transcribe').disabled")
    started = time.perf_counter()
    page.click("#transcribe")
    page.wait_for_function(
        "() => { const s = document.getElementById('status').textContent;"
        " const t = document.getElementById('transcribe');"
        " return !t.disabled && !s.includes('Transcribing'); }",
        timeout=300_000,
    )
    elapsed = time.perf_counter() - started
    text = page.input_value("#transcript")
    dev_response = page.text_content("#dev-response") or ""
    try:
        body = json.loads(dev_response)
    except json.JSONDecodeError:
        body = {"unparsed": dev_response[:500]}
    return {
        "clip": audio.name,
        "language": lang,
        "displayed_text": text,
        "status_line": page.text_content("#status"),
        "request_id": page.text_content("#dev-request"),
        "sample_id": page.text_content("#dev-sample"),
        "response_body": body,
        "wall_seconds": round(elapsed, 2),
    }


def scan_forbidden(label: str, content: str, problems: list[str]) -> None:
    lowered = content.casefold()
    for word in FORBIDDEN:
        if word in lowered:
            problems.append(f"{label}: contains {word!r}")


def run(mode: str) -> None:
    EVIDENCE.mkdir(exist_ok=True)
    SHOTS.mkdir(exist_ok=True)
    record: dict = {"mode": mode, "base_url": BASE, "runs": [], "problems": []}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(
            ignore_https_errors=True,  # Caddy's local internal CA
            viewport={"width": 1280, "height": 900},
            permissions=["clipboard-read", "clipboard-write"],
        )
        context.add_init_script(f"localStorage.setItem('intelliai_api_key', '{KEY}')")
        page = context.new_page()
        page.goto(f"{BASE}/console/playground")
        page.wait_for_selector("#transcribe")

        if mode in ("off", "failopen", "recovered"):
            # Single boss pass: rollback (flag OFF), forced-timeout
            # fail-open, or post-restore recovery — same drill, named
            # evidence each.
            result = transcribe(page, BOSS, "en")
            record["runs"].append(result)
            page.screenshot(path=str(SHOTS / f"boss-{mode}.png"), full_page=True)
            (EVIDENCE / f"browser-{mode}.json").write_text(
                json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            print(f"{mode.upper()} text:", result["displayed_text"][:160])
            print(f"{mode.upper()} status:", result["status_line"])
            browser.close()
            return

        # ── boss audio (the primary demo) ────────────────────────────────
        boss = transcribe(page, BOSS, "en")
        record["runs"].append(boss)
        page.screenshot(path=str(SHOTS / "boss-punctuated.png"), full_page=True)
        print("BOSS:", boss["displayed_text"][:160])

        # ── Share: clicks the real button; headless Chromium has no
        # navigator.share, so the M46 clipboard fallback is the path —
        # verify the clipboard holds EXACTLY the displayed transcript.
        page.click("#share")
        page.wait_for_function("() => document.getElementById('share-note').textContent !== ''")
        clipboard = page.evaluate("navigator.clipboard.readText()")
        record["share"] = {
            "note": page.text_content("#share-note"),
            "clipboard_equals_displayed": clipboard == boss["displayed_text"],
        }
        page.screenshot(path=str(SHOTS / "share-note.png"), full_page=False)

        # ── Correction: a REAL fix (the M48 disputed span), saved through
        # the real endpoint; the editor starts from the displayed
        # (punctuated) text.
        corrected = boss["displayed_text"].replace("droughts", "drafts")
        page.fill("#transcript", corrected)
        page.click("#save")
        page.wait_for_function(
            "() => document.getElementById('thanks').textContent.length > 0", timeout=60_000
        )
        record["correction"] = {
            "started_from_displayed": True,
            "edit": "droughts -> drafts (the founder-disputed M48 span)",
            "thanks_line": page.text_content("#thanks"),
        }
        page.screenshot(path=str(SHOTS / "correction-saved.png"), full_page=True)

        # ── dev details open + capture (leak scan happens below) ─────────
        page.click("#dev-details summary")
        page.screenshot(path=str(SHOTS / "dev-details.png"), full_page=True)

        # ── English battery ──────────────────────────────────────────────
        for name in (
            "normal",
            "question",
            "names",
            "date",
            "phone",
            "currency",
            "commas",
            "paragraph",
            "technical",
            "exclaim",
        ):
            result = transcribe(page, CLIPS / f"{name}.wav", "en")
            record["runs"].append(result)
            print(f"{name}: {result['displayed_text'][:100]}")
        page.screenshot(path=str(SHOTS / "battery-last.png"), full_page=True)

        # ── Hindi regression through the same browser ────────────────────
        hindi = transcribe(page, CLIPS / "hindi.wav", "hi")
        record["runs"].append(hindi)
        page.screenshot(path=str(SHOTS / "hindi.png"), full_page=True)
        print("HINDI:", hindi["displayed_text"][:120])

        # ── security scan of everything the browser saw ──────────────────
        scan_forbidden("playground DOM", page.content(), record["problems"])
        for result in record["runs"]:
            scan_forbidden(
                f"response body ({result['clip']})",
                json.dumps(result["response_body"]),
                record["problems"],
            )

        # ── /console/status page ─────────────────────────────────────────
        page.goto(f"{BASE}/console/status")
        page.wait_for_load_state("networkidle")
        status_content = page.content()
        scan_forbidden("status DOM", status_content, record["problems"])
        record["status_page_mentions_production_claim"] = (
            "english punctuation is live in production" in status_content.casefold()
        )
        page.screenshot(path=str(SHOTS / "console-status.png"), full_page=True)

        # ── mobile-width pass (fresh context, 390x844) ───────────────────
        mobile = browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 390, "height": 844},
            permissions=["clipboard-read", "clipboard-write"],
        )
        mobile.add_init_script(f"localStorage.setItem('intelliai_api_key', '{KEY}')")
        mpage = mobile.new_page()
        mpage.goto(f"{BASE}/console/playground")
        mpage.wait_for_selector("#transcribe")
        mresult = transcribe(mpage, CLIPS / "normal.wav", "en")
        mrecord = {
            "displayed_text": mresult["displayed_text"],
            "share_visible": mpage.is_visible("#share"),
            "save_visible": mpage.is_visible("#save"),
            "transcript_visible": mpage.is_visible("#transcript"),
            "no_horizontal_scroll": mpage.evaluate(
                "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
            ),
        }
        record["mobile"] = mrecord
        mpage.screenshot(path=str(SHOTS / "mobile-390.png"), full_page=True)

        # tablet width: layout-only check
        tablet = browser.new_context(
            ignore_https_errors=True, viewport={"width": 820, "height": 1180}
        )
        tpage = tablet.new_page()
        tpage.goto(f"{BASE}/console/playground")
        tpage.wait_for_selector("#transcribe")
        record["tablet_no_horizontal_scroll"] = tpage.evaluate(
            "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
        )
        tpage.screenshot(path=str(SHOTS / "tablet-820.png"), full_page=True)

        browser.close()

    (EVIDENCE / "browser-e2e-on.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("problems:", record["problems"] or "none")


if __name__ == "__main__":
    run(sys.argv[1])
