"""14B production-configuration guards — executable documentation.

These read the deployment files as text and pin the production posture:
stateful ports stay loopback-bound, secrets stay required-not-defaulted,
the edge keeps its body ceiling and security headers, the backup scripts
exist and never carry credentials, and the example env files hold
placeholders only. No fake infrastructure — the files ARE the interface
being tested, exactly like the Android scope guards.
"""

import re
from pathlib import Path

# Tests run with apps/api as the working directory root for the package;
# the repository root is two levels above this file's directory.
REPO = Path(__file__).resolve().parents[3]

COMPOSE = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
PROD_OVERLAY = (REPO / "infra/compose/prod.yml").read_text(encoding="utf-8")
CADDYFILE = (REPO / "infra/Caddyfile").read_text(encoding="utf-8")
ENV_EXAMPLE = (REPO / ".env.example").read_text(encoding="utf-8")
ENV_PROD_EXAMPLE = (REPO / ".env.prod.example").read_text(encoding="utf-8")


# ── Compose posture ──────────────────────────────────────────────────────


def test_every_published_port_in_the_base_stack_is_loopback_bound() -> None:
    # The base file must never expose a service to the LAN: the prod
    # overlay adds Caddy for the internet, and ONLY Caddy.
    published = re.findall(r'-\s*"([^"]+:\d+:\d+)"', COMPOSE)
    assert published, "expected published ports in the base compose file"
    for entry in published:
        assert entry.startswith("127.0.0.1:"), f"non-loopback port mapping: {entry}"


def test_only_caddy_faces_the_internet_in_the_prod_overlay() -> None:
    ports = re.findall(r'-\s*"(\d+:\d+)"', PROD_OVERLAY)
    assert sorted(ports) == ["443:443", "80:80"], ports
    # And the overlay pins the production posture explicitly.
    assert "INTELLIAI_ENV: prod" in PROD_OVERLAY
    assert "INTELLIAI_STT_SLOTS: whisper" in PROD_OVERLAY


def test_the_staging_registry_profile_is_never_committed_configuration() -> None:
    # Milestone 18: INTELLIAI_REGISTRY_PROFILE=staging activates the
    # prepared proposals. It is a LOCAL, hand-set choice — a committed
    # compose file carrying it would be a promotion that skipped review.
    for overlay in (COMPOSE, PROD_OVERLAY):
        assert "INTELLIAI_REGISTRY_PROFILE" not in overlay


def test_research_engines_never_appear_in_committed_deployments() -> None:
    # Milestone 16 production-disabled guard: the qwen3-asr engine is
    # research-only until the switching gates pass and a founder promotes
    # it via the catalog (docs/ops/model-rollout.md). No committed compose
    # file may declare it — a research candidate reaching a deployment
    # declaration must be a loud, reviewed diff, never drift.
    for overlay in (COMPOSE, PROD_OVERLAY):
        assert "qwen3" not in overlay.lower()


def test_secrets_are_required_never_defaulted_in_compose() -> None:
    # `:?` makes compose refuse to start without a value — a dev default
    # can never silently become a production credential.
    for variable in (
        "INTELLIAI_AUTH_KEY_PEPPER",
        "POSTGRES_PASSWORD",
        "MINIO_ROOT_PASSWORD",
    ):
        assert re.search(rf"\${{{variable}:\?", COMPOSE), f"{variable} must be required (:?)"


def test_dev_tools_and_tts_stay_behind_profiles() -> None:
    # Adminer and the TTS runtime must never start with a bare `up -d`.
    # Service definitions are two-space-indented keys at line start —
    # never confused with the service names inside URL values.
    def service_block(name: str) -> str:
        start = COMPOSE.index(f"\n  {name}:\n")
        following = re.search(r"\n  [a-z-]+:\n", COMPOSE[start + 1 :])
        end = start + 1 + following.start() if following else len(COMPOSE)
        return COMPOSE[start:end]

    assert "profiles: [tools]" in service_block("adminer")
    assert "profiles: [tts]" in service_block("tts-runtime")


def test_every_service_restarts_unless_stopped() -> None:
    services = COMPOSE.count("restart: unless-stopped")
    assert services >= 6, "every long-running service needs a restart policy"


# ── Edge (Caddy) ─────────────────────────────────────────────────────────


def test_the_edge_keeps_the_body_ceiling_and_security_headers() -> None:
    assert "max_size 30MB" in CADDYFILE
    assert "Strict-Transport-Security" in CADDYFILE
    assert "X-Content-Type-Options" in CADDYFILE
    assert "reverse_proxy api:8000" in CADDYFILE
    # The domain is configuration, never a hardcoded name.
    assert "{$DOMAIN" in CADDYFILE


# ── Backup interface ─────────────────────────────────────────────────────


def test_backup_and_restore_scripts_exist_and_never_embed_credentials() -> None:
    for name in ("backup.sh", "backup-objects.sh", "restore-objects.sh"):
        script = (REPO / "infra" / name).read_text(encoding="utf-8")
        # Credentials arrive via environment; a literal assignment of a
        # non-empty password on a CODE line would be a leak. Comment
        # lines (usage examples with `...` placeholders) are exempt.
        for line in script.splitlines():
            if line.lstrip().startswith("#"):
                continue
            match = re.search(r"(?i)(password|secret[_A-Z]*key)\s*=\s*([^\s${:?]+)", line)
            if match:
                raise AssertionError(f"{name} embeds a credential-looking literal: {line.strip()}")
        assert "set -euo pipefail" in script, f"{name} must fail loudly"


def test_backup_scripts_never_delete_source_data() -> None:
    script = (REPO / "infra/backup-objects.sh").read_text(encoding="utf-8")
    # Mirroring must stay additive on the source side: no --remove (which
    # deletes destination strays and, misdirected, source objects), no rm
    # against a bucket alias.
    assert "--remove" not in script
    assert not re.search(r"mc\s+rm", script)


def test_the_makefile_exposes_the_backup_verbs() -> None:
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    for target in ("backup:", "backup-objects:", "restore-objects:", "prod-up:", "prod-migrate:"):
        assert f"\n{target}" in makefile, f"missing Makefile target {target}"


# ── Example env files: placeholders only ────────────────────────────────


def test_env_examples_contain_no_real_looking_secrets() -> None:
    # A generated secret is long hex; examples must carry empty values or
    # obvious dev-only placeholders, never something that looks minted.
    for name, text in ((".env.example", ENV_EXAMPLE), (".env.prod.example", ENV_PROD_EXAMPLE)):
        for match in re.finditer(r"(?m)^[A-Z_]+=([^\s#]+)", text):
            value = match.group(1)
            assert not re.fullmatch(r"[0-9a-fA-F]{32,}", value), (
                f"{name} contains a minted-looking secret: {match.group(0)[:40]}…"
            )
        assert "ik_live_" not in text, f"{name} must never carry an API key"


def test_the_prod_example_requires_generation_not_reuse() -> None:
    # Production secrets ship EMPTY: the operator must generate them.
    for variable in ("INTELLIAI_AUTH_KEY_PEPPER", "POSTGRES_PASSWORD", "MINIO_ROOT_PASSWORD"):
        assert re.search(rf"(?m)^{variable}=$", ENV_PROD_EXAMPLE), (
            f"{variable} must be empty in .env.prod.example"
        )
    # And the off-box backup interface is declared (empty until supplied).
    assert "INTELLIAI_BACKUP_S3_URL=" in ENV_PROD_EXAMPLE
