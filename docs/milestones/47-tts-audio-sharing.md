# Milestone 47 — TTS Web Audio Sharing

| | |
|---|---|
| **Status** | SHIPPED (web console) — classification **A. TTS AUDIO SHARE READY** |
| **Date** | 2026-08-25 |
| **Scope** | Web UI only: one Share button in the Speech Studio's Audio panel. No backend, streaming, PlaybackSession, billing, routing, or deployment change. |
| **Files** | `static/console/speech.html` (button + share logic) · `tests/test_console.py::TestTtsAudioShare` |

## 1. What shipped

The replay panel (`[audio player]` row) gains **📤 Share** next to
Download WAV. Clicking it opens the browser/OS **native file share
sheet** with:

- title: `IntelliAI TTS Audio`
- files: `intelliai-speech.wav` — the **exact completed WAV blob
  Download uses** (same name convention, same bytes; never re-encoded,
  never re-fetched, no second synthesis, no backend endpoint).

Destinations (WhatsApp/Telegram/Mail/Files/…) are the platform's
decision; the page never hardcodes or guarantees any app.

## 2. The behavior laws

- **Only completed audio** — the button lives INSIDE `#player-wrap`,
  which the M37 PlaybackSession shows exclusively in `COMPLETED`
  (`playerWrap.classList.toggle("hidden", state !== "COMPLETED")`), so
  IDLE / GENERATING / STREAMING / PAUSED / **STOPPED** / ERROR all
  hide Share through the EXISTING state machine — no second state
  machine, and partial/stopped audio is never shareable.
- **Current session only** (Generate → Generate safety): `newSession()`
  clears `completedBlob` the instant a new generation supersedes the
  old one; both completion paths stamp `completedSessionId`; the click
  handler snapshots blob+id and refuses when `sid !== activeSessionId`.
  Stale audio can never travel as if it were the new session's.
- **File-aware feature detection** (runtime, never device sniffing):
  `navigator.share` existing is NOT treated as file support —
  `navigator.canShare({ files: [file] })` gates the native path; the
  `File` construction itself is try/caught.
- **Fallback**: unsupported → *"Audio sharing isn't supported here.
  Download the WAV file instead."* · unexpected share failure →
  *"Couldn't share the audio. Please download the WAV file instead."*
  Download WAV remains fully functional and independent of Share.
- **Cancel is not an error**: `AbortError` returns silently; the words
  "Share failed" appear nowhere on the page.
- **Playback safety**: the share block performs no fetch, touches no
  `player.*`, creates no AudioContext, schedules nothing — test-pinned
  by token ban inside the block. The one-player law
  (`audibleSources <= 1`, `window.__iaiPlayback`) is untouched.
- **Privacy**: user-initiated export of the user's own generated
  audio; no network call, no analytics, no consent interaction; the
  share call's payload is test-pinned to `title` + `files` only (no
  model/voice/request/session vocabulary inside the call).
- **Accessibility**: real `<button>` with `aria-label="Share audio"`,
  icon PLUS text, `role="status"` live region for feedback — the M46
  conventions.

## 3. Verification (2026-08-25, local production-shaped stack)

- Inline script passes `node --check`; the served page carries all
  share markers after container sync + restart.
- Real gateway E2E (the same `/v1/audio/speech` the page calls):
  - **english-female** 4.2 s · **english-male** 4.8 s ·
    **hindi-female** 4.4 s · **hindi-male** 5.7 s — all four produce
    the completed-WAV artifact Share consumes; no voice-specific code
    exists.
  - **Long audio**: 1999 chars streamed → 5,736,044 bytes ≈ **119.5 s**
    WAV. The page rebuilds the replay/download/share blob from the
    received PCM with a correct header (`wavBlobFromPcm`), so the
    shared file equals the generated audio byte-for-byte — no
    app-side truncation path exists.
  - One honest tooling note: a shell-side curl quirk mangled inline
    Devanagari during testing (fixed with a UTF-8 body file). The
    browser page always sends proper UTF-8 via `fetch`; nothing
    server- or page-side was wrong.
- **Tests: 50/50 green** on `test_console.py`, including 7 new
  `TestTtsAudioShare` tests (A-Q mapped: completed-only placement,
  exact payload + File name/type, canShare gating, silent AbortError,
  friendly fallbacks, stale-session guard with both completion paths
  stamped, playback/network token ban, accessibility) and the standing
  M31 public-product leak sweep over the page.
- **Native sheet interaction** is an OS surface a headless session
  cannot click: Chrome/Edge (Windows/Android) and Safari (iOS/macOS)
  expose file sharing on current versions; Firefox desktop generally
  does not — which is exactly what the runtime detection + fallback
  are for. Recorded as the platform-dependent limitation it is.

## 4. Limitations (by design)

- Destination availability is platform-controlled; no app guaranteed.
- Some platforms cap shared-file sizes at the OS level; the app never
  shortens the audio itself.
- Browsers without file-capable Web Share get the Download WAV path
  with a friendly pointer.

## 5. Declarations

| Claim | Answer |
|---|---|
| TTS AUDIO SHARE | **YES** |
| NATIVE FILE SHARE | **YES** (where the browser exposes it; canShare-gated) |
| DOWNLOAD FALLBACK | **YES** (unchanged, independent) |
| ENGLISH | **PASS** (both voices) |
| HINDI | **PASS** (both voices) |
| LONG AUDIO | **PASS** (119.5 s, byte-equal artifact) |
| STALE SESSION | **PASS** (blob cleared + session-id guard, test-pinned) |
| PLAYBACK REGRESSION | **PASS** (share block bans player/context tokens; one-player law untouched) |
| ACCESSIBILITY | **PASS** |
| PRODUCTION ROUTING | **UNCHANGED** |
| HOSTINGER | **UNCHANGED** |
