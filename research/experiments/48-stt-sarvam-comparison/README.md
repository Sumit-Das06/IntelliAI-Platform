# M48 — IntelliAI STT vs Sarvam STT (research/evaluation only)

Report: `docs/research/2026-08-27-stt-intelliai-vs-sarvam.md`.
Nothing here touches production; the boss audio clip lives OUTSIDE git
(session scratchpad + WSL) per the privacy law — only its sha256 and
transcripts are recorded.

## Instruments

- `m48_score.py` — WER/CER on the FROZEN `ml/evaluation` wer.py ruler
  (punctuation cannot leak into WER by construction) + the NEW M48
  punctuation/boundary-F1 ruler v1 (per-word mark positions, marks
  `. , ? ! ।`) + word-level alignment dump.
- `m48_punct_probe.py` — EXPERIMENTAL Phase-15 probe: the pinned
  punct-cap-seg-47 artifact + shipped word-copy wrapper with an
  ENGLISH label map patched in research memory only (shipped v1 scope
  is Hindi danda/comma/question; production flag stays OFF).

## Evidence

- `evidence/manifest.json` — clip identity (sha256), fresh IntelliAI
  run conditions + latency, Sarvam capture conditions (UNKNOWNs
  labeled), silence/short-speech probe results.
- `evidence/reference-draft.txt` — DRAFT reference; 7 disputed spans
  await the founder's listen-through (table in the report §4).
- `evidence/intelliai-raw.txt` · `evidence/sarvam-boss.txt` ·
  `evidence/intelliai-punctuated.txt` — the three hypotheses.
- `evidence/boss-scores.json` — all scores + alignments.

## Headline

IntelliAI MEASURED: boss-clip WER 0.042 vs the DRAFT reference,
punctuation F1 0.000 (no English punctuation stage exists). Sarvam
QUALITATIVE (captured output only): near-identical words, fully
sentence-punctuated — **the gap is readability, not recognition**, and
that conclusion needs no Sarvam metric. Our own 47-lang model with an
English map reaches only 0.092 F1 — v1's Hindi scope does not
transfer. Recommendation: **M49 = English punctuation/readability
stage** under the M29/M30 gate discipline.

## Founder directive update (2026-08-27)

Sarvam API credentials are NOT available. Accordingly: the captured
playground output is QUALITATIVE evidence only, no Sarvam
WER/CER/latency is claimed anywhere, and every Sarvam-side measurement
is classified **BLOCKED - CREDENTIALS REQUIRED**. `m48_harness.py` is
the reproducible plug-in runner: the IntelliAI adapter works today,
the Sarvam adapter refuses loudly until a legitimate key exists, and
the same clip manifest reruns both when it does.

## IntelliAI-side battery (evidence/intelliai-battery.json)

- Latency ×5 on the 102 s clip: median 6.37 s (RTF 0.062), stable.
- Long ladder: 5 min WER 0.067, 9.5 min WER 0.058, zero truncation.
- Numbers/names synthetic round-trip: mean RT-WER 0.108 (names clean;
  QwikCart/OpenAI/Kubernetes/slash-date slip).
- Hinglish (hi route): English tokens come back TRANSLITERATED to
  Devanagari (0/8 Latin kept; "QwikCart" mangled) - recorded as a
  product/script-policy question, not scored as WER.
