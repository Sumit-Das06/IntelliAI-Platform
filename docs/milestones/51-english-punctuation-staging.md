# Milestone 51 — English Punctuation Staging Promotion + Real Web E2E

| | |
|---|---|
| **Status** | STAGING VERIFIED — classification **A. ENGLISH PUNCTUATION STAGING VERIFIED** |
| **Date** | 2026-08-27 |
| **Scope** | Enable the M50 English punctuation stage on the local production-shaped (staging) stack only; validate through a REAL browser; prove rollback. Production stays OFF. |
| **Evidence** | `research/experiments/51-english-punctuation-staging/` (browser JSONs, 12 screenshots, verification.json) |

## 1. M50 hand-off

M50 shipped `punct-en-kredor@v1` (kredor/punctuate-all INT8 ONNX)
behind `INTELLIAI_STT_PUNCTUATION_EN_ENABLED` (default FALSE) with every
gate PASS except one recorded exception: the live-browser click-through.
M51 closes exactly that exception.

## 2. Staging flag (environment-specific, no defaults touched)

The M30 pattern, applied verbatim:

- `infra/compose/local-prod.yml` (staging): `INTELLIAI_STT_PUNCTUATION_EN_ENABLED: "true"`, languages `en,en-US,en-IN` — the ONLY committed deployment that enables it.
- `infra/compose/prod.yml`: `INTELLIAI_STT_PUNCTUATION_EN_ENABLED: "false"` — pinned explicitly so a stray dev variable can never enable it.
- Application defaults unchanged (still FALSE); nothing hardcoded.
- New guard test `test_english_punctuation_ships_off_in_prod_and_on_only_in_the_local_stage`; `prod-preflight.sh` refuses an enabled deployment without the seedable artifact; `prod-smoke.sh` requires `punctuation_en` readiness to MATCH the declaration in both directions.

Startup: `make local-prod-up` seeded `punct-en-kredor@v1` into the model
volume and the rebuilt stack came up ready:
`{"status":"ready","slots":{"whisper-small":"ready","qwen3-asr-0.6b-hi-ft-e3":"ready"},"punctuation":"ready","punctuation_en":"ready"}` —
Hindi stage untouched and still ready.

## 3. THE FINDING the browser E2E caught (and its fix)

The first battery showed **double punctuation on clean read speech**:
"Hello, my name is Sumit.. How are you??". Cause: **Whisper itself
fully punctuates clean speech**, and the M50 stage appended marks on
top. The boss clip (spontaneous WhatsApp speech — the M48 gap) arrives
bare, so M50's evidence never exposed this.

**Fix (stage law, test-pinned):** `engine_already_punctuated()` — when
any token of the raw transcript ENDS with a sentence mark (`.,?!;:`),
the engine's own punctuation stands and the stage does nothing
(no `raw_text`, no stage event). Token-final only, so intra-word marks
(`2.5`, `example.com`, `test@example.com`, `987-654-3210`) never count.
This is exactly complementary: Whisper punctuates clean read speech and
leaves spontaneous speech bare — the stage now applies only where the
readability gap actually is. Four new tests
(`TestEngineAlreadyPunctuated`); STT suite 228 passed. This is the only
runtime code change in M51.

## 4. Real browser E2E — PASS (the primary gate)

Playwright Chromium 151 against `https://localhost/console/playground`
(Caddy edge, internal CA) — the REAL page, real uploads, real clicks:

1. upload works (boss `.ogg` + 11 generated clips) ✓
2. transcribe works ✓  3. transcript appears ✓
4. punctuation visible on spontaneous audio ✓
5. words unchanged (verification below) ✓
6. Copy path ✓  7. Share ✓  8. Correction ✓

Screenshots: `evidence/screenshots/` (punctuated boss, raw rollback,
share note, saved correction, dev details, Hindi run, status page,
mobile 390 px, tablet 820 px).

## 5. Boss audio before/after (actual staging output, sha `117cba69…af635`)

BEFORE (flag OFF, browser):
> "see this is a text to which I generated from my speech okay and if
> you see it has taken the whole statement or speech as one statement
> so that's where we need to add punctuations and signs …"

AFTER (flag ON, browser):
> "see this is a text to which I generated from my speech. okay, and if
> you see it has taken the whole statement or speech as one statement.
> so that's where we need to add punctuations and signs where it
> understand where is the right fit, break the statement and then start
> so full stops, comma. all of those things should be there. …"

Same words, sentence boundaries added. Sarvam remains **QUALITATIVE
ONLY** — no Sarvam metrics anywhere.

## 6. Word invariant — PASS (100%)

- Boss ON vs OFF (browser): `depunct` streams EQUAL.
- Recovery run vs ON run: equal.
- Long-audio ladder: envelope `raw_text` vs served text — invariant
  TRUE on 30 s / 2 min / 5 min / 10 min.
- Battery clips: engine-punctuated → stage stands down → displayed ==
  raw trivially; no `..`/`,,`/`??` anywhere (`battery_no_double_marks`).

