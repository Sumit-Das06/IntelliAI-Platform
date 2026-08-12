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

# ── Stage 1b: the vendored llama.cpp runtime (Milestone 18/19 layer) ────
# The qwen3-asr engine serves through a PINNED llama.cpp build. The pin
# is enforced twice: BuildKit verifies the release archive's checksum at
# fetch, and the engine re-hashes the six load-bearing binaries at every
# load (services/stt-runtime/.../engines/qwen3_asr.py, linux table) —
# so a tampered layer cannot serve. Carrying the layer activates
# NOTHING: engines load only for artifacts a deployment declares, and
# every committed deployment declares whisper only (guard-tested).
FROM python:3.12-slim AS llama
ADD --checksum=sha256:01b90b0764821d0e53b985730eea3837e29a976ee00e783e18837937b93fc3f1 \
    https://github.com/ggml-org/llama.cpp/releases/download/b10344/llama-b10344-bin-ubuntu-x64.tar.gz \
    /tmp/llama.tar.gz
RUN mkdir -p /opt/llama-cpp && \
    tar xzf /tmp/llama.tar.gz -C /tmp && \
    # The full library set travels (the server resolves VERSIONED sonames
    # like libllama.so.0 and libllama-common.so.0 via RPATH=$ORIGIN, so
    # cherry-picking breaks at exec); -a preserves the symlink layout.
    cp -a /tmp/llama-b10344/llama-server /tmp/llama-b10344/*.so* /opt/llama-cpp/ && \
    cd /opt/llama-cpp && \
    echo "9b7b699e2e9579184117834aeaef34d5cc711027fbbc67a2a38d66559c4f288e  llama-server" | sha256sum -c - && \
    echo "2e5d35d03aefee87ff59482e098b081bc75251ff633a5bc381ce75200df2fefc  libllama-server-impl.so" | sha256sum -c - && \
    echo "4b5095195b0cadb260ea2765cfab9d1e503f92bb6b82f15f971c489f6ce77007  libllama.so" | sha256sum -c - && \
    echo "d6a465f5346b4d5d89ce995f19cc67b21b3b9ea846995c8e043c0536087c64ae  libmtmd.so" | sha256sum -c - && \
    echo "ffd6a736ad58e2d9407ed427252520ffbd4bca8dd5de467ecb2bd446a7a3d75b  libggml.so" | sha256sum -c - && \
    echo "e486598626ec06c8cb23a4661ad0401f146a7744b0a136f092e6042597a21e4c  libggml-base.so" | sha256sum -c -

# ── Stage 2: runtime ────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# ffmpeg is the pipeline's decoder; startup verification refuses to serve
# without it, so it is part of the image contract. libgomp1 is the ONE
# system dependency of the vendored llama.cpp layer (outside its pin
# table by design — an OS package, satisfied by the OS layer).
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg libgomp1 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=llama /opt/llama-cpp /opt/llama-cpp

RUN groupadd --system app && \
    useradd --system --gid app --no-create-home --shell /usr/sbin/nologin app && \
    mkdir /models && chown app:app /models

WORKDIR /app
COPY --from=builder --chown=app:app /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    INTELLIAI_STT_MODEL_DIR=/models \
    INTELLIAI_STT_QWEN3_SERVER_BINARY=/opt/llama-cpp/llama-server

USER app
EXPOSE 8001

CMD ["uvicorn", "--factory", "intelliai_stt_runtime.main:create_app", "--host", "0.0.0.0", "--port", "8001"]
