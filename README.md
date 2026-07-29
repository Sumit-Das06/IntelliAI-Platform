# IntelliAI Platform

A commercial AI platform exposing production-grade AI APIs — starting with Speech AI
(speech-to-text, text-to-speech), expanding to LLMs, translation, vision, OCR,
embeddings, and agents on the same platform chassis.

> **Status:** v0.1 — Milestone 0 (Foundations) in progress.

## Architecture at a glance

IntelliAI is built as three planes:

- **Data plane** — the inference APIs customers call (`/v1/audio/transcriptions`, `/v1/audio/speech`, …)
- **Control plane** — accounts, API keys, rate limits, usage metering, model registry, jobs
- **Experience plane** — developer console, playground, documentation, SDKs

Two rules hold everything together:

1. **Inference never runs inside the gateway.** Every model — ours or an external
   provider's — lives in its own inference service behind a shared internal runtime
   contract, routed via the model registry. Models are swappable with zero
   client-visible change.
2. **The platform layer is domain-generic.** Speech-specific logic exists only inside
   speech inference services. Adding a new AI domain means new services and registry
   entries, not platform refactors.

## Repository layout

| Path | Purpose |
|---|---|
| `apps/api` | API gateway + control plane (FastAPI) |
| `apps/console` | Developer console (Next.js) — arrives M6 |
| `services/` | Inference services, one per model/provider |
| `packages/` | Shared libraries (runtime contract, Python SDK) |
| `ml/` | Production ML: dataset pipelines, training, evaluation harness |
| `research/` | Isolated experiments — production code never imports from here |
| `infra/` | Dockerfiles, compose overlays, deployment |
| `docs/` | Architecture Decision Records, API documentation |
| `tools/` | Developer scripts |

## Quickstart (development)

Prerequisites: Docker Desktop (WSL2 backend on Windows), GNU `make`.

```bash
cp .env.example .env    # dev defaults work out of the box; edit if you prefer
make up                 # full platform: API + Postgres + Redis + MinIO
make migrate            # apply database migrations
make ps                 # wait until every service reports (healthy)
```

Then: API docs at http://localhost:8000/docs · health at
http://localhost:8000/health/ready · DB browser via `make db-ui`.

Inner dev loop (hot reload, runs the API natively against the containers):

```bash
make sync               # once: install Python dependencies
make api                # uvicorn with --reload on port 8000
make test               # run the test suite
```

## Development rules

- On Windows, develop inside **WSL2** — Windows-native Python is unsupported for this repo.
- Trunk-based development: short-lived `feat/`-branches off `main`, squash-merged,
  [Conventional Commits](https://www.conventionalcommits.org/) message format.
- Significant decisions are recorded as ADRs in [docs/adr/](docs/adr/) — read them
  before challenging an existing pattern; update them when you win the argument.
