# ml/ — Production ML

Versioned, tested, production-grade ML work — distinct from `research/`
(exploratory, no quality bar). Reserved layout (MLOps-ready from day one):

- `datasets/`  — dataset pipelines + dataset registry (Phase 2)
- `training/`  — training & fine-tuning pipelines, experiment tracking,
                 checkpoint storage conventions (Phase 2)
- `evaluation/`— benchmark harness (Milestone 9): STT WER/CER/RTF/latency/
                 throughput; TTS MOS-proxy/latency/generation-speed/memory.
                 Every fine-tuned model is compared against its baseline here.
