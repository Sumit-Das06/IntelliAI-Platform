# IntelliAI Platform — Project Progress & Architecture Report

**Current Capabilities, Measured Improvements & Roadmap**
1 September 2026 · Prepared by Sumit Das

---

## 1. Executive Summary

IntelliAI has progressed from early model experiments into a **measured,
bilingual voice platform**. Today the platform offers speech-to-text in
English and Hindi (including our **own fine-tuned Hindi model**),
text-to-speech in both languages with streaming playback, **live realtime
transcription** running on GPU, automatic punctuation, a user-correction
workflow that feeds our training-data flywheel, and transcript/audio
sharing — all behind one authenticated, metered API with a self-serve web
console.

The biggest recent progress: **realtime transcription became a real
product feature** (speak → text appears live → punctuated final), the GPU
serving stack was validated end-to-end, and a long-standing Hindi
reliability defect on CPU was **eliminated by GPU serving** — proven with
byte-identical repeated runs through the real customer API.

What is still pending is one thing only: **public production
infrastructure**. Everything runs and is demonstrable today on our
production-shaped local stack; nothing is deployed to a public server yet.

## 2. Project Journey

| Stage | What was solved | Why it mattered | Status |
|---|---|---|---|
| Platform foundation | API gateway, auth, metering, billing-safe usage records, model registry | A commercial service, not a script around a model | Done |
| STT foundation (EN) | Production media pipeline, worker pools, first public API | First customer-facing AI capability | Done |
| Evaluation infrastructure | Frozen benchmarks, immutable evidence ledger, speaker-disjoint Hindi test set | Every later claim is measured, never guessed | Done — in permanent use |
| TTS (EN, then HI) | Model selection by measurement, license firewall, true streaming | Second product line; voice output | Done (production-approved) |
| Own Hindi model (E1→E3) | Fine-tuning program; two honest failures, then a winner that forgot nothing | Hindi quality we own and can keep improving | Done — E3 is the promoted Hindi model |
| Punctuation (HI, then EN) | Raw speech text → readable text, words guaranteed unchanged | Readability is the difference users actually see | Staging |
| **Realtime STT (EN+HI)** | Live transcription over WebSocket with GPU inference | The flagship interactive experience | Staging-verified |
| GPU serving readiness | Capacity, failure drills, alerts, rollback, batch-on-GPU | Production promotion is now a config flip + one hardware purchase | Done (production-like verified) |

## 3. What We Have Built

| Capability | Current Status | What It Does | Key Evidence |
|---|---|---|---|
| English STT (batch) | **Production-approved**; serving on the staging stack | Upload/record → transcript (OpenAI-compatible API) | M2: WER 0.000 seed eval; M48: within ~4 pts of Sarvam on a real 102 s clip (n=1) |
| Hindi STT (batch) | **Production-approved** — our fine-tuned **E3** model | Hindi transcription incl. real conversational speech | M26 promotion; M55: 10.92% WER, 30 s real multi-speaker (GPU) |
| English punctuation | **Staging** (flag ON there, OFF in prod config) | "hello how are you" → "Hello, how are you?" | M49–M51; +45 ms on a 102 s clip |
| Hindi punctuation | **Staging** | Same for Hindi (danda, question marks) | M28–M30 |
| Realtime English STT | **Staging-verified**, GPU | Live text while speaking | M53–M55 |
| Realtime Hindi STT | **Staging-verified**, GPU | Live Hindi text while speaking | M53–M55 |
| English TTS | **Production-approved**, streaming | Text → natural speech, 2 voices | M35/M36: WER 0.0659, TTFA ~0.4–1.3 s |
| Hindi TTS | **Production-approved**, streaming | Hindi speech, 2 voices | M38–M40: clean RT-WER 0.045–0.062 |
| Transcript Share | Working (web share/clipboard) | One-tap share of results | M46 |
| TTS audio Share | Working (shares the exact WAV) | Share generated audio | M47 |
| Correction workflow | Working end-to-end | User fixes → consented training data | verified live in-browser (M51/M53/M55) |
| GPU serving | **Validated production-like**; config prepared, OFF | Realtime + Hindi batch on one 8 GB GPU | M55 |

*"Production-approved" = approved and configured in the repository and
serving on our production-shaped staging stack; no public server is
deployed yet (Section 10).*

## 4. Major Improvements (what's new)

1. **Live realtime transcription** — Before: speak, stop, wait. Now: text
   appears while you speak, in English and Hindi, with a punctuated final
   on Stop. Users see first words in ~0.3–1.1 s.
2. **Our own Hindi model** — Before: off-the-shelf models with weak Hindi.
   Now: a fine-tuned model (E3) we own, promoted on a speaker-disjoint
   benchmark, improving with every user correction.
3. **A Hindi reliability defect eliminated** — Before: the CPU service
   could return wildly different transcripts for the same long clip (2–94
   words). Now: GPU serving returns **byte-identical results** run after
   run through the real API.
