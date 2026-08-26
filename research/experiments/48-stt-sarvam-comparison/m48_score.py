# M48 — boss-audio scoring: WER/CER on the FROZEN wer.py ruler,
# punctuation & sentence-boundary F1 on a NEW M48 ruler (v1), and a
# word-level alignment dump. Research-only; no production import paths
# are modified.
import json
import sys
from pathlib import Path

sys.path.insert(0, "ml/evaluation/src")
from intelliai_evaluation.wer import normalize_words, word_error_rate

PUNCT = ".,?!।"  # . , ? ! danda
BOUNDARY = ".?!।"


def cer(reference: str, hypothesis: str) -> float:
    # M48 ruler: char-level Levenshtein over the SAME frozen word
    # normalization, words joined by single spaces.
    a = " ".join(normalize_words(reference))
    b = " ".join(normalize_words(hypothesis))
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] / max(len(a), 1)


def punct_positions(text: str, marks: str) -> set[tuple[int, str]]:
    """Map each mark to (index of preceding normalized word, mark)."""
    out = set()
    word_i = 0
    in_word = False
    for ch in text.lower():
        if ch.isalnum():
            if not in_word:
                word_i += 1
                in_word = True
        else:
            in_word = False
            if ch in marks:
                out.add((word_i, ch))
    return out


def f1(ref: set, hyp: set) -> dict:
    tp = len(ref & hyp)
    p = tp / len(hyp) if hyp else (1.0 if not ref else 0.0)
    r = tp / len(ref) if ref else (1.0 if not hyp else 0.0)
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return {
        "precision": round(p, 4),
        "recall": round(r, 4),
        "f1": round(f, 4),
        "ref_marks": len(ref),
        "hyp_marks": len(hyp),
        "matched": tp,
    }


def align_dump(ref_words, hyp_words):
    import difflib

    ops = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=ref_words, b=hyp_words).get_opcodes():
        if tag == "equal":
            continue
        ops.append(
            {
                "op": tag,
                "ref": " ".join(ref_words[i1:i2]),
                "hyp": " ".join(hyp_words[j1:j2]),
                "ref_pos": i1,
            }
        )
    return ops


def main():
    base = Path(sys.argv[1])
    ref = (base / "reference-draft.txt").read_text(encoding="utf-8")
    systems = {
        "intelliai_raw": (base / "intelliai-raw.txt").read_text(encoding="utf-8"),
        "sarvam_saaras_v4": (base / "sarvam-boss.txt").read_text(encoding="utf-8"),
    }
    punct_file = base / "intelliai-punctuated.txt"
    if punct_file.exists():
        systems["intelliai_plus_punct_stage"] = punct_file.read_text(encoding="utf-8")

    ref_words = normalize_words(ref)
    out = {
        "reference_status": "DRAFT - awaiting human verification (founder listens)",
        "reference_words": len(ref_words),
        "systems": {},
    }
    for name, hyp in systems.items():
        w = word_error_rate(ref, hyp)
        row = {
            "wer": round(w.wer, 4),
            "cer": round(cer(ref, hyp), 4),
            "sub": w.substitutions,
            "ins": w.insertions,
            "del": w.deletions,
            "hyp_words": w.hypothesis_words,
            "punctuation": f1(punct_positions(ref, PUNCT), punct_positions(hyp, PUNCT)),
            "boundary": f1(punct_positions(ref, BOUNDARY), punct_positions(hyp, BOUNDARY)),
            "word_diffs_vs_ref": align_dump(ref_words, normalize_words(hyp)),
        }
        out["systems"][name] = row
        print(
            name,
            "WER",
            row["wer"],
            "CER",
            row["cer"],
            "punctF1",
            row["punctuation"]["f1"],
            "boundaryF1",
            row["boundary"]["f1"],
        )
    (base / "boss-scores.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print("SCORES-DONE")


if __name__ == "__main__":
    main()
