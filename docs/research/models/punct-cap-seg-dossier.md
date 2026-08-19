# punct_cap_seg_47_language (1-800-BAD-CODE) — Dossier

| | |
|---|---|
| **Stage** | Gate 3+ complete (benchmarked M29A/M29B/M29C; runtime-integrated behind a disabled flag, M30) |
| **Gate 1** | **PASS** — `apache-2.0` verified at source (HF tags + card, 2026-08-19); not gated; no remote code required (plain ONNX + sentencepiece files) |
| **Status** | Approved for Adoption (capability implemented; PRODUCTION ACTIVATION PENDING its own promotion decision) |
| **Capability** | punctuation-restoration (text post-processing; first non-transcription dossier) |

> **Labels:** **[FACT]** verified at source · **[CLAIM]** publisher/third-party statement ·
> **[INFERENCE]** reasoning, not evidence.

## 1. Identity

- Repo `1-800-BAD-CODE/punct_cap_seg_47_language`, revision
  `1b9d51fc7989ebc61e844d407d9dadd08ff4ba28` **[FACT]**. Files:
  `punct_cap_seg_47lang.onnx` (232,986,305 B, sha256 `640d91c0…0df4`),
  `spe_unigram_64k_lowercase_47lang.model` (sha256 `1bc15b6e…af47`),
  `config.yaml` (sha256 `30eb8e05…5b84f2`) — all pinned as IntelliAI
  artifact `punct-cap-seg-47@v1` (seeded, never downloaded at runtime).
- IDENTITY NOTE **[FACT]**: the `punctuators` alias `pcs_47lang` resolves
  to THIS repo; the M28 document's attribution to
  `xlm-roberta_punctuation_fullstop_truecase` was wrong and was corrected
  in M29A.

## 2. Architecture

6-layer / 512-d bidirectional transformer, 64k lowercase sentencepiece,
max sequence 128; four argmaxed heads (pre-punct, post-punct, truecase,
sentence-boundary) **[CLAIM: card; FACT: I/O verified against the ONNX
graph in M29B]**. IntelliAI uses ONLY the post-punct head, through its
own word-copy decoder — the upstream text reconstruction (which destroys
rare Latin tokens as `<unk>`) is never used.

## 3. Languages

47 claimed incl. Hindi and English **[CLAIM]**; Hindi danda is a native
label **[FACT: label table]**. IntelliAI scope: Hindi route only (v1).

## 4. Licensing (Gate 1, verified 2026-08-19)

Apache-2.0 at source **[FACT]**. Commercially usable; fits the
permissive-only law. Upstream `punctuators` package is Apache-2.0 but
prototype-grade — NOT a runtime dependency (vendored wrapper instead).

## 5. Runtime and deployment profile

onnxruntime CPU + sentencepiece, in-process, one shared session
(`services/stt-runtime/engines/punctuation.py`). MEASURED (dev box,
M29B/M30): warm load 0.88 s; 600 s-tier restore 0.45 s (decoder share
<0.001 s); RSS peak ≈ 428 MiB. Fail-open stage; artifacts hash-verified
at startup; enabled deployments refuse to start unseeded.

## 6. Quality evidence (IntelliAI's own benchmarks — the only numbers that count)

hi-punct-eval@v3 through the PRODUCTION wrapper (M30, v1 mark scope
।,",",?): read-paragraph boundary F1 0.7441 (R 0.9313); spontaneous
text-ratified-51 micro F1 0.5733, boundary F1 0.7222; comma F1
0.39/0.43; questions 21/30 overall, 91.3% on lexically-cued, 0/12 false
positives; word invariant 100% everywhere; edge corruption 0/22.
**All six founder-approved gates PASS.** Card metrics (danda F1 96.94 on
their news test) remain **[CLAIM]**, never load-bearing.

## 7-13. Strengths / weaknesses / risks (compressed)

- Strengths: word-safe by construction under our decoder; fast; small;
  finds ~93% of mid-text boundaries (the product need rules can't touch).
- Weaknesses: news-register training (author: "unlikely to be of
  production quality" **[CLAIM]** — our gates measure what matters);
  over-segmentation precision ~0.62 on read paragraphs; NO "!" label;
  intonation questions unrecoverable from text (structural).
- Risks: upstream abandonment costs nothing (files pinned, wrapper
  vendored); argmaxed outputs expose no probabilities (tuning =
  post-filters only).

## 14. Open questions

Audio/native review of the 9 flagged spontaneous rows; long spontaneous
dictation references; Hinglish beyond probe level; production-box
re-ladder before activation.

## 15. Strategic value

Closes the punctuation gap the E3 promotion exposed, engine-agnostically,
with zero client changes and zero billing impact — and its outputs plus
human corrections feed the flywheel for a possible future E-series
punctuated fine-tune.
