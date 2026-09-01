# ruff: noqa: S310 — research script: long Devanagari rows; operator-local URLs
"""M58 Phase 5 — correction latency ladder, LIVE through the authenticated
gateway. Sizes 20/50/100/250/500 words (500 < MAX_INPUT_WORDS=600 must pass);
then a >600-word request must be REFUSED loudly with an actionable message
(no silent truncation — the M17 law applied to text).

    python latency_ladder.py <out.json>
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
SCRATCH = Path(
    r"C:\Users\VIKASH~1\AppData\Local\Temp\claude"
    r"\d--Sumit-Projects-IntelliAI-Platform"
    r"\67762b73-e6aa-43b8-a730-264d0d432d4f\scratchpad"
)
KEY = (SCRATCH / "m24-key.txt").read_text(encoding="utf-8").strip()
URL = "http://127.0.0.1:8000/v1/text/corrections"

# VARIED sentence pools cycled to size. A single repeated seed measured
# wrong the first time: the model deduplicated 500 words down to ~36 —
# which exposed the content-collapse trust-gate gap AND invalidated the
# timing. Distinct sentences keep output length ≈ input length, the way
# a real monologue does.
EN_POOL = [
    "so basically we was working on the new deployment yesterday",
    "and the server keep crashing every time we push the build",
    "i think we need to check the logs before the meeting",
    "the customer said the dashboard is loading very slow on mobile",
    "we should probably move the heavy queries out of the main thread",
    "my teammate already finish the review but forgot to approve it",
    "the staging environment behave different from what we see locally",
    "someone need to update the documentation after this release goes out",
    "the design team want a smaller header on the settings page",
    "we still waiting for the security review to come back",
    "backup job ran twice last night and nobody know why",
    "the intern fixed the flaky test that was failing every friday",
    "marketing asked when the new pricing page will be ready",
    "i will summarize everything in the standup tomorrow morning",
]
HI_POOL = [
    "कल हम लोग नई रिपोर्ट पर काम कर रहा था",
    "सर्वर बार बार बंद हो रहा था और किसी को कारण नहीं पता",
    "मुझे लगता है कि मीटिंग से पहले हमें लॉग देखना चाहिए",
    "ग्राहक ने कहा कि मोबाइल पर पेज बहुत धीरे खुलती है",
    "हमारी टीम ने रिव्यू पूरा कर लिया लेकिन अप्रूव करना भूल गई",
    "डिज़ाइन टीम को सेटिंग पेज पर छोटा हेडर चाहिए",
    "रिलीज़ के बाद किसी को डॉक्यूमेंटेशन अपडेट करना होगा",
    "हम अभी भी सिक्योरिटी रिव्यू का इंतज़ार कर रहे हैं",
    "बैकअप कल रात दो बार चला और किसी को पता नहीं क्यों",
    "नई कीमत वाला पेज कब तैयार होगा यह पूछा गया था",
    "मैं कल सुबह स्टैंडअप में सब कुछ बता दूँगा",
    "टेस्ट हर शुक्रवार को फेल हो रहा था अब ठीक है",
    "स्टेजिंग का व्यवहार लोकल से अलग दिख रहा है",
    "भारी क्वेरी को मुख्य थ्रेड से बाहर करना चाहिए",
    "आज दोपहर को बिजली चली गई थी इसलिए काम रुक गया",
    "नए लैपटॉप पर सब कुछ पहले से तेज़ चल रहा है",
    "मीटिंग में तय हुआ कि पहले छोटे बदलाव किए जाएँगे",
    "पुराने ग्राहक ने फिर से वही शिकायत दोहराई है",
    "ऑफिस की छत पर पानी टपक रहा था बारिश में",
    "अगली तिमाही का बजट अभी तक मंज़ूर नहीं हुआ",
    "ट्रेन देर से आई इसलिए मैं मीटिंग में देर से पहुँचा",
    "नई भर्ती के लिए इंटरव्यू अगले हफ्ते रखे गए हैं",
    "सबने मिलकर त्योहार से पहले काम खत्म करने की ठानी",
    "मौसम खराब होने की वजह से डिलीवरी अटक गई है",
    "पुरानी मशीन की मरम्मत पर बहुत खर्च आ रहा है",
    "बच्चों के लिए दफ्तर में एक छोटा कार्यक्रम रखा गया",
    "मैनेजर ने कहा कि रिपोर्ट शुक्रवार तक चाहिए हर हाल में",
    "दुकान वाले ने सामान के दाम फिर बढ़ा दिए हैं",
    "हमने नए विक्रेता से बातचीत शुरू कर दी है",
    "पिछले महीने की बिक्री उम्मीद से बेहतर रही है",
    "सड़क पर काम चलने की वजह से रास्ता बदलना पड़ा",
    "टीम ने रात भर जागकर समस्या का हल निकाला",
    "नए दफ्तर की जगह अभी तक तय नहीं हो पाई",
    "किसी ने मीटिंग का समय बदलकर सबको परेशान कर दिया",
    "खाने की गुणवत्ता को लेकर कैंटीन से बात करनी होगी",
    "छुट्टियों की सूची अगले सोमवार को जारी की जाएगी",
]

SIZES = [20, 50, 100, 250, 500]


def build(pool: list[str], words: int) -> str:
    sentences: list[str] = []
    index = 0
    while sum(len(s.split()) for s in sentences) < words:
        sentences.append(pool[index % len(pool)])
        index += 1
    return " ".join(" ".join(sentences).split()[:words])


def call(text: str, language: str) -> tuple[int, float, str]:
    payload = json.dumps({"text": text, "language": language}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        URL,
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            body = json.loads(response.read())
        ms = round((time.perf_counter() - started) * 1000, 1)
        return 200, ms, str(body.get("corrected_text", ""))
    except urllib.error.HTTPError as exc:
        ms = round((time.perf_counter() - started) * 1000, 1)
        try:
            detail = json.loads(exc.read())
            message = str(detail.get("error", {}).get("message", ""))
        except Exception:
            message = ""
        return exc.code, ms, message


def main() -> None:
    out_name = sys.argv[1] if len(sys.argv) > 1 else "latency-ladder.json"
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    rows = []
    for language, pool in (("en", EN_POOL), ("hi", HI_POOL)):
        for words in SIZES:
            text = build(pool, words)
            status, ms, out = call(text, language)
            ok = status == 200 and bool(out)
            rows.append(
                {
                    "language": language,
                    "words": words,
                    "status": status,
                    "ms": ms,
                    "out_words": len(out.split()) if status == 200 else 0,
                    "verdict": "PASS" if ok else "FAIL",
                }
            )
            print(
                f"{language} {words:>4}w -> {status} {ms:>9.1f}ms "
                f"out={len(out.split()) if status == 200 else 0}w "
                f"{'PASS' if ok else 'FAIL'}"
            )

    # The >600 refusal: must be a 4xx with a human-actionable message,
    # and NEVER a truncated 200.
    over = build(EN_POOL, 650)
    status, ms, message = call(over, "en")
    refusal_ok = 400 <= status < 500 and bool(message)
    rows.append(
        {
            "language": "en",
            "words": 650,
            "status": status,
            "ms": ms,
            "message": message,
            "verdict": "PASS" if refusal_ok else "FAIL",
            "law": "no silent truncation — loud refusal with actionable message",
        }
    )
    print(f"en  650w -> {status} ({ms}ms) message={message!r} {'PASS' if refusal_ok else 'FAIL'}")

    passes = sum(r["verdict"] == "PASS" for r in rows)
    result = {
        "what": "M58 correction latency ladder through the live gateway (RTX 5070 laptop)",
        "pass": passes,
        "total": len(rows),
        "rows": rows,
    }
    (EVIDENCE / out_name).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"{passes}/{len(rows)} PASS -> {out_name}")


if __name__ == "__main__":
    main()
