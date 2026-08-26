# M49 — freeze en-punct-eval@v1 (NEW dataset; frozen Hindi sets and
# the punct_slots@v1 ruler untouched). Sources:
#   - LJSpeech-1.1 normalized transcripts (public domain): read
#     sentences, comma-heavy rows, numbers, multi-sentence paragraphs
#   - authored probes (questions/exclamations/lists/quotes/brands/
#     abbreviations/disfluencies) with the annotation policy in the
#     dataset description
#   - the M48 boss-audio DRAFT reference (spontaneous slice; human
#     verification pending — labeled)
# Deterministic: seed 49, fixed filters, fixed order.
import json
import random
import re
import sys
from pathlib import Path

LJ = Path.home() / "m44/data/LJSpeech-1.1/metadata.csv"
OUT = Path(sys.argv[1])
BOSS_REF = Path(sys.argv[2]).read_text(encoding="utf-8").strip()

rows_lj = []
rows_raw = []
for line in LJ.read_text(encoding="utf-8").splitlines():
    parts = line.split("|")
    if len(parts) >= 3 and parts[2].strip():
        rows_lj.append((parts[0], parts[2].strip()))
        rows_raw.append((parts[0], parts[1].strip()))


def ascii_clean(t):
    return all(ord(c) < 128 for c in t)


sentences = [
    (i, t)
    for i, t in rows_lj
    if t.endswith((".", "?", "!")) and 8 <= len(t.split()) <= 30 and ascii_clean(t)
]
random.seed(49)
picks = random.sample(sentences, 50)

comma_heavy = [
    (i, t)
    for i, t in rows_lj
    if t.count(",") >= 3 and t.endswith(".") and ascii_clean(t) and len(t.split()) <= 45
]
comma_picks = random.sample(comma_heavy, 10)

numeric = [
    (i, t)
    for i, t in rows_raw
    if re.search(r"\d", t) and t.endswith(".") and ascii_clean(t) and 8 <= len(t.split()) <= 40
]
num_picks = random.sample(numeric, min(10, len(numeric)))

# paragraphs: consecutive LJ rows joined (3-5 sentences)
paras = []
idx = 0
random.seed(490)
while len(paras) < 20 and idx < len(rows_lj) - 6:
    n = random.choice([3, 4, 5])  # noqa: S311 - deterministic benchmark sampling, not crypto
    group = rows_lj[idx : idx + n]
    idx += n + random.choice([5, 9, 13])  # noqa: S311
    text = " ".join(t for _, t in group)
    if ascii_clean(text) and all(t.endswith((".", "?", "!", ",", ";")) or True for _, t in group):
        paras.append((group[0][0] + f"+{n}", text))

PROBES = [
    ("q", "Hello, my name is Sumit. How are you?"),
    ("q", "Can you send the report today?"),
    ("q", "Do you want tea or coffee?"),
    ("q", "Where did you keep the invoice?"),
    ("q", "Is the meeting still on for Friday?"),
    ("e", "Wow, that was amazing!"),
    ("e", "Stop, that hurts!"),
    ("e", "What a fantastic result that was!"),
    ("l", "We need three things: patience, funding, and time."),
    ("l", "The kit includes a cable, a charger, a manual, and a case."),
    ("l", "Bring pens, paper, and a laptop to the workshop."),
    ("qt", "He said, I will call you tomorrow."),
    ("qt", "She asked, are we done yet?"),
    ("qt", "The manager said, ship it on Monday."),
    ("n", "I bought it for $49.99 yesterday."),
    ("n", "Call me at +91-9876543210."),
    ("n", "The meeting is on August 12, 2026."),
    ("n", "Version 2.5 is ready."),
    ("b", "OpenAI released the new model."),
    ("b", "IntelliAI and QwikCart signed the deal."),
    ("b", "NVIDIA and PostgreSQL support arrived."),
    ("a", "Mr. Smith called at 10 a.m."),
    ("a", "Dr. Rao joined the U.N. panel."),
    ("a", "The GMT offset changed, didn't it?"),
    ("d", "Uh, I mean, we could, you know, try again tomorrow."),
    ("d", "So, um, the report is, well, mostly done."),
    ("d", "I was going to say, actually, let's wait."),
]


def src(sid):
    return {"sentence_id": str(sid), "files": [], "genders": [], "duration_seconds": []}


rows = []
for fid, text in picks:
    rows.append(
        {
            "id": f"lj-sent-{fid}",
            "language": "en",
            "reference_text": text,
            "source": src(f"LJSpeech-1.1/{fid}"),
            "domain": "read-single",
        }
    )
for fid, text in comma_picks:
    rows.append(
        {
            "id": f"lj-comma-{fid}",
            "language": "en",
            "reference_text": text,
            "source": src(f"LJSpeech-1.1/{fid}"),
            "domain": "read-single",
        }
    )
for fid, text in num_picks:
    rows.append(
        {
            "id": f"lj-num-{fid}",
            "language": "en",
            "reference_text": text,
            "source": src(f"LJSpeech-1.1/{fid}"),
            "domain": "read-single",
        }
    )
for fid, text in paras:
    rows.append(
        {
            "id": f"lj-para-{fid}",
            "language": "en",
            "reference_text": text,
            "source": src(f"LJSpeech-1.1/{fid}"),
            "domain": "read-paragraph",
        }
    )
KINDS = {
    "q": "question",
    "e": "exclamation",
    "l": "list",
    "qt": "quoted",
    "n": "numeric",
    "b": "brand",
    "a": "abbreviation",
    "d": "disfluency",
}
for kind, text in PROBES:
    rows.append(
        {
            "id": f"probe-{kind}-{PROBES.index((kind, text)):02d}",
            "language": "en",
            "reference_text": text,
            "source": src(f"authored-m49/{KINDS[kind]}"),
            "domain": "authored-probe",
        }
    )
# spontaneous slice: boss DRAFT reference, split into 3 chunks at sentence marks
sents = re.split(r"(?<=[.!?])\s+", BOSS_REF)
third = max(1, len(sents) // 3)
for i in range(3):
    chunk = " ".join(sents[i * third : (i + 1) * third if i < 2 else len(sents)])
    rows.append(
        {
            "id": f"boss-spont-{i}",
            "language": "en",
            "reference_text": chunk,
            "source": src("m48-boss-audio/DRAFT-founder-verification-pending"),
            "domain": "spontaneous",
        }
    )

dataset = {
    "name": "en-punct-eval",
    "version": 1,
    "task": "punctuation-restoration",
    "description": (
        "Frozen English punctuation benchmark (M49). Sources: LJSpeech-1.1 "
        "normalized transcripts (public domain; read speech), authored M49 "
        "probes, and the M48 boss-audio DRAFT reference (spontaneous; human "
        "verification pending). Annotation policy: reference punctuation is "
        "the corpus text verbatim (LJ), authored per standard English "
        "conventions (probes: quoted speech uses comma-introduction without "
        "quote marks since STT emits none; abbreviation periods kept; "
        "disfluencies comma-separated), and the M48 draft policy for the "
        "spontaneous slice. Marks in scope: . , ? ! per punct_slots@v1; "
        "scoring ruler punct_slots@v1 UNCHANGED."
    ),
    "rows": rows,
}
OUT.write_text(json.dumps(dataset, ensure_ascii=False, indent=1), encoding="utf-8")
print("rows:", len(rows), "->", OUT)
