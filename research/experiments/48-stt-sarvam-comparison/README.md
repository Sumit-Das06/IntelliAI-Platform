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

WER delta ≤ ~4 pts on n=1 (inside reference uncertainty); punctuation
F1 0.000 vs 0.794 — **the gap is readability, not recognition**. Our
own 47-lang model with an English map reaches only 0.092 F1 — v1's
Hindi scope does not transfer. Recommendation: **M49 = English
punctuation/readability stage** under the M29/M30 gate discipline.
