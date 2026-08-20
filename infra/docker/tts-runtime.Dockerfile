# IntelliAI TTS runtime image.
# Build context is the REPOSITORY ROOT (uv workspace needs root manifests):
#   docker compose build tts-runtime
#
# Same shape as the stt image (multi-stage uv, non-root, stdout logs,
# weights as a /models volume cache — never baked in) with the `kokoro`
# engine extra, plus one legal subtraction: misaki[en] transitively
# installs GPL espeak wrappers (phonemizer-fork, espeakng-loader). The
# engine's license firewall keeps them out of the PROCESS (M3 design
# review §8); this build keeps them off the DISK entirely — the deployed
# artifact carries no GPL code, verified at build time: the image REFUSES
# to build if either package is still importable.

# ── Stage 1: builder ────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.0 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Layer 1: third-party dependencies (incl. the kokoro engine extra).
COPY pyproject.toml uv.lock .python-version ./
COPY services/tts-runtime/pyproject.toml services/tts-runtime/
COPY packages/runtime-contract/pyproject.toml packages/runtime-contract/
COPY packages/runtime-core/pyproject.toml packages/runtime-core/
RUN uv sync --frozen --no-dev --no-install-workspace \
    --package intelliai-tts-runtime --extra kokoro

# Layer 2: our source, then the workspace packages themselves.
COPY services/tts-runtime/src services/tts-runtime/src
COPY packages/runtime-contract/src packages/runtime-contract/src
COPY packages/runtime-core/src packages/runtime-core/src
RUN uv sync --frozen --no-dev --package intelliai-tts-runtime --extra kokoro

# The GPL subtraction: remove the espeak wrapper chain from the venv and
# FAIL THE BUILD if anything GPL remains importable.
RUN uv pip uninstall --python /app/.venv/bin/python phonemizer-fork espeakng-loader && \
    /app/.venv/bin/python -c "import importlib.util, sys; \
banned = ['phonemizer', 'espeakng_loader']; \
present = [name for name in banned if importlib.util.find_spec(name) is not None]; \
sys.exit(1 if present else 0)"

# ── Stage 2: runtime ────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# espeak-ng: the M35 OOV-fallback BINARY (GPL-3.0), used ONLY behind an
# exec boundary (M3 §8 — the ffmpeg posture). The python GPL chain stays
# banned above; nothing in this image links espeak as a library. The
# runtime pins the reported version (INTELLIAI_TTS_ESPEAK_VERSION_PIN)
# and refuses startup on a mismatch when the fallback is enabled.
RUN apt-get update && \
    apt-get install -y --no-install-recommends espeak-ng espeak-ng-data && \
    rm -rf /var/lib/apt/lists/* && \
    espeak-ng --version

RUN groupadd --system app && \
    useradd --system --gid app --no-create-home --shell /usr/sbin/nologin app && \
    mkdir /models && chown app:app /models

WORKDIR /app
COPY --from=builder --chown=app:app /app /app

# HF_HUB_OFFLINE: the runtime loads ONLY from the hash-verified store;
# the Hugging Face hub is never contacted from a deployment.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    INTELLIAI_TTS_MODEL_DIR=/models \
    HF_HUB_OFFLINE=1

USER app
EXPOSE 8002

CMD ["uvicorn", "--factory", "intelliai_tts_runtime.main:create_app", "--host", "0.0.0.0", "--port", "8002"]
