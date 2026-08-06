# IntelliAI API gateway image.
# Build context is the REPOSITORY ROOT (uv workspace needs root manifests):
#   docker compose build api
#
# Multi-stage: the builder has uv and build tooling; the runtime image has
# only Python, the virtualenv, and the application source — no package
# manager, no lockfiles, no compilers. One process, non-root, logs to stdout.

# ── Stage 1: builder ────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.0 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Layer 1: third-party dependencies. Only manifests are copied, so this
# expensive layer is rebuilt ONLY when dependencies change — source edits
# reuse the cache and rebuild in seconds.
COPY pyproject.toml uv.lock .python-version ./
COPY apps/api/pyproject.toml apps/api/
COPY packages/runtime-contract/pyproject.toml packages/runtime-contract/
RUN uv sync --frozen --no-dev --no-install-workspace --package intelliai-api

# Layer 2: our source (the gateway and the workspace packages it depends
# on), then install the workspace packages themselves. Alembic ships in
# the image so a fresh deployment can migrate its own database:
#   docker compose run --rm api alembic -c apps/api/alembic.ini upgrade head
COPY apps/api/src apps/api/src
COPY apps/api/alembic.ini apps/api/alembic.ini
COPY apps/api/alembic apps/api/alembic
COPY packages/runtime-contract/src packages/runtime-contract/src
RUN uv sync --frozen --no-dev --package intelliai-api

# ── Stage 2: runtime ────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Least privilege: a system user with no shell, no home directory writes,
# and no ability to install anything.
RUN groupadd --system app && \
    useradd --system --gid app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app
COPY --from=builder --chown=app:app /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER app
EXPOSE 8000

CMD ["uvicorn", "--factory", "intelliai_api.main:create_app", "--host", "0.0.0.0", "--port", "8000"]
