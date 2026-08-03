# IntelliAI STT runtime image.
# Build context is the REPOSITORY ROOT (uv workspace needs root manifests):
#   docker compose build stt-runtime
#
# Same shape as the api image (multi-stage uv, non-root, stdout logs) plus
# the runtime's two extras: ffmpeg (the media pipeline's decoder) and the
# `whisper` engine extra (faster-whisper — engines are the only reason a
# model library enters an image, and only THIS image). Model weights are
# NOT baked in: the ModelManager downloads and hash-verifies them into the
# /models volume on first startup — images stay small and artifact updates
# never require an image rebuild.

# ── Stage 1: builder ────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.0 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Layer 1: third-party dependencies (incl. the whisper engine extra).
COPY pyproject.toml uv.lock .python-version ./
COPY services/stt-runtime/pyproject.toml services/stt-runtime/
COPY packages/runtime-contract/pyproject.toml packages/runtime-contract/
COPY packages/runtime-core/pyproject.toml packages/runtime-core/
RUN uv sync --frozen --no-dev --no-install-workspace \
    --package intelliai-stt-runtime --extra whisper

# Layer 2: our source, then the workspace packages themselves.
COPY services/stt-runtime/src services/stt-runtime/src
COPY packages/runtime-contract/src packages/runtime-contract/src
COPY packages/runtime-core/src packages/runtime-core/src
RUN uv sync --frozen --no-dev --package intelliai-stt-runtime --extra whisper

# ── Stage 2: runtime ────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# ffmpeg is the pipeline's decoder; startup verification refuses to serve
# without it, so it is part of the image contract.
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd --system app && \
    useradd --system --gid app --no-create-home --shell /usr/sbin/nologin app && \
    mkdir /models && chown app:app /models

WORKDIR /app
COPY --from=builder --chown=app:app /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    INTELLIAI_STT_MODEL_DIR=/models

USER app
EXPOSE 8001

CMD ["uvicorn", "--factory", "intelliai_stt_runtime.main:create_app", "--host", "0.0.0.0", "--port", "8001"]
