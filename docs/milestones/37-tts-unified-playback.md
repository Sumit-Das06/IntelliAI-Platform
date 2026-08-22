# Milestone 37 — Unified Kokoro TTS Stream Playback

| | |
|---|---|
| **Status** | COMPLETE — one generation = one playback session = one audible source, structurally enforced; M36 streaming and quality fully preserved |
| **Date** | 2026-08-22 |
| **Evidence** | `research/experiments/37-unified-playback/evidence/` · structural pins in `test_console.py` |

    STREAMING BACKEND CHANGED: NO   (zero server-side diffs)
    FRONTEND PLAYBACK FIXED: YES
    ONE PLAYER GUARANTEE: YES       (structural, observable, pinned)
    DUPLICATE PLAYBACK: FIXED
    WEB E2E VERIFIED: YES
    PRODUCTION ENABLED: NO
    HOSTINGER: NO

    FINAL CLASSIFICATION: A — UNIFIED PLAYBACK READY

## 1. The bug and its root cause

M36 shipped two independent playback paths for one generation: the
live AudioContext stream AND an HTML `<audio>` element. Two duplicate
windows existed: (a) at stream end the blob was attached to the
element **while the scheduled tail was still sounding** (the context
closed on a timer ~150 ms after attach) — pressing the element's Play
in that window doubled the audio; (b) the element (with the PREVIOUS
generation's audio) stayed visible and playable during a NEW
generation's stream. Two owners, no shared state — the classic
two-booleans bug the spec names.

## 2. The new architecture — PlaybackSession

One explicit state machine, one owner, one identity:

    IDLE → GENERATING → STREAMING ⇄ PAUSED → COMPLETED
                       ↘ STOPPED / ERROR (from any live state)

- **Session identity**: a monotonic `activeSessionId`; every async
  callback (stream pump, completion timer, pause/resume promises,
  error handlers) first checks `isStale(session)` and no-ops if a
  newer session exists — a stale stream can never schedule audio,
  flip UI state, or revive playback (race case F).
- **One audible owner per phase**: during GENERATING/STREAMING/PAUSED
  the session's AudioContext is the only mechanism and Pause/Stop the
  only controls — the replay `<audio>` element is HIDDEN and has NO
  src. On COMPLETED, order is law: `teardown()` closes the live
  context FIRST, the blob attaches SECOND (the order is test-pinned) —
  there is no instant where both mechanisms can sound.
- **Pause/Resume**: `ctx.suspend()/ctx.resume()` on the SAME session —
  the schedule timeline freezes with the clock, so resume continues
  exactly where paused; the fetch keeps buffering ahead meanwhile.
- **Stop** (race case B): abort the fetch, `.stop()` every scheduled
  source, close the context, clear the completion timer, state
  STOPPED — the stale-check then blocks any late chunk or completion
  from resurrecting audio. Server-side, the M36 pool law stops the
  producer within one chunk.
- **Replay** (Phases 5-6): COMPLETED shows the element with the
  session's assembled WAV (real sizes) — replay is a local blob, never
  a re-fetch; seek/pause/play are the element's own, and the live
  context no longer exists. Download uses the same blob and is
  unavailable until COMPLETED (Phase 11).
- **Generate→Generate** (race case A): `newSession()` tears the old
  session down completely (abort, sources, context, timer, blob URL
  revoked) before the new one begins — only the newest session
  survives, and only it may touch the UI.
- **Belt-and-braces**: even if the replay element somehow starts while
  a live context exists, its `play` event STOPS the live session —
  one-audible-source is enforced, not assumed.
- **Observable proof** (Phase 16): the page maintains
  `window.__iaiPlayback = {sessionId, state, audibleSources}` on every
  transition and shows it in the dev view — `audibleSources ≤ 1` is
  the checkable invariant (DevTools-verifiable; presence and structure
  pinned by test). Nothing relies on "I didn't hear it twice."

## 3. Resource cleanup (Phase 20)

Per session teardown: AbortController aborted, every BufferSource
stopped and dropped, AudioContext closed, completion timer cleared,
prior blob URL `revokeObjectURL`'d before a new one is minted. Repeated
Generate→Complete cycles hold exactly one context and one blob URL at
a time by construction.

## 4. Regressions — MEASURED, none

| Check | M36 | M37 | Verdict |
|---|---|---|---|
| Stream TTFA (300/700/1200/1990 chars) | 0.45-1.31 s band | **478 / 805 / 860 / 820 ms** | preserved ✅ |
| Whole-body path (fallback + default) | — | unchanged rows in the same matrix | ✅ |
| Quality (25-probe streamed, judge) | 0.0650 / 0.0248 | **0.0650 / 0.0248** | identical ✅ |
| Backend contract / billing / auth | — | **zero server-side changes** in this milestone | ✅ |

## 5. Verification

- Page served through the HTTPS edge with all M37 markers (state
  machine, session guards, observable).
- test_console pins: the six states, session-identity symbols, the
  replay-only-on-COMPLETED toggle, the teardown-before-src order, the
  observable, suspend/resume — the architecture cannot be silently
  reverted. api suite green; nothing else touched.
- Founder click-through (2 min): Generate → while Playing… press
  Pause/Resume/Stop; Generate twice fast; after Completed press the
  player's play (replay, no network) — and watch
  `window.__iaiPlayback.audibleSources` stay ≤ 1 throughout.

## 6. Sarvam UX comparison (Phase 24, behavior only)

Sarvam's playground exposes exactly one output card whose single
control owns the streaming session and later the finished clip. The
Speech Studio now matches that behavior — live controls during the
stream, one seekable clip after — implemented entirely on our stack
(AudioContext + session state machine), nothing copied.

## 7. Limitations / next

- Pause during GENERATING (before first audio) is disabled — pausing
  nothing is a no-op by design.
- After STOPPED, partial audio is not offered for replay (regenerate
  instead) — a deliberate simplification, documented.
- No JS unit-test runner exists in this stack; the guarantees are
  enforced by structural pins + the runtime observable + the founder
  protocol. A browser-automation harness (Playwright) remains a
  candidate for a future milestone.
- Production unchanged; next milestone queue unchanged (Hindi TTS
  serving path or TTS production launch — founder's pick).