4. **Readable transcripts** — Automatic punctuation in both languages with
   a hard guarantee: words are never added, removed, or changed.
5. **Low-latency GPU inference** — 1 second of Hindi audio: ~0.9–1.3 s on
   CPU vs **64 ms on GPU** — the headroom that makes live transcription
   possible at all.
6. **Voice output with streaming** — First audio now arrives in ~0.4–1.3 s
   regardless of text length (previously up to 27+ s for long text).
7. **Share + correction loop** — Transcripts and generated audio are
   shareable in one tap; corrections flow back (with consent) as training
   data — the platform gets better from use.
8. **Privacy & local processing** — All inference runs on our own
   machines; audio is never sent to third-party AI services; nothing is
   stored without consent; silence and cancelled sessions store nothing.
9. **Production-grade robustness** — Authentication before any audio,
   loud degradation instead of silent failure, one-switch rollback for
   every feature, and runnable alerts that we have proven fire.
10. **Measured everything** — Frozen benchmarks and an append-only
    evidence ledger mean every claim in this report traces to a recorded
    measurement.

## 5. STT Performance (measured)

**Batch (upload) quality** — model / dataset / hardware / mode / date:

| Metric | Value | Context |
|---|---|---|
| English WER | 0.000 | whisper-small · internal seed eval · CPU batch · M2 |
| English vs competitor | within ~4 pts of Sarvam | real 102 s founder clip, n=1 · M48 |
| Hindi WER (real 30 s, multi-speaker) | **10.92%** | E3 · IndicVoices-derived clip · GPU batch · M55 |
| Hindi WER (30 real clips, avg) | 15.6% | E3 · IndicVoices · GPU offline · M52H |

**Realtime (staging stack, RTX 5070, M54–M55):**

| Capability | English | Hindi |
|---|---:|---:|
| Realtime | Yes (GPU) | Yes (GPU) |
| First text | p50 1.10 s (20 runs) | **0.33–0.42 s** |
| Live update (p50) | 0.53 s | 0.62–0.79 s (all lengths to 10 min) |
| Finalization | p50 0.20 s | 0.77–1.43 s |
| Quality | 2.08% vs our batch text | within the batch model's band vs ground truth |
| GPU requirement | shared 8 GB card | shared 8 GB card |
| Concurrency (safe) | 2 sessions/GPU (4 = degraded burst) | shared |

## 6. Why GPU for Realtime?

Batch transcription can take its time — the user already finished
speaking. **Realtime must transcribe faster than speech arrives.**

- 1 second of Hindi audio: **CPU ~0.9–1.3 s** (barely keeping up, and it
  falls behind under load) vs **GPU 64 ms** (M52H, measured same day,
  same model).
- That ~15–20× headroom is what allows live updates every ~0.6 s, several
  simultaneous sessions, and instant finals.

CPU is not useless — it still serves background/batch workloads fine for
English. But for realtime (both languages) and for reliable long-form
Hindi, GPU is the requirement — and one 8 GB consumer-class GPU runs the
**entire** voice stack (both realtime engines + Hindi batch) in 5.3 GB
with headroom.

## 7. TTS Status

English and Hindi TTS are **production-approved** (repository state;
deployment pending with everything else): 2 English + 2 Hindi voices,
true streaming on the public endpoint, unified playback in the console,
and one-tap audio sharing.

- Quality (judged by round-trip through our own STT): English trap-set
  WER **0.0659** (hardened from 0.1247); Hindi clean RT-WER
  **0.045–0.062** across voices.
- Latency: first audio **~0.4–1.3 s regardless of text length**
  (streaming, M36) — previously scaled to 27+ s.
- Model choice, simply: **Kokoro** won on measurement — best
  quality-per-CPU-cost with a permissive license (a GPL component in its
  ecosystem is firewalled out at build time). **Qwen3-TTS** was evaluated
  honestly: its base model can beat Kokoro on clean text, but fine-tuning
  collapsed and its latency/serving economics lost — recorded, not
  adopted. Long Hindi text silently truncated in the upstream library —
  we found it, and our chunking makes long text correct.

## 8. English Punctuation

Raw STT output reads like `"hello sumit how are you today"`. The
punctuation stage turns it into `"Hello Sumit, how are you today?"` —
the single most visible readability improvement for users.

- Model: a compact INT8 punctuation model (selected in M49 on a frozen
  120-row benchmark against 3 alternatives).
- **Word-preservation guarantee**: the stage may only insert punctuation
  marks — a 100% word-copy invariant enforced by tests; if anything looks
  wrong it stands down and serves the raw text (fail-open).
- Overhead: **+45 ms** on a real 102 s clip; ~60 ms cold start.
- Status: **staging** (ON there, pinned OFF in production config until
  launch). Hindi punctuation (M30) has the same laws.

## 9. Realtime STT (the flagship)

**Old experience:** speak → stop → upload → wait → transcript.
**New experience:** press ⚡ → speak → words appear live → keep speaking →
Stop → punctuated final → correct/share — and hear your own recording
back in the player.

