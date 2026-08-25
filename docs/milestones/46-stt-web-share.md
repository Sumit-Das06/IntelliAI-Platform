# Milestone 46 — STT Web Share (native transcript sharing)

| | |
|---|---|
| **Status** | SHIPPED (web console) — classification **A. STT SHARE READY** |
| **Date** | 2026-08-25 |
| **Scope** | Web UI only: one Share button on `/console/playground`. No backend, model, API-contract, billing, consent, TTS, mobile, routing, or deployment change. |
| **Files** | `static/console/studio.html` (button + share logic) · `tests/test_console.py::TestSttShare` |

## 1. What shipped

The Transcript panel gains a **📤 Share** button. Clicking it opens the
browser/OS **native share sheet** (`navigator.share`) with the payload:

- title: `IntelliAI STT Transcript`
- text: the transcript exactly as displayed — nothing else.

The OS decides the destinations (WhatsApp/Telegram/Mail/… wherever the
platform offers them); the page never hardcodes or guarantees any
particular app, and no per-app integration exists.

## 2. The behavior laws

- **Visibility**: ships hidden; shown only when a non-empty transcript
  is displayed AND no transcription is in flight; hides again on empty
  results or while a new request runs; reacts live to edits
  (`input` listener + `refreshShareButton()` at submit/settle).
- **What travels**: `var shareText = transcript.value.trim()` captured
  AT CLICK TIME — a correction (saved or not) shares the corrected
  text; a transcript changed mid-share still sends the click-time
  snapshot. No app-side truncation exists (`slice`/`substring` absent,
  test-pinned).
- **Cancel is not an error**: `AbortError` returns silently. The words
  "Share failed" appear nowhere.
- **Fallback chain** (runtime feature detection, never device
  sniffing): no `navigator.share` → clipboard copy + *"Sharing isn't
  supported here. Transcript copied to clipboard."* · unexpected share
  failure → clipboard rescue + *"Sharing didn't work here — transcript
  copied to clipboard instead."* · no clipboard either → *"Sharing
  isn't supported in this browser."* No technical error is ever shown.
- **Privacy**: share is a user-initiated export of the user's own
  text. It does NOT depend on the contribution checkbox (that governs
  storage, not the user's ability to share), performs **no network
  call**, and the payload can never carry API keys, request/sample
  IDs, model names, language codes, or developer details — the share
  call's argument list is test-pinned to `title` + `shareText` only,
  and the page-wide engine-vocabulary ban (M31 public-product rule)
  already covers the rest.
- **Accessibility**: a real `<button>` (Tab-reachable, Enter/Space
  activatable by nature) with `aria-label="Share transcript"`, an icon
  PLUS text label, and a `role="status"` live region for feedback.
  Existing focus styles apply unchanged.
- **Responsive**: one small button inside the existing `.btn-row`
  pattern — no overflow, no layout change at mobile widths (the same
  row primitive every other page uses).

## 3. Verification (2026-08-25, local production-shaped stack)

- Served page carries the feature (curl against the running gateway);
  the inline script passes `node --check` (syntax).
- Real E2E through the real gateway with web headers:
  - **English**: `fs-trap/en-general-01.wav` → *"The quick brown fox
    jumps over the lazy dog near the river bank."* — Share enabled.
  - **Hindi**: production TTS (hindi-female) → STT round-trip returns
    Devanagari text into the textarea; Share passes it verbatim
    (UTF-8 end to end; content accuracy is the STT model's known
    posture, untouched here).
  - **Long**: 30 s clip → 476-char transcript flows through the same
    path; the app passes the full string.
- **Tests: 43/43 green** on `test_console.py`, including the 7 new
  `TestSttShare` tests (A-L mapped: visibility law, clean payload,
  snapshot, AbortError silence, fallback chain wording, frontend-only
  + consent-free block, no-internal-vocabulary in the call,
  accessibility, no-truncation) and the standing public-product leak
  sweep over the page.
- **Native sheet interaction** (opening/choosing a target) is an
  OS-level surface a headless session cannot click; support varies by
  browser (Chrome/Edge on Windows and Android, Safari on iOS/macOS
  expose it; Firefox desktop generally does not). This is exactly why
  the fallback exists, and why runtime detection — not device
  detection — gates the path. Recorded as the platform-dependent
  limitation it is.

## 4. Limitations (documented, by design)

- Destination availability is platform-controlled; nothing is
  guaranteed per-app and the page never claims otherwise.
- Some platforms cap share-intent payload sizes (OS-level, undocumented
  precisely); the app itself never shortens the text.
- Desktop browsers without Web Share get the clipboard experience.

## 5. Declarations

| Claim | Answer |
|---|---|
| SHARE FEATURE | **YES** |
| NATIVE WEB SHARE | **YES** (where the browser exposes it; runtime-detected) |
| CLIPBOARD FALLBACK | **YES** |
| HINDI SHARE | **YES** (Devanagari verbatim) |
| ENGLISH SHARE | **YES** |
| LONG TRANSCRIPT | **PASS** (no app-side truncation, test-pinned) |
| ACCESSIBILITY | **PASS** (name + keyboard + live region) |
| PRODUCTION ROUTING | **UNCHANGED** |
| HOSTINGER | **UNCHANGED** |
