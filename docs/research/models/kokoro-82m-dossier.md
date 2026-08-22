# Kokoro-82M (hexgrad) — Dossier

| | |
|---|---|
| **Status** | **Approved for Adoption** — the incumbent behind `intelliai-tts` since v0.4 (M3, 2026-08-03); this dossier retro-fills the framework-v0.2 requirement (adoption predates the dossier law) and carries the M32 re-examination |
| **Capability** | speech_synthesis |
| **Ledger** | [MODEL_LEDGER.md](../MODEL_LEDGER.md) → speech_synthesis → Kokoro-82M |
| **Written** | 2026-08-20 (M32) |

## 1. Identity

| Fact | Value | Verified |
|---|---|---|
| Upstream | `hexgrad/Kokoro-82M` (Hugging Face) | 2026-08-03 at adoption; re-verified 2026-08-20 |
| Revision measured at M32 | `f3ff3571791e39611d31c381e3a41a3af07b4987` (hub main; research venv) | 2026-08-20 |
| Served artifact | `kokoro-82m` v1 — 4 files, SHA-256-pinned in `services/tts-runtime/.../engines/kokoro.py`, re-hashed every boot | repo |
| Files | `kokoro-v1_0.pth` (327 MB, sha `496dba11…`), `config.json`, voice packs `af_heart.pt` / `am_michael.pt` (~523 KB each) | repo |
| Release | v1.0, 2025-01-27 | source |
| Params | 82 M | source |

## 2. Architecture

StyleTTS2-lineage decoder (no diffusion at inference) + ISTFTNet vocoder;
phoneme input (~510 per pass); 24 000 Hz mono output. G2P is external
(`misaki`): native dictionary G2P for English (ja/ko/zh/vi also native),
**espeak-ng for everything else — including Hindi**. Voices are ~510-row
style-embedding packs (one per voice), selected per request — a voice is
an artifact file, exactly the platform's Voice-Asset abstraction.

## 3. Languages

- **English**: shipped since M3, espeak-free (misaki native, `fallback=None`).
- **Hindi**: 4 upstream voices — `hf_alpha`, `hf_beta` (F), `hm_omega`,
  `hm_psi` (M) — all upstream grade **C**, trained on **minutes-scale**
  data (upstream VOICES.md, 2026-08-20). Requires espeak-ng `hi` G2P.
- Arabic: none. (8 languages / 54 voices total in v1.0.)

## 4. Licensing

| Component | License | Class |
|---|---|---|
| Weights, `kokoro` pip, `misaki` | Apache-2.0 (source, 2026-08-03; re-verified 2026-08-20) | CLEAR |
| espeak-ng chain (needed for Hindi; optional EN OOV fallback) | GPL-3.0 | in-process: **banned** (M3 §8, poison-stub + GPL-free image, build-verified). Subprocess **binary behind an exec boundary** (ffmpeg posture): the M3-blessed compliant shape — M32 measured phoneme parity (below) |
| Training data | "permissive/non-copyrighted audio" incl. synthetic audio from third-party models (provenance note, upstream card) | informational |

## 5. Runtime and deployment profile (MEASURED)

| Fact | M3 (2026-08-03) | M32 (2026-08-20, current source) |
|---|---|---|
| Quality, frozen 25-case corpus EN slice (whisper judge) | round-trip WER 0.072 | **0.0759** (reproduced) |
| Extended EN probe set via gateway | — | WER 0.0773 / CER 0.0556; median RTF 0.279 |
| RTF | 0.19–0.21 native / 0.25–0.37 container | same band (container 2.39 GiB RSS idle-loaded) |
| TTFB via gateway | 814 ms (1 sentence) / 2237 ms (122 chars) — PRD FAIL beyond one sentence | unchanged design (unstreamed); chunk-level TTFA measured ~0.6–1.8 s in research runs |
| Memory | ~2.0 GiB flat to c=20 | 2.39 GiB container idle-loaded |
| Startup | cold 38 s / warm 7 s | warm start: load 5.1 s + warmup 0.8 s (rebuilt image) |

## 6. M32 Hindi evidence (research spike — upstream pipeline, scratch venv)

Round-trip through OUR promoted E3 Hindi judge (gateway, frozen
normalization, `intelliai_evaluation.accuracy`):

| Slice | hf_alpha (F) | hm_omega (M) |
|---|---|---|
| All 24 hi probes | WER 0.1615 / CER 0.1190 | WER 0.1635 / CER 0.1183 |
| Clean slice (20 probes, no digits/currency/dates) | **WER 0.0834 / CER 0.0347** | — |
| Timing | median RTF 0.38, TTFA (first chunk) median 1.78 s | (timing run invalidated by concurrent load; quality valid) |

Context: E3's CER on *real* Hindi speech is 0.11612 — clean synthetic
speech round-trips at 0.035, i.e. the TTS adds almost no
unintelligibility on non-numeric text. Number/currency probes conflate
verbalization with error (digits verbalized correctly as words; ₹ symbol
DROPPED and comma-broken — a text-normalization gap, not an acoustic one).

