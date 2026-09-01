# ruff: noqa: S310 — research script: long Devanagari rows; operator-local URLs
"""M58 Phase 2 — deterministic Hindi edge-case regression suite, run
LIVE through the authenticated gateway. Classification per row:

    must_correct     — the output must differ from input AND carry the marker
    must_not_change  — squash(output) == squash(input) (punctuation-only ok)
    meaning_guard    — every marker must survive (meaning > grammar, the law)

    python hi_regression.py <out.json>
"""

from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"
SCRATCH = Path(
    r"C:\Users\VIKASH~1\AppData\Local\Temp\claude"
    r"\d--Sumit-Projects-IntelliAI-Platform"
    r"\67762b73-e6aa-43b8-a730-264d0d432d4f\scratchpad"
)
KEY = (SCRATCH / "m24-key.txt").read_text(encoding="utf-8").strip()
URL = "http://127.0.0.1:8000/v1/text/corrections"

# (id, language, kind, input, markers)
# kind: correct=must_correct, keep=must_not_change, guard=meaning_guard
ROWS = [
    # A. gender agreement (must correct)
    ("gA1", "hi", "correct", "मेरा बहन कल आएगा", ["बहन"]),
    ("gA2", "hi", "correct", "यह किताब बहुत अच्छा है", ["किताब"]),
    ("gA3", "hi", "correct", "मुझे एक रिपोर्ट बनाना है", ["रिपोर्ट"]),
    ("gA4", "hi", "correct", "उसकी गाड़ी नया है", ["गाड़ी"]),
    ("gA5", "hi", "correct", "सारी फाइलें डिलीट हो गया", ["फाइलें"]),
    # B. homographs / ambiguity (must keep — no reinterpretation)
    ("hB1", "hi", "keep", "कल हम बाग गए थे।", ["बाग"]),
    ("hB2", "hi", "keep", "मुझे वह सोना पसंद है।", ["सोना"]),
    ("hB3", "hi", "keep", "उसने हार मान ली।", ["हार"]),
    ("hB4", "hi", "guard", "meeting teen baje shuru hogi der mat karna", ["देर|der"]),
    # C. loanwords / hinglish (correct but keep the loanword)
    (
        "cC1",
        "hi",
        "guard",
        "server down hai isliye website nahi khul rahi",
        ["सर्वर|server", "वेबसाइट|website"],
    ),
    ("cC2", "hi", "guard", "bhai ka birthday hai gift lena hai", ["बर्थडे|birthday", "गिफ्ट|gift"]),
    ("cC3", "hi", "guard", "sab theek hai bas thoda busy hoon", ["बिज़ी|बिजी|busy|व्यस्त"]),
    (
        "cC4",
        "hi",
        "guard",
        "password reset karke mujhe bata dena",
        ["पासवर्ड|password", "रीसेट|reset"],
    ),
    # D. names (guard)
    ("dD1", "hi", "guard", "सुमित और अमित दोनों अलग लोग हैं", ["सुमित", "अमित"]),
    ("dD2", "hi", "guard", "sharma ji kal nagpur se aa rahe hain", ["शर्मा|sharma", "नागपुर|nagpur"]),
    ("dD3", "hi", "guard", "priya ko call karke batao", ["प्रिया|priya"]),
    # E. numbers (guard: digits/values survive; no Devanagari-digit conversion)
    ("eE1", "hi", "guard", "मुझे पाँच टिकट चाहिए कल के लिए", ["पाँच"]),
    ("eE2", "hi", "guard", "कुल रकम 12,500 रुपये है", ["12,500|12500"]),
    ("eE3", "hi", "guard", "मेरा नंबर 9876543210 है", ["9876543210"]),
    ("eE4", "hi", "guard", "छूट 15% है 50% नहीं", ["15", "50"]),
    ("eE5", "hi", "guard", "version 2.5 deploy karna hai aaj", ["2.5"]),
    # F. emails / URLs (byte-identical)
    ("fF1", "hi", "guard", "email bhejo support@intelliai.com par", ["support@intelliai.com"]),
    ("fF2", "hi", "guard", "website intelliai.com par jao", ["intelliai.com"]),
    # G. technical terms (guard)
    (
        "gG1",
        "hi",
        "guard",
        "FastAPI aur Redis production mein use hote hain",
        ["FastAPI|फास्टएपीआई", "Redis|रेडिस"],
    ),
    (
        "gG2",
        "hi",
        "guard",
        "CUDA wale GPU par STT aur TTS dono chalte hain",
        ["CUDA|कूडा", "GPU|जीपीयू", "STT", "TTS"],
    ),
    (
        "gG3",
        "hi",
        "guard",
        "PostgreSQL ka backup RAG pipeline se pehle lena",
        ["PostgreSQL|पोस्टग्रेएसक्यूएल|पोस्टग्रेस", "RAG|रैग"],
    ),
    ("gG4", "hi", "guard", "Python ka naya version install karo", ["Python|पाइथन"]),
    # H. already-correct Hindi (must keep)
    ("hH1", "hi", "keep", "मैं कल सुबह दिल्ली जा रहा हूँ।", []),
    ("hH2", "hi", "keep", "क्या आप मुझे वह फाइल भेज सकते हैं?", []),
    ("hH3", "hi", "keep", "बैठक ठीक तीन बजे शुरू होगी।", ["तीन"]),
    ("hH4", "hi", "keep", "हमें ग्राहकों की बात ध्यान से सुननी चाहिए।", []),
    ("hH5", "hi", "keep", "उसने प्रस्ताव के लिए मना कर दिया।", ["मना"]),
]


