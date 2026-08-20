# Milestone 36 — Kokoro English TTS True Streaming + Low Time-To-First-Audio

| | |
|---|---|
| **Status** | COMPLETE — progressive audio delivery on the existing endpoint; TTFA now length-independent (~0.4-1.3 s) where whole-body scaled to 27+ s; zero quality regression; local Web + HTTPS edge verified |
| **Date** | 2026-08-20 |
| **Evidence** | `research/experiments/36-tts-streaming/evidence/` · new suites across runtime-core / tts-runtime / api |

    STREAMING IMPLEMENTED: YES
    TTFA IMPROVED: YES            (5-21x on 300-2000 char inputs)
    WEB E2E VERIFIED: YES         (HTTPS edge streams progressively; §9)
    AUDIO CONTINUITY VERIFIED: YES (byte-equality law + seam metrics; §7)
    PRODUCTION ENABLED: NO
    HOSTINGER: NO

    FINAL CLASSIFICATION: A — STREAMING READY FOR STAGING PROMOTION

## 1. Problem

M35's whole-body response meant TTFA = total synthesis: a 1200-char
paragraph made the listener wait ~12-16 s before ANY sound. M35's
internal chunk merging improved totals, not delivery — the audio still
left the server only when finished.

## 2. Architecture decision (Phase 1-3)

**HTTP chunked transfer on the EXISTING `POST /v1/audio/speech`**, an
additive `stream: bool = false` request field (both the public schema
and the runtime contract — ADR-0016 additive rules; default false is
byte-identical v1 behavior, pinned by test). Options rejected:
WebSocket (a second transport for no gain — ADR-0020 called the raw
body "chunk-ready" from day one), MediaSource (Chrome's MSE does not
accept WAV/PCM), a new endpoint (contract sprawl).

**Audio format**: the streaming body is a standard 44-byte WAV header
whose two size fields carry the streaming placeholder (0xFFFFFFFF — the
long-standing "WAV still being written" convention), then raw PCM16
mono 24 kHz exactly as synthesized. Same content-type, same bytes a
whole-body caller would get, minus foreknowledge of length. The
browser player never trusts the size fields; players that do read to
end-of-stream anyway.

## 3. Server path (Phases 4-5)

