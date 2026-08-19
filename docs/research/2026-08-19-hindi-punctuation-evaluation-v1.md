# Hindi Punctuation Evaluation v1 — Benchmark + Baselines (M29A)

| | |
|---|---|
| **Status** | EVALUATION COMPLETE — classification **B: evaluation promising, needs better data**; NOTHING integrated, production unchanged |
| **Date** | 2026-08-19 |
| **Benchmark** | `hi-punct-eval@v1` — 265 rows, frozen, sha256 `3fa83ddb98cb2aafc3814c2cf4a385d309f8f79c7cf90699f83baefe7434a154` |
| **Evidence** | `research/experiments/29a-hindi-punctuation-eval/` |
| **Follows** | [M28 architecture research](2026-08-19-hindi-punctuation-restoration.md) |

Labels: **VERIFIED FROM REPO** · **MEASURED** · **WEB-RESEARCHED** ·
**ESTIMATED** · **UNKNOWN** — same discipline as M28.

---

## 1. Why punctuation is needed

Simple Hinglish mein: E3 Hindi ke **words bilkul sahi** likhta hai, lekin
**viram-chinh ek bhi nahi** — na danda (।), na comma, na "?". Do sentence
bolo to ek lambi line milti hai. Dictation product ke liye ye adhoora
likhna hai. M28 ne architecture research kiya; M29A ka kaam tha: **pehle
properly NAAPO** — benchmark banao, baselines chalao, tabhi integration
ki baat karo.

## 2. The current E3 problem (recap, all MEASURED in M28)

- Training corpus v3: 14,224 Hindi rows, **0 punctuation marks**; 900
  English rows 100% punctuated → model ne wahi seekha.
- E3 on the frozen ASR eval: 0/153 clips with any punctuation. The
  whisper-small incumbent punctuated 56.2% — the switch to E3 was a
  regression on a dimension no gate measured.
- The CER/WER ruler is punctuation-blind (**VERIFIED FROM REPO**:
  category P → space in `normalization.py`), so punctuation quality was
  an unmeasured product dimension — until this milestone.

## 3. The evaluation dataset — `hi-punct-eval@v1`

**Frozen, separate from `stt-hi-public-eval@v1` (untouched).**

