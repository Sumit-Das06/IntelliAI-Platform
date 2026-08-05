# Whisper (OpenAI) — Gate 0 Intake Record

| | |
|---|---|
| **Stage** | Gate 0 — intake only. No screening, scoring, comparison, or recommendation. |
| **Status** | Approved for Adoption (small, incumbent) · Researching (large-v3 / turbo) |
| **Registered** | 2026-08-04 (ledger seed) · intake record created 2026-08-05 |
| **Capability** | transcription |

> Fields are **claims** (§2) unless marked *verified at source*. Only
> `ml/evaluation` records are Evidence. Full §11 dossier is due at Gate 2.

## Lineage
OpenAI Whisper — weakly-supervised encoder-decoder transformer (2022).
The lineage includes upstream checkpoints (tiny → large-v3,
large-v3-turbo) plus two derivative families that inherit its license and
tooling: **Distil-Whisper** (distilled, faster) and **IndicWhisper**
(AI4Bharat Indic fine-tunes — see [indicwhisper-dossier.md](indicwhisper-dossier.md)).

## Repository
`github.com/openai/whisper`; checkpoints at `huggingface.co/openai/whisper-*`.
Production serving runtime: **faster-whisper** (SYSTRAN, CTranslate2), the
form IntelliAI actually deploys.

## Organization
OpenAI. Upstream research effort is effectively concluded; the ecosystem
is carried by third parties (SYSTRAN, HuggingFace, whisper.cpp, AI4Bharat).

## License (claimed at intake)
MIT — verified at the Systran faster-whisper distribution 2026-07-31 for
the `whisper-small` artifact in production. Per-version re-verification is
required before any *new* checkpoint (large-v3, turbo) becomes
load-bearing.

## Model family / sizes
tiny (39M) · base (74M) · small (244M, **in production**) · medium (769M) ·
large-v2/v3 (1.55B) · large-v3-turbo (809M, claimed). Distil-Whisper and
IndicWhisper variants sit at assorted sizes.

## Supported languages (claimed)
~99 languages claimed upstream. IntelliAI's own position:
- **English** — Evidence: WER 0.000 on stt-eval-v1, production baseline 2026-08-03.
- **Hindi** — usable; a wedge gap is anecdotally observed (one founder self-test), unmeasured.
- **Arabic** — claimed by the card, **never evaluated by us**.

## Streaming support (claimed)
No native streaming. Fixed 30-second window; streaming requires external
chunking plus VAD gating (which our pipeline already performs).

## Model sizes / hardware expectations
CPU-viable and proven at our economics: int8 `small` measures RTF 0.162
(~6× realtime) at ~800MiB steady-state on our reference hardware.
`large-v3` is roughly 6× the parameters — CPU viability at our latency
targets is an **open question**, not a known quantity.

## Maintenance activity
Upstream frozen; ecosystem highly active. The framework treats a frozen
base as strategically acceptable for a company that intends to fine-tune
(FOUNDATION_MODELS §2 reasoning) — the lineage matters more than the
checkpoint.

## Commercial concerns
MIT with no known field-of-use, revenue, or MAU traps. No transitive
license issues identified in the deployed faster-whisper path to date.

## Known limitations
Hallucination on silence and non-speech (structurally mitigated by our
VAD short-circuit — probes measure 0 hallucinated words); 30s window;
no native streaming; no diarization; timestamp granularity depends on
the serving stack.

## Why this lineage deserves investigation
It is the incumbent and therefore the **baseline every challenger must
beat** — the switching test is defined against it. Two standing questions
justify continued research: whether `large-v3`/`turbo` earns its cost over
`small` on *our* corpus, and whether the Hindi gap is a lineage ceiling or
a fine-tuning opportunity (the answer decides between §9 rung 3 and
rung 5). Its fine-tuning ecosystem is the largest in ASR, so capital spent
here compounds.
