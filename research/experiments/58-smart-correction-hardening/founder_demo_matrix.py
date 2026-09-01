# ruff: noqa: S310 — research script: long Devanagari rows; operator-local URLs
"""M58 Phase 8 — the founder demo matrix: 17 demo-facing cases (7 EN,
10 HI) run LIVE through the authenticated gateway, each with the input
transcript, the AI suggestion, what the founder should expect to see,
and a mechanical PASS/FAIL. Same verdict law as hi_regression.py:

    correct — output must differ AND keep every marker
    keep    — output must be squash-identical (punctuation-only ok)
    guard   — every marker survives (meaning > grammar)

    python founder_demo_matrix.py
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"
sys.path.insert(0, str(HERE))
from hi_regression import KEY, URL, marker_ok, squash  # noqa: E402

# (id, language, kind, input, markers, what the founder should see)
CASES = [
    # ── English (7) ─────────────────────────────────────────────────
    (
        "en1",
        "en",
        "correct",
        "i has went to the office yesterday and meet the client",
        ["office", "client"],
        "grammar fixed: 'I went to the office yesterday and met the client'",
    ),
    (
        "en2",
        "en",
        "correct",
        "um so basically we uh we need to to ship the build today",
        ["ship", "build", "today"],
        "fillers and stutters removed, meaning intact",
    ),
    (
        "en3",
        "en",
        "correct",
        "can you send me the file which i had sended you last week",
        ["sent"],
        "'sended' becomes 'sent' — the DIRECTION of sending must not flip",
    ),
    (
        "en4",
        "en",
        "guard",
        "the invoice total is 45250 rupees due on 15 march",
        ["45250", "15"],
        "every number survives exactly",
    ),
    (
        "en5",
        "en",
        "guard",
        "please email the report to support@intelliai.com by friday",
        ["support@intelliai.com"],
        "the email address survives byte-exact",
    ),
    (
        "en6",
        "en",
        "keep",
        "The deployment finished successfully and all tests passed.",
        [],
        "already-correct text returned unchanged",
    ),
    (
        "en7",
        "en",
        "guard",
        "sumit will call priya after the demo tomorrow",
        ["sumit", "priya"],
        "names survive; capitalization may improve",
    ),
    # ── Hindi (10) ──────────────────────────────────────────────────
    ("hi1", "hi", "correct", "मेरी भाई कल आएगी", ["भाई"], "gender agreement fixed: मेरा भाई कल आएगा"),
    (
        "hi2",
        "hi",
        "correct",
        "मतलब वो वो रिपोर्ट आज ही भेज दो",
        ["रिपोर्ट", "आज"],
        "stutter (वो वो) cleaned, instruction intact",
    ),
    (
        "hi3",
        "hi",
        "correct",
        "kal office nahi aaunga kyunki tabiyat kharab hai",
        ["ऑफिस|office", "तबियत|तबीयत"],
        "Roman Hindi becomes clean Devanagari",
    ),
    (
        "hi4",
        "hi",
        "guard",
        "meeting cancel ho gayi hai",
        ["मीटिंग|meeting", "कैंसिल|कैंसल|cancel"],
        "loanwords stay loanwords (मीटिंग कैंसिल), never translated",
    ),
    (
        "hi5",
        "hi",
        "guard",
        "कुल 25000 रुपये देने हैं",
        ["25000"],
        "the amount survives exactly, no Devanagari numerals",
    ),
    (
        "hi6",
        "hi",
        "guard",
        "mera number 9123456780 hai",
        ["9123456780"],
        "phone number survives digit-for-digit",
    ),
    (
        "hi7",
        "hi",
        "guard",
        "रोहित और मोहित दोनों आएंगे",
        ["रोहित", "मोहित"],
        "similar-sounding names never swapped",
    ),
    (
        "hi8",
        "hi",
        "guard",
        "report admin@intelliai.com par bhejo",
        ["admin@intelliai.com"],
        "email survives inside Roman-Hindi input",
    ),
    ("hi9", "hi", "keep", "हम कल सुबह नौ बजे मिलेंगे।", [], "already-correct Hindi returned unchanged"),
    (
        "hi10",
        "hi",
        "correct",
        "boss ne bola ki demo acha tha lekin report late hui",
        ["बॉस|boss", "डेमो|demo", "रिपोर्ट|report", "लेट|late"],
        "mixed Hinglish sentence becomes natural Hindi, every borrowed word kept",
    ),
]


def call(text: str, language: str) -> tuple[str | None, float, int]:
    payload = json.dumps({"text": text, "language": language}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        URL,
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.loads(response.read())
        return str(body["corrected_text"]), round((time.perf_counter() - started) * 1000, 1), 200
    except urllib.error.HTTPError as exc:
        return None, round((time.perf_counter() - started) * 1000, 1), exc.code


def main() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    rows = []
    passes = 0
    for case_id, language, kind, text, markers, expected in CASES:
        output, ms, status = call(text, language)
        verdict, reason = "FAIL", ""
        if output is None:
            reason = f"http {status}"
        else:
            markers_alive = all(marker_ok(m, output) for m in markers)
            unchanged = squash(output) == squash(text)
            if not markers_alive:
                reason = "marker lost — meaning risk"
            elif kind == "keep" and not unchanged:
                reason = "rewrote already-correct text"
            elif kind == "correct" and unchanged:
                reason = "under-correction (safe direction)"
            else:
                verdict = "PASS"
        passes += verdict == "PASS"
        rows.append(
            {
                "id": case_id,
                "language": language,
                "kind": kind,
                "input": text,
                "ai_suggestion": output,
                "expected": expected,
                "ms": ms,
                "verdict": verdict,
                "reason": reason,
            }
        )
        print(case_id, verdict, reason, "|", (output or "")[:70])
    result = {
        "what": "M58 founder demo matrix — live gateway, deterministic pinned server",
        "pass": passes,
        "total": len(CASES),
        "rows": rows,
    }
    (EVIDENCE / "founder-demo-matrix.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"{passes}/{len(CASES)} PASS -> founder-demo-matrix.json")


if __name__ == "__main__":
    main()
