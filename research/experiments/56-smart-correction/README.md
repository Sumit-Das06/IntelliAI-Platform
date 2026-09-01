# M56 — Smart transcript correction: research + model selection

Evidence for `docs/research/2026-09-01-smart-transcript-correction.md`.

Frozen benchmark: `evidence/dataset.jsonl` (`smart-correction-en-hi@v1`,
300 AUTHORED rows, sha in `dataset-manifest.json`; rows_en.py / rows_hi.py
are the source of the freeze — editing them creates a NEW version).

Prototype (research-only, loopback llama-server, no production surface):
`tools/research/smart_correction/` — run_correction.py (v3 language-scoped
prompts), score_correction.py (NFC-normalized; violation vs
normalization-miss split), latency_probe.py, extras.py.

Result naming: `*-qwen3-4b-v3` = the canonical run;
`outputs-qwen3-4b-{en,hi}.jsonl` + `-v2-` = archived prompt iterations;
`baseline-*` = identity/rules. Servers used: pinned llama.cpp b10344
CUDA (ports 8899/8900) + pinned CPU build (8901). No external API
received a single token.
