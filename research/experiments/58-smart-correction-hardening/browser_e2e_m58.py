"""M58 Phase 9 — browser E2E: the full M57 Improve flow PLUS the two
M58 drills: duplicate-click (two fast clicks must fire exactly ONE
correction request) and long-Hindi async UX (a ~250-word Hindi
transcript corrects with the page staying responsive, no stuck state).

    python browser_e2e_m58.py <en|hi> <wav> <out.json>
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

HI_LONG_SEED = [
    "कल हम लोग नई रिपोर्ट पर काम कर रहा था",
    "सर्वर बार बार बंद हो रहा था और किसी को कारण नहीं पता",
    "मुझे लगता है कि मीटिंग से पहले हमें लॉग देखना चाहिए",
    "ग्राहक ने कहा कि मोबाइल पर पेज बहुत धीरे खुलती है",
    "हमारी टीम ने रिव्यू पूरा कर लिया लेकिन अप्रूव करना भूल गई",
    "रिलीज़ के बाद किसी को डॉक्यूमेंटेशन अपडेट करना होगा",
    "हम अभी भी सिक्योरिटी रिव्यू का इंतज़ार कर रहे हैं",
    "बैकअप कल रात दो बार चला और किसी को पता नहीं क्यों",
    "मैं कल सुबह स्टैंडअप में सब कुछ बता दूँगा",
    "टेस्ट हर शुक्रवार को फेल हो रहा था अब ठीक है",
    "स्टेजिंग का व्यवहार लोकल से अलग दिख रहा है",
    "आज दोपहर को बिजली चली गई थी इसलिए काम रुक गया",
    "मीटिंग में तय हुआ कि पहले छोटे बदलाव किए जाएँगे",
    "पुराने ग्राहक ने फिर से वही शिकायत दोहराई है",
    "अगली तिमाही का बजट अभी तक मंज़ूर नहीं हुआ",
    "नई भर्ती के लिए इंटरव्यू अगले हफ्ते रखे गए हैं",
    "मौसम खराब होने की वजह से डिलीवरी अटक गई है",
    "पिछले महीने की बिक्री उम्मीद से बेहतर रही है",
    "टीम ने रात भर जागकर समस्या का हल निकाला",
    "छुट्टियों की सूची अगले सोमवार को जारी की जाएगी",
]
HI_LONG = " ".join(" ".join(HI_LONG_SEED * 2).split()[:250])


def main() -> None:
    language, wav_path, out_name = sys.argv[1:4]
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    SHOTS.mkdir(exist_ok=True)
    record: dict = {"language": language}
    correction_requests: list[float] = []
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
        page.on(
            "request",
            lambda req: (
                correction_requests.append(time.time())
                if "/v1/text/corrections" in req.url
                else None
            ),
        )
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

        # ── M58 drill 1: duplicate click fires exactly one request ──
        before = len(correction_requests)
        # A real double-click lands in one event-loop turn; page.click()
        # would WAIT for the button to re-enable and fire a legitimate
        # second correction. Dispatch both synchronously instead.
        page.evaluate(
            "() => { const b = document.getElementById('smart-correct'); b.click(); b.click(); }"
        )
        page.wait_for_function(
            "() => !document.getElementById('sc-improved').classList.contains('hidden')"
            " || document.getElementById('sc-note').textContent.includes('unavailable')",
            timeout=120_000,
        )
        record["duplicate_click_requests"] = len(correction_requests) - before
        improved_text = page.input_value("#transcript")
        record["improved_differs"] = improved_text != final_text
        record["toggle_visible"] = page.is_visible("#sc-original")

        # Toggle + share stay intact (M57 regression).
        page.click("#sc-original")
        record["toggle_back_to_original"] = page.input_value("#transcript") == final_text
        page.click("#sc-improved")
        record["toggle_to_improved"] = page.input_value("#transcript") == improved_text

        # Stale drill: user edit wins.
        page.fill("#transcript", final_text)
        page.click("#smart-correct")
        page.fill("#transcript", final_text + " USER-EDIT")
        page.wait_for_function(
            "() => document.getElementById('sc-note').textContent.includes('discarded')"
            " || document.getElementById('sc-note').textContent.includes('unavailable')",
            timeout=120_000,
        )
        record["user_edit_preserved"] = page.input_value("#transcript").endswith("USER-EDIT")

        # ── M58 drill 2: long-Hindi async UX (hi run only) ──────────
        if language == "hi":
            page.fill("#transcript", HI_LONG)
            started = time.time()
            page.click("#smart-correct")  # click clears sc-note synchronously

            # The page must stay responsive while the model works: the
            # language selector still answers within the wait window.
            time.sleep(1.0)
            record["page_responsive_during_long_hi"] = page.evaluate(
                "() => { const s = document.getElementById('lang'); return s && !s.disabled; }"
            )
            # The toggle pair is already visible from the earlier drill, so
            # completion is signalled by sc-note (cleared on click, filled
            # on success/failure) — never by button visibility.
            page.wait_for_function(
                "() => document.getElementById('sc-note').textContent.includes('AI improved')"
                " || document.getElementById('sc-note').textContent.includes('unavailable')"
                " || document.getElementById('sc-note').textContent.includes('unchanged')",
                timeout=180_000,
            )
            record["long_hi_note"] = page.text_content("#sc-note")
            record["long_hi_seconds"] = round(time.time() - started, 1)
            record["long_hi_out_words"] = len(page.input_value("#transcript").split())
            page.screenshot(path=str(SHOTS / "m58-hi-long-improved.png"))

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