| Property | Value | Label |
|---|---|---|
| Source | google/fleurs, `hi_in` TEST split, `raw_transcription` column | VERIFIED (M28: the only punctuation-bearing column; `transcription` drops marks) |
| Source revision | `70bb2e84b976b7e960aa89f1c648e09c59f894dd` | MEASURED (HF API pin) |
| Source file | `data/hi_in/test.tsv`, sha256 `889e82e2…a729f`, 473,366 bytes — build refuses on drift | MEASURED |
| License | CC-BY-4.0 (verified 2026-08-19; same source family as the M23 English slice) | WEB-RESEARCHED |
| Rows | **265** (418 TSV rows; 153 duplicate re-reads merged — text-level benchmark scores each sentence once; every recording's audio identity retained on its row) | MEASURED |
| Punctuated rows | 264/265 | MEASURED |
| Reference marks | danda 81 · comma 267 · full stop 241 · "?" 1 · "!" 1 | MEASURED |
| Audio | NOT vendored (text-level benchmark); recoverable from the pinned revision for a future end-to-end phase | — |
| Manifest | `ml/evaluation/punctuation/datasets/hi-punct-eval-v1.json` | sha256 `3fa83ddb…4154` |
| Provenance | `ml/datasets/manifests/hi-punct-eval-v1.provenance.json` (existing sidecar pattern) | — |
| Style | READ speech; **mixed sentence enders** — the source itself writes both "।" (81) and "." (241) | MEASURED |

**Sentence-ending policy (documented, not silently normalized):**
references keep their marks VERBATIM. Per-mark scores treat "।" and "."
as different marks; the **sentence-boundary group** (।, ?, !, .) scores
them as the same event. Dono views report hote hain — style-mix ki wajah
se kisi ko chhupaya nahi, aur kisi restorer ko source ke apne style-drift
ki saza nahi milti.

**Two known biases, stated up front:** (a) read speech, not spontaneous
dictation; (b) rows are mostly SINGLE sentences — dono ka asar §14 mein.

## 4. Reference preparation

1. `raw_transcription` verbatim → NFC → whitespace collapsed. Punctuation
   preserved. Nothing else touched. (Schema-enforced: the manifest
   validator refuses unnormalized or empty references.)
2. Restorer input = reference minus punctuation:
   `strip_punctuation_for_input` — NFC, format chars (Cf) deleted,
   category P → space, collapse, **case preserved** (our ASR emits cased
   text). Deterministic, test-pinned.
3. Provenance records source, revision, file hash, split, dedup counts,
   and the reference field name.

## 5. Text-level evaluation (the PRIMARY benchmark)

```
punctuated reference ──strip──▶ input ──restorer──▶ output
                └──────────── compare marks by position ────────┘
```

ASR word errors is benchmark mein ghus hi nahi sakte — reference ke words
hi input hain. Isolates punctuation restoration quality from ASR quality,
exactly per the M28 recommendation.

## 6. Metrics — how positions are aligned

New evaluation-plane module: `intelliai_evaluation/punctuation.py`, ruler
**`punct_slots@v1`** (a NEW named ruler; the frozen accuracy rulers are
untouched — **VERIFIED FROM REPO**, no golden pin changed).

- **Alignment**: text → words + **slots**. Slot *i* = the gap after word
  *i* (slot 0 = before the first word). Words are the depunct sequence
  (NFC, casefold, Cf deleted, P → space). Reference aur prediction ke
  words agar identical hain to slots 1:1 align hote hain — koi fuzzy
  matching nahi. Words differ → the row is REFUSED (invariant failure),
  never partially scored.
- Marks in a slot are a multiset (`??` vs `?` counts honestly). Unscored
  punctuation (quotes, parens, hyphens…) is ignored **symmetrically** on
  both sides, so it can never flip a verdict.
- **PRIMARY: micro-averaged punctuation F1** over {।, ",", ?, !, "."} —
  TP/FP/FN summed over every slot and mark. Precision = jitne marks
  lagaye unme se kitne sahi; recall = jitne hone chahiye the unme se
  kitne lage; F1 = dono ka balance. No single misleading "accuracy"
  number exists anywhere in the harness.
- Secondary: per-mark F1 (danda, comma, ?, !, ".") and
  sentence-boundary F1. "?" aur "!" ke reference mein sirf 1-1 sample
  hai — **un F1 numbers ka koi statistical matlab nahi** (stated in
  every table below).
- Degenerate-zero convention: no predictions → precision 0; nothing
  expected → recall 0 (documented in code, test-pinned).

29 unit tests pin the whole thing: extraction, slot alignment, the
"." vs "।" policy, multisets, invariant, degenerate cases, determinism,
manifest schema + row count. (`ml/evaluation/tests/test_punctuation.py`)

## 7. The hard safety invariant

```
depunct(output) == depunct(input)
depunct = NFC → casefold → Cf DELETED → category P → space → collapse
```

(One refinement over M28's sketch: Cf characters are deleted, not
spaced — the `unicode_generic@v2` conjunct lesson, now test-pinned.)

This is a GATE, not a metric: **required pass rate = 100%.** A failing
row is counted and shown, never repaired, never silently scored. And the
gate earned its keep in its first real run — see §10.

## 8. Baseline 0 — NO-OP (the current production floor)

| Metric | Value |
|---|---|
| micro F1 / precision / recall | **0.0 / 0.0 / 0.0** |
| every per-mark F1, boundary F1 | 0.0 |
| invariant | **100%** (265/265) |

**MEASURED**, exactly as predicted. Ye aaj ka production hai: Hindi user
ko punctuation nahi milta. Improvement isi floor se naapa jayega.

## 9. Baseline 1 — SIMPLE RULES

The minimum honest rules (research instrument, ~15 lines): one final
ender per text — "?" if the text starts with a Hindi interrogative
(क्या/कौन/कब/…), else "।" for Devanagari, else ".". No internal
boundaries, no commas — deliberately.

| Metric | Value (MEASURED) |
|---|---|
| micro F1 | 0.1706 |
| danda F1 | 0.4220 |
| comma F1 | 0.0 (rules place no commas) |
| boundary F1 | **0.8942** |
| invariant | **100%** |

**The 0.8942 is a trap** — documented, not celebrated: benchmark rows are
mostly single sentences, so "put one mark at the end" is nearly always
right. The multi-sentence probe (§14) shows what happens where the
product actually lives: rules' boundary **recall collapses to 0.2687**.
Rules cannot find boundaries INSIDE text; that is the entire product
need. Limitation documented; the instrument stays research-only.

## 10. The lead model — identity, verification, results

**IDENTITY CORRECTION (important, honest):** the `punctuators` alias
`pcs_47lang` resolves to **`1-800-BAD-CODE/punct_cap_seg_47_language`**
— NOT `xlm-roberta_punctuation_fullstop_truecase` as the M28 document
stated. Every M28 measured number was produced by this model; the M28
attribution was wrong. Corrected here, in the ledger, and in the
evidence. (**MEASURED**: local cache snapshot == pinned revision.)

| Identity | Value | Label |
|---|---|---|
| Repo / revision | `1-800-BAD-CODE/punct_cap_seg_47_language` @ `1b9d51fc7989ebc61e844d407d9dadd08ff4ba28` | MEASURED (HF API + cache) |
| License | **Apache-2.0** (source tag + card, 2026-08-19) | WEB-RESEARCHED |
| Architecture | 6-layer / 512-d transformer + punct/truecase/seg heads; 64k lowercase sentencepiece; max 128 tokens/window; ~233 MB ONNX | WEB-RESEARCHED (card) + MEASURED (file size) |
| File integrity | onnx `640d91c0…0df4`, spm `1bc15b6e…af47` — asserted by the predictor before EVERY run | MEASURED |
| Author's own caveat | news-trained; "unlikely to be of production quality"; one prediction per subword (acronyms break) | WEB-RESEARCHED |
| Card's Hindi claims (their news test) | danda F1 96.94, comma F1 66.74 | WEB-RESEARCHED — never treated as our number |

**Results on hi-punct-eval@v1 (MEASURED):**

| Metric | Lead model | vs rules | vs no-op |
|---|---|---|---|
| micro F1 | **0.2421** (P 0.2351 / R 0.2496) | +0.0715 | +0.2421 |
| danda F1 | 0.2721 | −0.1499 | — |
| comma F1 | **0.3467** | +0.3467 | — |
| full-stop F1 | 0.0 (model writes ।, references often write ".") | — | — |
| "?" / "!" F1 | 0.0 / 0.0 (1 reference sample each — no statistical meaning) | — | — |
| boundary F1 | 0.7497 | −0.1445 (see §9's trap + §14) | — |
| **invariant** | **96.23% — 10/265 FAIL** | rules/no-op: 100% | — |

**The 10 invariant failures have ONE root cause (all 10 inspected):**
Latin acronyms/rare Latin tokens (MS, M16, pH, TMZ, CEP, A.D, GMT, METI,
TogiNet, Apple) come back as `<unk>`/`<Unk>` — the punctuators pipeline's
detokenizer destroys words it cannot re-emit. The card's own documented
acronym limitation, caught red-handed by our gate. Crucially: this is a
**pipeline text-reconstruction defect, not a classifier defect** — the
model only LABELS positions; an integration that copies INPUT words
verbatim and applies predicted marks (a **word-copy decoder**) makes the
invariant structural (100% by construction) and eliminates the `<unk>`
class entirely. That decoder is the non-negotiable integration contract
for M29B — it also removes the unwanted Latin truecasing (§15).

**Danda vs full stop:** the model consistently writes "।" after
Devanagari; FLEURS references often write "." (241 vs 81). Per-mark danda
F1 punishes the style mismatch; boundary F1 (0.7497) is the honest
position measure — exactly why the policy keeps both views.

**Examples (from `examples.json` — worst rows shown, not hidden):**

Good (row F1 1.0, marks and positions exact):
> ref: `यह बीमारी सूअरों के कारण होती है, जो बाद में मच्छरों के माध्यम से मनुष्यों में आती है।`
> out: `यह बीमारी सूअरों के कारण होती है, जो बाद में मच्छरों के माध्यम से मनुष्यों में आती है।`

Bad (invariant FAIL — word destroyed):
> ref: `रोलैंडो मेंडोज़ा ने अपनी M16 राइफल से पर्यटकों के ऊपर फायर किया।`
> out: `रोलैंडो मेंडोज़ा ने अपनी <Unk>16 राइफल से पर्यटकों के ऊपर फायर किया।`

All 10 good + 10 bad in the evidence.

## 11. The challenger — Cadence-Fast: **BLOCKED**

Per the Phase-14 rule: is the license legally clear enough to benchmark?
**No.** The card says MIT; the base model is Gemma-3-270M, and Google's
Gemma Terms of Use assert flow-down conditions on derivatives. No
relicensing statement, no LICENSE discussion, community tab empty
(checked 2026-08-19). Recorded **BLOCKED** in
`license-access-checks.json` and the ledger: **not downloaded, not
benchmarked, not adopted.** Unblocking needs legal review or upstream
clarification — that decision is the founder's, not this milestone's.

## 12. Real E3 output sanity (NOT a benchmark — no human references)

Lead model over the 151 non-empty REAL E3 hypotheses from the frozen ASR
eval result (**MEASURED**, `e3-sanity.json`):

- **Invariant: 151/151 PASS.** Real spontaneous Hindi dictation output
  contains almost no Latin acronyms — the `<unk>` failure mode never
  fired on the actual product distribution.
- Marks added: 262 danda, 209 comma, 21 "?" across 151 clips.
- Over-segmentation: 12/151 rows contain a ≤2-word "sentence"
  (the M28 "क्वालिटी।" pattern). Under-segmentation: 0/151 rows of >25
  words left with no sentence ender. Mean predicted sentence: 10.7 words.

## 13. Performance (development machine — NOT a production SLA)

**MEASURED** (`perf-tiers.json`, best of 3, 16 logical cores):

| Tier | Latency | Invariant |
|---|---|---|
| 5 s (260 chars) | 0.081 s | PASS |
| 30 s | 0.095 s | PASS |
| 120 s | 0.124 s | PASS |
| 300 s | 0.192 s | PASS |
| 600 s (7,340 chars) | **0.306 s** | PASS |

Cold load incl. download 36.3 s (once, M28); warm disk load **3.37 s**;
RSS: 469 MiB after load → **peak 616 MiB** through all tiers. Against the
M28 target (punctuation p95 ≤ 10% of STT p50): E3's real product-path
latency for a 30 s clip is ~9 s (M25 real sessions) — 0.095 s is ~1%.
**Target met with a wide margin on this machine; deploy-box numbers
remain UNKNOWN until M29B re-ladders there.**

## 14. Domain gap — what this benchmark can and cannot say

| Evidence class | What it shows |
|---|---|
| **Benchmark evidence** (hi-punct-eval@v1) | punctuation quality on READ, single-sentence, mixed-ender news-style text |
| **Multi-sentence probe** (derived: 88 paragraphs of 3 consecutive benchmark sentences; `multisentence-results.json`, MEASURED) | where the product lives — boundaries INSIDE text: lead boundary **R 0.9435 / P 0.6496 / F1 0.7695** vs rules **R 0.2687 / F1 0.4216**. The model finds 94% of mid-text boundaries; rules find 27%. Lead micro F1 0.2589 vs rules 0.0739. (Lead invariant 88.64% here — same `<unk>` acronym cause, more acronym exposure per paragraph.) |
| **Real E3 sanity** (§12) | on the true product distribution: word-safe (151/151), plausible segmentation, known over-segmentation rate |
| **UNKNOWN domain gap** | punctuation CORRECTNESS on spontaneous speech — no human-punctuated spontaneous Hindi references exist yet, so no number claims it. This is the v2 data gap. |

Ek line mein: read-speech benchmark par rules jeetne ka dikhawa karte
hain kyunki rows single-sentence hain; jaise hi text lamba hota hai
(product case), model 3.5× recall par aage nikal jaata hai — lekin uski
apni precision cost (0.65) aur `<unk>` defect ke saath. Spontaneous
correctness ke liye data hi nahi hai — that gap stays honestly UNKNOWN.

## 15. Hinglish / edge probes (sanity only — no statistical claim)

12 authored probes (**MEASURED**, `probes-results.json`): 11/12 invariant
PASS. Highlights: pure-Hindi question → `क्या आप कल ऑफिस आओगे?` correct;
Hinglish code-switch word-safe; digits preserved. Failures/warts:
**email FAIL** (`support@example.com` → `Support<UNK>Example…` — the
acronym/`@` defect again); URL gets an internal danda + odd truecasing
(`Intelliai.Example.।COM`); spoken digit sequences get comma-spam;
`डॉ` receives a danda after the honorific. All word-safe except the
email. Consequences → the M29B decoder must copy input words (kills the
truecasing warts and `<unk>`), and URL/email handling belongs in the v2
probe/eval design.

## 16. Decision matrix

On the frozen benchmark (265 rows) + the multi-sentence probe:

| Candidate | micro F1 | danda F1 | comma F1 | boundary F1 (1-sent / 3-sent) | Invariant (1-sent / 3-sent) | Latency 600s | RAM peak | Verdict |
|---|---|---|---|---|---|---|---|---|
| No-op | 0.0 | 0.0 | 0.0 | 0.0 / 0.0 | 100% / 100% | 0 | 0 | the floor — today's production |
| Rules | 0.1706 | 0.4220 | 0.0 | 0.8942 / **0.4216** | 100% / 100% | ~0 | ~0 | safe but blind inside text; not a restorer |
| **Lead ONNX** | **0.2421** | 0.2721 | **0.3467** | 0.7497 / **0.7695** | 96.2% / 88.6% (raw pipeline) | 0.306 s | 616 MiB | real signal, real defect; integration-viable ONLY behind a word-copy decoder |
| Cadence-Fast | — | — | — | — | — | — | — | **BLOCKED** (license) |

**Is the lead model good enough to justify runtime integration NOW?
Not yet.** The signal is real (boundary recall 0.94 where it matters,
commas from nothing, 151/151 word-safe on real E3 text), but: (a) the
raw pipeline fails the 100% invariant requirement — fixable by design,
but the fixed decoder must be built and re-measured, and (b) the only
frozen benchmark under-represents the product (single sentences, read
speech), so the decisive number — boundary quality on realistic text —
currently rests on a derived probe, not a frozen benchmark.

## 17. Proposed gates — **PROPOSED, NOT YET APPROVED**

Derived from the measured no-op floor, the lead results, and product
value; the founder approves or amends these in M29B:

| Gate | Proposed threshold | Basis |
|---|---|---|
| Word-preservation invariant | **100%** on benchmark v2 + probes + real-E3 set, structural via the word-copy decoder | the M28 contract; measured defect class |
| Sentence-boundary F1 (multi-sentence data) | ≥ 0.75, AND ≥ rules + 0.25 absolute | lead 0.7695 today with the defect rows excluded; rules 0.4216 |
| Sentence-boundary recall | ≥ 0.85 with precision ≥ 0.65 | lead 0.9435 / 0.6496 today; recall is the product need, precision the annoyance bound |
| Comma F1 (benchmark) | ≥ 0.30, else ship danda/? only (comma disable is one label drop) | lead 0.3467 today |
| Question probes | ≥ 80% correct on a ≥ 25-question probe set (to be built in v2 — the benchmark's single "?" cannot gate) | current 1-sample non-evidence |
| Latency | p95 ≤ 10% of route STT p50 per tier, re-measured on the deploy box | measured ~1% on dev |
| RAM | ≤ 700 MiB added per runtime process | measured peak 616 MiB |
| ASR untouched | CER/WER on `stt-hi-public-eval@v1` byte-identical with the stage on/off | ruler is punctuation-blind; any drift = words changed = FAIL |

## 18. Risks

- **Benchmark ≠ product**: v1 is read speech, single sentences, mixed
  enders. Anything gated only on v1 can pass while dictation quality
  disappoints. Mitigation: v2 data before integration gates (below).
- **`<unk>` word destruction** is measured and real (10/265; 1/12
  probes). The word-copy decoder removes the mechanism, but until it is
  built and re-measured this stays an open defect, not a solved one.
- **Over-segmentation** (12/151 real clips; probe P 0.65): users see
  extra dandas. Threshold tuning / minimum-sentence-length policy is
  M29B design space.
- **Comma subjectivity**: 267 reference commas are translators' style;
  comma F1 will never look like danda F1. The disable-path is cheap.
- **Model provenance**: a prototype-grade upstream (11 commits). The
  ONNX + spm files are pinned by hash and the wrapper will be vendored —
  upstream abandonment then costs nothing.
- **Ledger hygiene**: punctuation models now live in the ledger under a
  new capability group; dossier obligations kick in if any model moves
  beyond Researching.

## 19. Recommendation

**Classification: B — EVALUATION PROMISING, NEEDS BETTER DATA.**

Not A (integration now): the 100% invariant requirement is failed by the
raw pipeline, and the decisive product-shaped number lives in a probe,
not a frozen benchmark. Not C (rules better): rules' benchmark win is a
measured artifact — 0.2687 boundary recall on 3-sentence text is not a
product answer. Not D/E/F: the lead model is Apache-2.0, fast, small,
word-safe on the real E3 distribution, and finds 94% of mid-text
boundaries — the signal justifies the next data investment.

## 20. Exact next milestone (on approval)

**M29B-data — Hindi Punctuation Evaluation v2 + decoder prototype
(still evaluation-only, no production change):**

1. **Benchmark v2**: (a) a frozen multi-sentence set (deterministic
   paragraph construction from pinned sources — promote the §14 probe
   design to a frozen manifest); (b) a small human-punctuated
   SPONTANEOUS Hindi slice (founder decision: annotation budget/process
   — IndicVoices clips + one annotator + a written style guide); (c) a
   ≥25-question probe set; (d) URL/email/number edge rows.
2. **Word-copy decoder prototype** (research instrument): the model's
   mark predictions applied to input words verbatim → re-run every M29A
   measurement; invariant must read 100% everywhere by construction.
3. Re-run the decision matrix; if the §17 gates (founder-amended) pass
   on v2 → **M29B-runtime**: the M28 architecture (runtime post-merge
   stage, fail-open, hi-only, raw+punctuated contract, §14-C sample
   semantics) behind the full M28 §24 test battery.

---

Production behavior after M29A: **completely unchanged** (VERIFIED — the
only repo changes are the new evaluation module + tests, the frozen
benchmark + provenance, the ledger append, research instruments and
evidence, and this document). Hindi still serves unpunctuated; the
route, API, clients, metering, Speech Samples, and E3 are untouched.