## 7-9. Copy / Share / Correction — PASS

- **Share** (M46): headless Chromium has no `navigator.share`, so the
  clipboard fallback executed — clipboard verified **equal to the
  displayed punctuated transcript** (never the raw).
- **Copy**: the transcript surface is the textarea itself plus Share's
  clipboard fallback; both carry the displayed text. (The only other
  copy buttons are the dev-details/code-example ones — unchanged, no
  second behavior added.)
- **Correction**: editor starts from the displayed punctuated text; a
  REAL edit was saved (`droughts → drafts`, the founder-disputed M48
  span) through `POST …/correction` and acknowledged. Backend
  provenance (raw → punctuated → human correction) is the M30 contract,
  pinned by `apps/api/tests/test_punctuation_provenance.py`.

## 10-11. English + Hindi regression — PASS

- English: flag OFF output **byte-identical** to the forced-timeout raw
  output; ON↔OFF word streams depunct-equal → WER unchanged by
  construction. Silence/short-speech behavior untouched (stage runs
  only on non-empty text, after chunk-merge).
- Hindi: same browser, `language=hi`, the E3 route — output
  "क्या आप कल ऑफिस आओगे? मुझे रिपोर्ट आज चाहिए।" is the EXISTING Hindi
  stage's work; the English stage never ran (M50 service proof + M51
  browser run; gating unit tests pin en/en-US/en-IN only, never "auto").

## 12. Long audio — PASS

Staging runtime, flag ON: 30 s → 36 ms, 2 min → 166 ms, 5 min → 404 ms,
10 min (595 s) → 611 ms of stage time; words 48/241/622/1223 — zero
truncation, invariant TRUE every run, no latency explosion.

## 13. Latency — PASS

Boss clip ×5 through the staging container: `punctuation_en` p50
**196.4 ms**, max 229 ms = **2.87% of inference p50** (~6.8 s) — the
proposed ≤10% gate passes ~3.5×. (The container CPU is slower than the
M50 host measurement of 45.2 ms — recorded honestly; no production SLA
claimed.)

## 14. Fail-open (live) — PASS

Temporary staging override `INTELLIAI_STT_PUNCTUATION_EN_TIMEOUT_MS=0.001`
(uncommitted compose override file): the browser still got HTTP 200,
the RAW transcript, and the normal "Done." status — no user-visible
technical error. Override removed; service recovered to punctuated
output (screenshots `boss-failopen.png` / `boss-recovered.png`).

## 15. Rollback — PASS

Flag OFF (staging override) → readiness reports
`punctuation_en: "disabled"`, browser shows the raw transcript,
**byte-for-byte identical** to the fail-open raw capture; Hindi
unaffected. Flag back ON → punctuated output returns. The flag is the
operational rollback, demonstrated live.

## 16. Security — PASS

The browser DOM (playground + status page) and every response body were
scanned: no `kredor`, no `punctuate-all`, no `punct-en-kredor`, no
artifact hash, no internal path, no engine name. Dev details show only
request id / sample id / response JSON per the existing contract.

## 17. UI / product status

`/console/status` is catalog-driven (`{"services":{"tts":…}}`) and makes
**no** English-punctuation production claim; the STT card's badge
follows the M31 law ("production" = launched service, not
infrastructure). No UI redesign; mobile (390 px) and tablet (820 px)
remain usable with Share/Save/transcript visible and no horizontal
scroll.

## 18. Production safety — VERIFIED

- production flag pinned `"false"` (+ guard test, preflight, smoke)
- no Hostinger, no DNS, no production server, no customer traffic
- git diff to production config = the one pinned-false line + comments
- full workspace suite, lint, mypy strict: green (commit gate)

## 19. Limitations

- On clean read speech the served punctuation is the ENGINE's own
  (stage stands down) — quality there is Whisper's, not kredor's.
- Capitalization remains out of v1 scope (punctuation marks only).
- Staging latency (~196 ms p50 on 102 s) reflects this laptop's
  container CPU; the production box will re-measure at promotion.

## 20. Verdict

| | |
|---|---|
| STAGING FLAG | **ON** |
| PRODUCTION FLAG | **OFF** |
| BROWSER E2E | **PASS** |
| BOSS AUDIO | **PASS** |
| WORD INVARIANT | **PASS** (100%) |
| COPY | **PASS** |
| SHARE | **PASS** |
| CORRECTION | **PASS** |
| HINDI REGRESSION | **PASS** |
| LONG AUDIO | **PASS** |
| FAIL-OPEN | **PASS** |
| ROLLBACK | **PASS** |
| PRODUCTION ENABLED | **NO** |
| HOSTINGER | **NO** |

**Classification: A. ENGLISH PUNCTUATION STAGING VERIFIED.**

Next milestone (NOT performed here, founder-gated): **English
punctuation production promotion** — re-measure on the production box,
flip `prod.yml` after its own gate battery and founder decision.