**espeak parity** (subprocess CLI vs in-process GPL chain, 29 hi/mixed
texts): 16/29 byte-identical; every mismatch is one of three mechanical
transforms (punctuation preservation, `(en)/(hi)` switch-marker
stripping, misaki's diphthong table `aɪ→I`, `eɪ→A`) — no divergent
phonemization observed. The compliant subprocess path is an engineering
task, not a research risk.

**EN OOV quantified**: espeak-fallback-ON halves the extended-probe EN
error (WER 0.0344 vs 0.0773) — the dictionary-only path drops OOV words
("IntelliAI", "Kavya" — measured, reproducing the M3 founder finding).
The same subprocess component that un-gates Hindi can close this.

## 7-13. Strengths / weaknesses / risks (compressed)

- **Strengths**: quality/cost champion at 82 M; one process serves many
  languages (voices are +0.5 MB packs); already integrated, hash-pinned,
  GPL-free EN path proven in production shape; Apache-2.0 end-to-end
  (espeak aside); deterministic; chunk-level streaming possible.
- **Weaknesses**: Hindi voices are C-grade / minutes-trained (naturalness
  unproven — founder listening pending); **no released training
  pipeline** → not an ownership lineage, voices cannot be fine-tuned;
  dictionary-only EN G2P drops OOV words absent espeak; single-maintainer
  upstream; torch runtime is the heaviest of the small candidates
  (ONNX port exists upstream-community — unbenchmarked here).
- **Risks**: upstream stagnation (v1.0 is 2025-01; low activity);
  espeak-ng version pinning must be exact for phoneme stability;
  danda not in the runtime's sentence splitter (one-line fix when Hindi
  ships).

## 13b. M35 addendum (2026-08-20)

The §6-7 weaknesses are now largely CLOSED in the shipped runtime
(v0.2.0, local/staging): OOV drops fixed via the espeak exec-boundary
fallback (trap WER 0.0659 through the production path), normalization
v1 occupies the pipeline seam, chunk-merging halves short-text latency
(median wall 748 ms), voices renamed (`english-female`/`english-male`,
aliases kept), billing characters-only, stale-image smoke in place.
Community ONNX was measured and DECLINED (RTF 1.078 / WER 0.0956 via
the wrapper; RAM win real — a first-party export stays a PROPOSED
lever). Determinism documented: stochastic sampling, stable durations.

## 13c. M38 addendum (2026-08-22) — Hindi re-measured, all four voices

The M38 fixed Hindi benchmark (61 probes incl. long-text ladder,
Devanagari numerals, phone/time/slash-date traps) re-ran the upstream
Hindi path for ALL FOUR voice packs — solo runs, E3 judge, evidence at
`research/experiments/38-hindi-tts-selection/`:

| Voice | hi clean RT-WER/CER | median RTF | peak RSS |
|---|---|---|---|
| hf_alpha (F) | 0.0593 / 0.0193 | 0.169 | 2.28 GiB |
| hf_beta (F) | 0.0710 / 0.0222 | 0.181 | 2.21 GiB |
| hm_omega (M) | 0.0653 / 0.0255 | 0.185 | 2.37 GiB |
| **hm_psi (M)** | **0.0450 / 0.0178** (best) | 0.183 | 2.25 GiB |

M32's comparable slice reproduces (alpha 0.1634/0.1191 vs 0.1615/0.1190).
Two NEW facts that supersede §6's optimism:

1. **Silent long-text truncation**: the upstream KPipeline (`lang h`)
   saturates at ~23.9 s audio (~510 phonemes) for EVERY input beyond
   ~300-350 chars — 683/1189/1897-char ladder texts all emit the same
   duration, no error raised. M32's 545-char "zero failures" probe was
   already truncated, unnoticed. Danda-aware chunking is therefore a
   CORRECTNESS requirement for the serving milestone, not a latency fix.
2. **In-process espeak chain is not thread-safe**: concurrent phonemize
   calls corrupt espeak's shared buffer (measured crash). Irrelevant to
   the production shape (isolated subprocess per call) — recorded so
   nobody ever "optimizes" the subprocess back in-process.

Also measured: espeak `hi` over the M35 subprocess transport works
as-is (stdin, `-q --ipa -v hi`; `(en)/(hi)` markers appear exactly as
the M32 parity table predicted); Devanagari numerals ०-९ are MISREAD
by espeak-hi (४५ → "पंद्रह सौ") — a normalization-layer rule, not an
engine fix. M38 recommendation: extend the incumbent to Hindi (Option
A re-confirmed) — see the M38 report §21/§25.

## 14. Open questions

1. Founder listening verdict on the 4 Hindi voices (naturalness ≠
   intelligibility; intelligibility is now measured — hm_psi leads).
2. ONNX build: RAM/RTF gains vs torch (PROPOSED optimization).
3. Long-term: which owned lineage eventually replaces it (see M32 §22 —
   the VITS-class in-house Hindi voice experiment).

## 15. Strategic value

The serve-track engine: it buys EN+HI (+6 more languages' ceiling) in
one small process while the ownership lineage matures elsewhere. Its
replaceability is the architecture's proof: engine module + registry
row, nothing else.