- **runtime-core** gains `WorkerPool.run_stream(produce, buffer_items)`
  — the admission law applied to progressive work: one slot for the
  stream's life, a BOUNDED handoff buffer (slow client ⇒ backpressure
  on the producer, never memory growth), consumer departure cancels the
  producer between items (`StreamCancelled` raised inside `emit`; the
  test proves a 10 000-item producer stops within a buffer's worth).
  Pure lifecycle machinery — items are opaque; no model vocabulary.
- **Engine seam** gains `synthesize_stream(text, voice, speed, emit)`.
  The reference engine emits per character — deterministic multi-chunk,
  so CI proves the core law exactly: **concatenated stream chunks are
  byte-identical to the whole-body audio**. Kokoro emits per bounded
  phoneme piece through the SAME `_render` loop `synthesize` uses (one
  code path, two chunk plans).
- **Chunk plan (Phase 5)**: streaming uses a deliberately SMALL first
  chunk — whole sentences up to `INTELLIAI_TTS_STREAM_FIRST_CHUNK_CHARS`
  (default 90; word-wrapped if one sentence exceeds it) — then the M35
  merge budget (300) for the rest. Measured: TTFA plateaus at
  first-chunk cost regardless of text length (§6) at a total-time cost
  of +3-6 % vs whole-body (more model passes) — the trade the milestone
  exists to make. Whole-body requests keep the exact M35 plan.
- **Priming**: the route synthesizes the FIRST piece *before* sending
  headers — so overload, invalid input, unknown voice, and
  first-piece engine failure all remain ordinary JSON errors, and TTFB
  honestly equals first-audio-ready. The pre-flight envelope rides the
  usual header carrying identity + characters (the billable unit, known
  up front); `duration_seconds` is 0.0 BY CONTRACT in streaming mode —
  the gateway measures delivered bytes instead.

## 4. Gateway path + billing (Phases 12-14)

`SpeechService.synthesize_stream` mirrors every pre-flight law, then
forwards bytes while counting them. **The streaming billing law**
(documented on the public schema): the request's CHARACTERS are billed
once audio delivery starts — F1, generation not socket completion; a
customer who disconnects mid-stream abandoned delivered work and is
billed; a RUNTIME failure mid-stream instead writes the non-billable
capacity row (our fault). Failures before first audio bill nothing.
The ledger write happens out-of-band after delivery ends
(`UsageRecorder.record_streamed_success` — the failure path's
machinery, applied to streamed success; at-most-once still guaranteed
by request-id uniqueness), shielded from client-disconnect
cancellation. Speed/chunk count/duration never change the bill —
test-pinned across modes.

## 5. Browser (Phases 10-11, 24)

The Speech Studio streams by default: `fetch` + `ReadableStream`
reader, first 44 bytes skipped, PCM scheduled GAPLESSLY on an
`AudioContext` created inside the click gesture (autoplay-safe —
speech starts without a second click; states: Generating… → Playing… →
Completed/Stopped/Failed). Stop aborts the fetch, silences scheduled
sources, and closes the context — the server's producer stops within
one chunk (the pool law). After completion the page assembles the
delivered PCM into a REAL WAV (true sizes) for the replay player and
the Download link. Browsers without `AudioContext`/`ReadableStream`
fall back to the exact M35 whole-body flow. Dev view shows request id,
status, and measured first-audio milliseconds.

## 6. TTFA results (Phases 7-9) — MEASURED, best-of-3, production-shaped local stack

| Text | whole-body TTFA | **stream TTFA** | speedup | totals (whole → stream) |
|---|---|---|---|---|
| short (22c) | 575 ms | 569 ms | 1.0× | 575 → 574 ms |
| question (12c) | 500 ms | 508 ms | 1.0× | ≈ equal |
| 120 chars | 1 884 ms | **927 ms** | 2.0× | 1 887 → 2 204 ms |
| 300 chars | 4 256 ms | **815 ms** | 5.2× | 4 282 → 4 820 ms |
| 700 chars | 9 586 ms | **1 257 ms** | 7.6× | 9 600 → 10 464 ms |
| 1200 chars | 16 354 ms | **1 296 ms** | 12.6× | 16 385 → 16 928 ms |
| 1990 chars | 27 592 ms | **1 308 ms** | **21.1×** | 27 658 → 28 728 ms |

(An earlier lighter-load pass measured stream TTFA 445-805 ms on the
300-1200 rows — treat 0.4-1.3 s as the machine's band; both passes are
in the task record, the recorded JSON is the conservative complete one.)

**Phase-9 verdict against the PROPOSED <1 s target**: **PASS** for
short/normal text (≤300 chars: 0.45-0.93 s across both passes);
**CLOSE** for long text (0.8-1.3 s — the plateau is first-chunk-bound
and length-independent, which is the design working; sub-second on
long text needs a smaller first chunk or faster hardware, both
measurable knobs). Nothing hidden: whole-body TTFB≠TTFA conflation is
avoided by definition (TTFA = first byte past the WAV preamble).

## 7. Continuity (Phases 6, 16-17)

- **Transport adds nothing**: reference-engine law — streamed chunks
  concatenate byte-identically to whole-body audio (CI-pinned).
- **Seam metrics** (20 ms RMS windows < −50 dBFS, interior only):
  stream ≈ whole across the matrix (22/22, 24/24, 501/493, 783/782,
  1307/1297); the 120/300-char rows show slightly more quiet windows
  (114 vs 96, 213 vs 185) — the different chunk plan renders slightly
  different sentence-boundary pauses; these are model-rendered pauses,
  not gaps (no zero-runs injected; durations differ ≤ 0.5 s on 19-119 s
  audio). No clicks/overlaps/duplication mechanism exists: chunks are
  butt-joined PCM from the same continuous plan.
- **Long-text law**: 1990-char input streams completely (119.05 s
  audio, no truncation); the 2039-char untrimmed input is REFUSED by
  the 2000-char law before any stream begins.

## 8. Quality regression (Phase 18) — NONE

Same 25-probe M33 trap set, same judge, streamed end to end:
**RT-WER 0.0650 / RT-CER 0.0248** vs M35 whole-body 0.0659 / 0.0251 —
statistically identical (target ≤ 0.08 holds with room). OOV names,
dates, currency, punctuation rows all round-trip as in M35.

## 9. Local E2E through the HTTPS edge (Phase 23)

Through Caddy (`https://localhost`, production-shaped stack):
`stream:true` returned **TTFB 1.20 s with total 3.43 s for 13.1 s of
audio** — the edge passes chunks through as they arrive (no buffering
observed; no Caddyfile change needed). The Speech Studio page serves
via the edge, leak-clean. The founder's click-through:
`https://localhost/console/speech` → Generate → speech begins while
the rest is still synthesizing; Stop halts it mid-sentence.

## 10. Concurrency (Phase 19) — streamed, c=1/2/4/8, zero errors

TTFA p50: 0.98 s / 3.16 s / 3.31 s / 6.35 s — under saturation a
queued stream's first chunk honestly waits behind executing work (pool
2+8 unchanged); memory stays bounded by the 4-chunk buffer per stream
(backpressure test-pinned); no incomplete streams, no refusal anomalies.
Not production capacity claims — MEASURED LOCAL.

## 11. Security (Phase 20)

No new auth path (same bearer flow); no text on disk; the subprocess
posture unchanged; cancellation bounded at every layer (browser abort →
gateway generator close → runtime producer stop — each proven by test);
no envelope/internal headers on the public stream; engine vocabulary
still banned everywhere; version bumped to **0.3.0** and the tts-smoke
floor raised with it (a pre-streaming image now FAILS the smoke).

## 12. Tests / limitations / next

- New: runtime-core `run_stream` laws (5) · runtime streaming suite
  (10: header, byte-equality, envelope, JSON-error paths, chunk plan,
  defaults) · gateway streaming suite (4: chunked shape, billing law,
  mid-stream break, defaults) · console pins (streaming path + states +
  fallback). Totals: runtime-core 46 · tts-runtime 111 · api 651 ·
  evaluation 677 · contract 46 — green; mypy strict clean; smoke OK.
- Limitations, stated: streamed responses carry no trailing metadata
  (duration is measured, not declared); `speed ≠ 1` streams fine but
  the browser download reflects delivered PCM only; Android/iOS remain
  whole-body clients by design (additive field invisible to them —
  contract-compatible, test-pinned).
- Production remains OFF everywhere; promotion rides the TTS launch
  gate. **Next milestone**: unchanged queue — Hindi TTS serving path
  (M32 §25) or TTS production enable-promotion, founder's pick;
  streaming now removes the PRD-TTFB blocker from both.