How it works (each stage exists because a measured problem demanded it):

```
Microphone → audio chunks (100 ms) → secure WebSocket
  → Gateway (authentication FIRST, then audio)
  → Voice-activity detection (silence costs nothing, prevents hallucination)
  → rolling audio window with smart commits (keeps quality over long sessions)
  → GPU STT engine (EN whisper-small · HI our E3)
  → live partial transcripts → display stabilizer (text only ever grows)
  → final transcript → punctuation → correction / share
```

Proven behaviors (staging, real browsers with real microphone path):
10-minute sessions stay clean; silence stores nothing; flooding the
service degrades **loudly** and still returns a complete final; two
sessions can never mix; killing the GPU mid-session produces an honest
error, never a hang.

## 10. Deployment Status (the honest picture)

| Area | Status |
|---|---|
| Local / staging (production-shaped stack: Docker, HTTPS edge, GPU host services) | **Live and fully working** — batch, realtime, TTS, console |
| Public production server | **NOT deployed** — repository is deployment-ready (rehearsed on clean Linux); VPS/hosting access pending |
| Production GPU | **Not provisioned** — validated production-like on RTX 5070; the purchase/provisioning decision is open |
| Realtime STT flags | OFF everywhere by default; production config prepared and deliberately wired to nothing |
| TTS | Production-approved in repository; deployment pending with the rest |
| Demos | Available NOW over a secure tunnel from the staging stack |

## 11. Current Blockers (real ones only)

1. **Production infrastructure** — no public VPS/GPU box exists yet.
   Impact: nothing customer-facing is live. Solution: provision a host
   with one 8 GB GPU; the deployment is rehearsed and the verification
   battery is scripted (~1 hour to re-run there). Status: awaiting the
   infrastructure decision.
2. **Production-box verification** — all GPU numbers are from the dev
   RTX 5070 (honestly labeled "production-like"). Must be re-measured
   once on the real box before enablement. Status: scripts ready.
3. **Latency acceptance** — English realtime first-text is ~1.1 s against
   a 1 s target; Hindi long-session finals reach ~1.4 s. Recommendation:
   acceptable for v1 launch; needs the founder's product sign-off.

## 12. Roadmap

**NOW** → Provision production infrastructure (VPS + GPU) and re-run the
scripted verification battery there.
**NEXT** → Founder-gated realtime STT production promotion (a prepared,
reviewed config switch) + Hindi batch moves to GPU serving (eliminates
the CPU defect for customers).
**AFTER THAT** → Scale-out policy per measured capacity; long-form Hindi
polish; grammar/broken-sentence correction (research defined, not yet
implemented); next language decisions (Arabic slots remain open).

## 13. What I Can Demo Today

| Demo | Where |
|---|---|
| English realtime STT (live text while speaking) | Staging, via tunnel — works in a normal browser |
| Hindi realtime STT | Staging, via tunnel |
| English + Hindi upload/record STT with punctuation | Staging, via tunnel |
| English + Hindi TTS with streaming playback | Staging, via tunnel |
| Transcript share, audio share, correction, replayable recording | Staging, via tunnel |
| Mobile-width console (phone browser) | Staging, via tunnel |

## 14. Management Takeaways

1. **Started** with model experiments; **built** a full bilingual voice
   platform — API, console, billing-safe metering, evaluation
   infrastructure, and our own Hindi model.
2. **The headline capability is live realtime transcription** in English
   and Hindi on GPU, verified end-to-end in real browsers.
3. **Everything is measured** — quality, latency, capacity, failure
   behavior — against frozen benchmarks with recorded evidence.
4. **Differentiation** is product engineering on top of models: realtime
   session architecture, punctuation with word guarantees, correction
   flywheel, privacy-first local inference, honest failure modes.
5. **One step remains to go live**: production infrastructure (VPS + one
   8 GB GPU), then a prepared promotion switch.

## Current Limitations

- No public production deployment yet; all metrics are staging/local.
- GPU numbers measured on one laptop-class RTX 5070 (production-like,
  not production-verified); realtime capacity = 2 sessions per such GPU.
- English realtime first-text ~1.1 s (target 1 s, narrowly missed).
- Grammar/sentence-repair is future work; languages beyond EN/HI are
  research-stage.

## Evidence References

| Claim area | Milestone documents |
|---|---|
| Hindi model fine-tuning + promotion | M23, M24, M26 |
| Hindi/English punctuation | M28–M30, M49–M51 |
| TTS selection → production approval | M32–M42 (esp. M35, M36, M38–M40, M42) |
| Competitor comparison | M48 |
| Realtime feasibility → product | M52, M52H, M53 |
| Realtime hardening + GPU readiness | M54, M55 |
| Architecture | `docs/architecture/`, `docs/ARCHITECTURE.md` |
| Measured model history | `docs/research/MODEL_LEDGER.md` |