def squash(text: str) -> str:
    # NFD then drop nukta so फ़ == फ (spelling-variant tolerance in the
    # RULER only — the model may legitimately add the nukta form).
    normalized = unicodedata.normalize("NFD", text).casefold()
    normalized = normalized.replace("़", "")
    normalized = unicodedata.normalize("NFC", normalized)
    normalized = normalized.replace("।", "").replace("॥", "")
    return re.sub(r"[^0-9a-zऀ-ॿ]+", "", normalized)


def correct(text: str, language: str) -> tuple[str | None, float, int]:
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


def marker_ok(marker: str, output: str) -> bool:
    return any(squash(option) in squash(output) for option in marker.split("|"))


def main() -> None:
    out_name = sys.argv[1] if len(sys.argv) > 1 else "hi-regression.json"
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    rows = []
    passes = 0
    for row_id, language, kind, text, markers in ROWS:
        output, ms, status = correct(text, language)
        verdict = "FAIL"
        reason = ""
        if output is None:
            reason = f"http {status}"
        else:
            markers_ok = all(marker_ok(m, output) for m in markers)
            unchanged = squash(output) == squash(text)
            if not markers_ok:
                reason = "marker lost — meaning risk"
            elif kind == "keep" and not unchanged:
                reason = "rewrote already-correct/ambiguous text"
            elif kind == "correct" and unchanged:
                reason = "under-correction (safe direction, still a miss)"
            else:
                verdict = "PASS"
        passes += verdict == "PASS"
        rows.append(
            {
                "id": row_id,
                "kind": kind,
                "in": text,
                "out": output,
                "ms": ms,
                "verdict": verdict,
                "reason": reason,
            }
        )
        print(row_id, kind, verdict, reason, "|", (output or "")[:60])
    result = {
        "what": "M58 Hindi edge-case regression (deterministic: temp-0 pinned server)",
        "pass": passes,
        "total": len(ROWS),
        "priority_note": "meaning_guard failures outrank grammar misses — meaning first",
        "rows": rows,
    }
    (EVIDENCE / out_name).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"{passes}/{len(ROWS)} PASS -> {out_name}")


if __name__ == "__main__":
    main()
