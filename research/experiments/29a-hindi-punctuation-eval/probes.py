"""M29A — deterministic Hinglish / edge-case probe set (research instrument).

A SMALL fixed probe list for sanity only — NOT the benchmark, and no
statistical claim is made from it. Each probe is fed to a restorer and we
record: the output, the word-preservation invariant, and which marks were
added. Probe texts are authored here (committed, deterministic) — no
customer or private text.

Runs inside the scratch venv (needs punctuators). PYTHONIOENCODING=utf-8.
"""

from __future__ import annotations

import json
import sys
import time
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent

PROBES = [
    {"kind": "hindi-statement", "text": "मैं घर जा रहा हूँ आप क्या कर रहे हैं"},
    {"kind": "hindi-question", "text": "क्या आप कल ऑफिस आओगे"},
    {"kind": "hindi-two-sentences", "text": "खाना तैयार है सब लोग खाने आ जाओ"},
    {"kind": "hinglish-mixed", "text": "मैंने कल एक नया laptop खरीदा उसकी battery life बहुत अच्छी है"},
    {"kind": "hinglish-code-switch", "text": "meeting कल सुबह दस बजे है आप time पर आ जाना"},
    {"kind": "english-control", "text": "the meeting is at ten tomorrow please be on time"},
    {"kind": "numbers-hindi", "text": "मेरा नंबर नौ आठ सात छह पांच चार तीन दो एक शून्य है"},
    {"kind": "numbers-digits", "text": "कुल रकम 2500 रुपये है और छूट 150 रुपये मिली"},
    {"kind": "abbreviation", "text": "डॉ शर्मा ने कहा कि रिपोर्ट सोमवार तक आ जाएगी"},
    {"kind": "url", "text": "आप हमारी वेबसाइट intelliai.example.com पर जाकर देख सकते हैं"},
    {"kind": "email", "text": "मुझे अपना बायोडाटा support@example.com पर भेज दीजिए"},
    {"kind": "quoted-speech", "text": "उन्होंने कहा मैं कल जरूर आऊंगा और फिर चले गए"},
]


def depunct(text: str) -> str:
    folded = unicodedata.normalize("NFC", text).casefold()
    cleaned = "".join(" " if unicodedata.category(ch).startswith("P") else ch for ch in folded)
    return " ".join(cleaned.split())


def marks_added(before: str, after: str) -> dict:
    marks = {"danda": "।", "comma": ",", "question_mark": "?", "exclamation": "!", "full_stop": "."}
    return {k: after.count(m) - before.count(m) for k, m in marks.items()}


def main() -> None:
    from punctuators.models import PunctCapSegModelONNX

    t0 = time.perf_counter()
    model = PunctCapSegModelONNX.from_pretrained("pcs_47lang")
    load_seconds = round(time.perf_counter() - t0, 2)

    results = []
    for probe in PROBES:
        out = model.infer([probe["text"]])[0]
        joined = " ".join(out) if isinstance(out, list) else str(out)
        results.append(
            {
                **probe,
                "output": joined,
                "invariant": "PASS" if depunct(joined) == depunct(probe["text"]) else "FAIL",
                "marks_added": marks_added(probe["text"], joined),
            }
        )

    out_path = HERE / "probes-results.json"
    out_path.write_text(
        json.dumps(
            {
                "experiment": "29a-hindi-punctuation-eval",
                "phase": "hinglish-edge-probes (sanity only, no statistical claim)",
                "model": "1-800-BAD-CODE/punct_cap_seg_47_language"
                " @ 1b9d51fc7989ebc61e844d407d9dadd08ff4ba28",
                "model_load_seconds": load_seconds,
                "probes": results,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    fails = [r for r in results if r["invariant"] != "PASS"]
    for r in results:
        print(f"[{r['invariant']}] {r['kind']}: {r['output'][:90]}")
    print(f"\ninvariant failures: {len(fails)}/{len(results)}")
    print(f"written: {out_path}")


if __name__ == "__main__":
    sys.exit(main())
