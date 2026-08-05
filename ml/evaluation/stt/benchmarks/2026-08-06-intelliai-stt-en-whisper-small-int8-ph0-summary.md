# Benchmark summary — intelliai-stt/en/whisper-small@1/int8/stt-eval-seed@v2

> **Derived report.** Regenerated from [`2026-08-06-intelliai-stt-en-whisper-small-int8-ph0.json`](2026-08-06-intelliai-stt-en-whisper-small-int8-ph0.json); never edited by hand and never citable as evidence — citations name the record.

## Identity

| | |
|---|---|
| Subject | `intelliai-stt` |
| Language | `en` |
| Artifact | `whisper-small` v1 (int8) |
| Deployment | `stt-runtime` |
| Corpus | `stt-eval-seed@v2` |
| Run at | 2026-08-05T21:30:23.638010+00:00 |
| Session | `CAMP-STT-2026A/PH0/S01-en` |
| Named baseline | — (not a named baseline) |
| Validity | not computed |

## Execution

| | |
|---|---|
| Route | `product_path` |
| Ruler | `unicode_generic@v2` |
| Language mode | `explicit` (declared `en`) |
| Emitted unit | `word` |
| VAD owner | `pipeline` |
| Timestamp source | `native` |
| Decode configuration | beam_size=5, best_of=5, compression_ratio_threshold=2.4, condition_on_previous_text=true, length_penalty=1, log_prob_threshold=-1.0, no_speech_threshold=0.6, patience=1, task=transcribe, temperature=0.0,0.2,0.4,0.6,0.8,1.0, vad_filter=false, without_timestamps=false, word_timestamps=false |
| Machine | Intel64 Family 6 Model 183 Stepping 1, GenuineIntel (class: unruled) |

## Startup lifecycle

- model load: 3637.6 ms · warm-up: 2667.6 ms

## Slice coverage

- 4 clip(s): 2 natural speech, 2 probe(s); 44 reference word(s)
- quality claim: yes

## Metrics

| Metric | Value | Better |
|---|---|---|
| `cer_unicode` | 0.0000 | lower |
| `deletion_rate` | 0.0000 | lower |
| `excess_word_ratio` | 0.0000 | lower |
| `hallucinated_words` | 0.0000 | lower |
| `insertion_rate` | 0.0000 | lower |
| `recognition_rtf` | 0.1310 | lower |
| `substitution_rate` | 0.0000 | lower |
| `wer_ascii` | 0.0000 | lower |
| `wer_unicode` | 0.0000 | lower |

## Determinations — absence recorded as evidence

| Code | State | By | Basis |
|---|---|---|---|
| `manifest_provenance_unverified` | undeterminable | harness | fact |
| `stack_not_reported` | not_measured | harness | fact |
| `cpu_physical_cores_unavailable` | undeterminable | harness | fact |
| `ram_total_mib_unavailable` | undeterminable | harness | fact |
| `thread_env_unavailable` | undeterminable | harness | fact |
| `hardware_class_unruled` | not_measured | harness | fact |
