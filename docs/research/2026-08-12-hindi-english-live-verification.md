# Hindi & English STT — Live Verification Summary

**Date:** 12 August 2026 · **Environment:** local staging (containers) · **Production:** unchanged

## What was tested

Real dictation through the customer API (`POST /v1/audio/transcriptions`) with
authentication, language routing, metering and sample collection all active —
from **the web STT Studio** and **an Android phone** over an HTTPS tunnel.
Routing under test: **Hindi → Qwen3-ASR 0.6B**, **everything else → Whisper-small**.

Every request routed correctly. Zero failures. No internal model names exposed
to any client.

---

## English → Whisper-small (current production model)

| Surface | Audio | Wait for text | Speed (RTF) |
|---|---|---|---|
| Web Studio | 32.4 s | **3.0 s** | 0.09 |
| Android phone | 23.6 s | **1.8 s** | 0.07 |

**Transcript:** verbatim and correctly punctuated.

> Learning good manners doesn't come with an instruction manual. Nobody can spoon
> feed us the approach we should learn. Our parents and teachers give us the
> necessary ways to cultivate our personality. But we are the ones who have to put
> in the effort to better ourselves every day.

**Verdict:** working well. No change proposed for English.

---

## Hindi → Qwen3-ASR 0.6B (proposed model)

| Surface | Audio | Wait for text | Speed (RTF) |
|---|---|---|---|
| Web Studio | 30.2 s | **9.4 s** | 0.31 |
| Android phone | 28.5 s | **9.0 s** | 0.31 |

**Transcript:** clean, punctuated, correct Devanagari.

> मेरा विद्यालय बहुत अच्छा है, यह शहर के बीच में है, मेरे स्कूल में एक बड़ा खेल का मैदान है,
> हमारे स्कूल के सभी शिक्षक बहुत अच्छे हैं, वे हमें बहुत प्यार से पढ़ते हैं, मेरा स्कूल में एक
> सुंदर बगीचा भी है, जहाँ बहुत सारे फूल खिले हैं, मुझे मेरा विद्यालय बहुत पसंद है.

Two minor points to verify against the speaker's intent: *पढ़ते* (would be *पढ़ाते*
for "teach") and *मेरा स्कूल में* (grammatically *मेरे*). Everything else is correct.

**Verdict:** usable quality at an acceptable wait.

---

## The decisive test: same recording, both models

The Hindi phone recording (28.5 s) was replayed through both engines:

| Model | Time taken | Result |
|---|---|---|
| **Whisper-small** (production today) | **25.3 s** | Broke out of Hindi — Korean, Cyrillic and English fragments. Unusable. |
| **Qwen3-ASR 0.6B** (proposed) | **6.1 s** | Full passage, correct and punctuated. |

Whisper is not merely less accurate on Hindi — it fails, and failing is also slow
(its internal retry mechanism fires repeatedly). **For Hindi, the proposed model is
both faster and the only usable one.**

This matches the frozen benchmark measured earlier: character error rate
**0.146 for Qwen vs 0.363 for Whisper** — a 60% reduction.

---

## Reading the numbers

- **Wait for text** = the pause after you stop speaking. That is the user experience.
- **RTF** = seconds of compute per second of audio. Below 1.0 means the system never
  falls behind a speaker. It also indicates capacity: roughly `1 ÷ RTF` simultaneous
  conversations per machine, so Hindi costs about 3× more compute per call than English.

The tests above used unusually long 25–30 second passages. Typical dictation is
shorter, and the wait scales with it:

| Speaking time | English wait | Hindi wait |
|---|---|---|
| 5 s | ~0.5 s | ~1.5 s |
| 10 s | ~1 s | ~3 s |
| 30 s | ~3 s | ~9 s |

Network and gateway overhead (auth, routing, metering, collection) was ~50 ms
locally and ~200–300 ms from the phone over the tunnel. Over 85% of every wait is
model computation.

---

## Caveats

- Measured on a development laptop inside containers, not on production hardware.
- Run-to-run variance is real: the same file took 8.8 s and 6.1 s in two runs
  (CPU contention). Single measurements are indicative; the benchmark ladders are
  authoritative.
- Hindi audio is currently capped at **120 seconds** per request — the measured safe
  limit of the proposed engine. Longer audio is refused with a clear message.
- Production routing is untouched: Hindi still resolves to Whisper for customers.

## Recommendation

Proceed toward a controlled Hindi canary. The remaining prerequisites are
deployment-side, not engineering: validation on production-class hardware, a
physical Android device pass, and the formal promotion decision.
