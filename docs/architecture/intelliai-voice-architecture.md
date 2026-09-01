# IntelliAI — Voice Processing Architecture (Diagram B)

*Detailed view of the voice path; status as of 2026-09-01.*

## Batch STT path (upload/record)

```mermaid
flowchart TD
    A["Audio upload<br/>(wav/mp3/m4a…, ≤10 min)"] --> M["Media pipeline<br/>type whitelist → sandboxed ffmpeg decode →<br/>canonical 16 kHz mono PCM"]
    M --> VAD["Voice-activity detection<br/>(silence short-circuits: no inference, no hallucination)"]
    VAD --> ROUTE{"Language route<br/>(registry-driven, no if-chains)"}
    ROUTE -->|en| W["whisper-small<br/>(dedicated worker pool)"]
    ROUTE -->|hi| Q["Own fine-tuned E3<br/>(llama.cpp server; long audio via<br/>VAD-snapped hybrid chunking)"]
    W --> PEN["English punctuation<br/>(INT8, +45 ms, word-copy guarantee)"]
    Q --> PHI["Hindi punctuation<br/>(word-copy guarantee)"]
    PEN --> OUT["Transcript<br/>text + raw_text"]
    PHI --> OUT
    OUT --> FLY["Correction / Share /<br/>consented sample collection"]
```

- Hindi batch on GPU (validated M55, production-required decision): the
  same E3 model served by a pinned GPU llama-server — this **eliminates**
  a measured CPU-only instability on long multi-speaker audio
  (2–94 words scatter → 117 words byte-identical ×5).

## Engine isolation (why models are swappable)

```mermaid
flowchart LR
    G["Gateway"] -->|"frozen runtime contract v1<br/>(unchanged through 5 capabilities)"| RT["STT / TTS runtime services"]
    RT --> EA["Engine adapters<br/>(only these may import model libraries — CI-enforced)"]
    EA --> MM["Model manager<br/>SHA-256-pinned weights, verified at startup,<br/>no request-time downloads (structurally impossible)"]
```

## Quality machinery around the models

- Frozen evaluation sets (speaker-disjoint Hindi primary; English trap
  sets; punctuation slot rulers) — models compete on fixed ground.
- Append-only MODEL_LEDGER records every measurement, including failures.
- Promotion = a reviewed repository decision with a drilled rollback,
  never a silent swap.
