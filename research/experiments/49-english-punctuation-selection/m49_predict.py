# M49 — candidate predictions on en-punct-eval@v1 (CPU, word-copy
# decoding: original tokens verbatim + predicted marks appended).
# Uses the FROZEN evaluation module for input-strip and invariant.
import json
import statistics
import sys
import time
from pathlib import Path

REPO = "/mnt/d/Sumit Projects/IntelliAI Platform"
sys.path.insert(0, REPO + "/ml/evaluation/src")
from intelliai_evaluation.punctuation import (  # noqa: E402
    apply_marks,
    invariant_holds,
    strip_punctuation_for_input,
)

DATASET = Path(REPO + "/ml/evaluation/punctuation/datasets/en-punct-eval-v1.json")
OUTDIR = Path.home() / "m49/out"
OUTDIR.mkdir(parents=True, exist_ok=True)
MODELS = Path.home() / "m49/models"

import hashlib  # noqa: E402

data = json.loads(DATASET.read_text(encoding="utf-8"))
DATASET_SHA = hashlib.sha256(DATASET.read_bytes()).hexdigest()
ROWS = data["rows"]

QUESTION_STARTERS = {
    "who",
    "what",
    "when",
    "where",
    "why",
    "how",
    "is",
    "are",
    "was",
    "were",
    "do",
    "does",
    "did",
    "can",
    "could",
    "will",
    "would",
    "should",
    "shall",
    "may",
    "am",
    "have",
    "has",
}


def predict_noop(text):
    return text


def predict_rules(text):
    words = text.split()
    if not words:
        return text
    mark = "?" if words[0].lower() in QUESTION_STARTERS else "."
    slots = [[] for _ in range(len(words) + 1)]
    slots[len(words)] = [mark]
    return apply_marks(text, slots)


class HFTagger:
    """Generic word-copy decoder over a token-classification model."""

    def __init__(self, local_dir, label_style):
        import torch  # noqa: F401
        from transformers import AutoModelForTokenClassification, AutoTokenizer

        self.tok = AutoTokenizer.from_pretrained(local_dir)
        self.model = AutoModelForTokenClassification.from_pretrained(local_dir)
        self.model.eval()
        self.id2label = self.model.config.id2label
        self.style = label_style  # 'fullstop' or 'felflare'
        if label_style == "felflare":
            # rpunct's hardcoded label order (the HF config only has
            # LABEL_n placeholders) - WEB-RESEARCHED from rpunct source.
            rp = [
                "OU",
                "OO",
                ".O",
                "!O",
                ",O",
                ".U",
                "!U",
                ",U",
                ":O",
                ";O",
                ":U",
                "'O",
                "-O",
                "?O",
                "?U",
            ]
            self.id2label = dict(enumerate(rp))

    def _marks_for_labels(self, label):
        if self.style == "fullstop":
            # labels: '0', '.', ',', '?', '-', ':'
            return label if label in (".", ",", "?", "!") else None
        # felflare: e.g. 'OU','!O','.O',',U','?O' — first char punct or O
        mark = label[0]
        return mark if mark in (".", ",", "?", "!") else None

    def punctuate(self, text):
        import torch

        words = text.split()
        if not words:
            return text
        slots = [[] for _ in range(len(words) + 1)]
        window, overlap = 180, 20
        start = 0
        while start < len(words):
            chunk = words[max(0, start - (overlap if start else 0)) : start + window]
            base = max(0, start - (overlap if start else 0))
            enc = self.tok(
                chunk,
                is_split_into_words=True,
                return_tensors="pt",
                truncation=True,
                max_length=512,
            )
            with torch.no_grad():
                logits = self.model(**enc).logits[0]
            pred = logits.argmax(-1).tolist()
            word_ids = enc.word_ids(0)
            last_tok_for_word = {}
            for ti, wi in enumerate(word_ids):
                if wi is not None:
                    last_tok_for_word[wi] = ti
            for wi, ti in last_tok_for_word.items():
                gi = base + wi
                if gi < start and start > 0:
                    continue  # overlap region: keep earlier prediction
                label = self.id2label[pred[ti]]
                mark = self._marks_for_labels(label)
                if mark and gi + 1 < len(slots):
                    slots[gi + 1] = [mark]
            start += window
        return apply_marks(text, slots)


def run_system(name, fn):
    preds, bad = [], 0
    t0 = time.perf_counter()
    for row in ROWS:
        source_input = strip_punctuation_for_input(row["reference_text"])
        out = fn(source_input)
        ok = invariant_holds(source_input, out)
        if not ok:
            bad += 1
        preds.append(
            {"id": row["id"], "input": source_input, "predicted_text": out, "invariant": ok}
        )
    wall = time.perf_counter() - t0
    payload = {
        "system": name,
        "dataset_sha256": DATASET_SHA,
        "invariant_failures": bad,
        "wall_s": round(wall, 2),
        "predictions": preds,
    }
    (OUTDIR / f"predictions-{name}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(
        name,
        "done:",
        len(preds),
        "rows,",
        bad,
        "invariant failures,",
        round(wall, 1),
        "s",
        flush=True,
    )


def perf(name, fn):
    import resource

    lj = [r["reference_text"] for r in ROWS if r["id"].startswith("lj-para")]
    corpus_words = " ".join(strip_punctuation_for_input(" ".join(lj)).split()[:2000]).split()
    ladder = {}
    for n in (100, 300, 700, 1200, 2000):
        text = " ".join(corpus_words[:n])
        walls = []
        for _ in range(5 if n <= 300 else 3):
            t0 = time.perf_counter()
            out = fn(text)
            walls.append(time.perf_counter() - t0)
        ok = invariant_holds(text, out)
        ladder[n] = {
            "p50_s": round(statistics.median(walls), 3),
            "max_s": round(max(walls), 3),
            "invariant": ok,
            "out_words": len(out.split()),
        }
        print(name, n, "words:", ladder[n], flush=True)
    rss_mib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    (OUTDIR / f"perf-{name}.json").write_text(
        json.dumps({"system": name, "ladder": ladder, "peak_rss_mib": round(rss_mib, 1)}, indent=1),
        encoding="utf-8",
    )


def main():
    which = sys.argv[1]
    if which == "noop":
        run_system("no-op", predict_noop)
    elif which == "rules":
        run_system("rules", predict_rules)
    elif which == "felflare":
        m = HFTagger(str(MODELS / "felflare-bert"), "felflare")
        run_system("felflare-bert", m.punctuate)
        perf("felflare-bert", m.punctuate)
    elif which == "kredor":
        m = HFTagger(str(MODELS / "kredor-punctuate-all"), "fullstop")
        run_system("kredor-xlmr-base", m.punctuate)
        perf("kredor-xlmr-base", m.punctuate)
    elif which == "fullstop":
        m = HFTagger(str(MODELS / "fullstop-large"), "fullstop")
        run_system("fullstop-xlmr-large", m.punctuate)
        perf("fullstop-xlmr-large", m.punctuate)
    print("PREDICT-DONE", which)


if __name__ == "__main__":
    main()
