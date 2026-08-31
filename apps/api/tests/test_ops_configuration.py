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
    # And the overlay pins the production posture explicitly — since the
    # M26 promotion that means the incumbent PLUS the approved Hindi
    # specialist, named exactly (never a generic or mutable reference).
    assert "INTELLIAI_ENV: prod" in PROD_OVERLAY
    assert "INTELLIAI_STT_SLOTS: whisper,qwen3-asr:qwen3-asr-0.6b-hi-ft-e3" in PROD_OVERLAY


def test_the_staging_registry_profile_is_never_committed_configuration() -> None:
    # Milestone 18: INTELLIAI_REGISTRY_PROFILE=staging activates the
    # prepared proposals. It lives ONLY in the explicit local-staging
    # overlay — the base stack and the prod overlay carrying it would be
    # a promotion that skipped review.
    for overlay in (COMPOSE, PROD_OVERLAY):
        assert "INTELLIAI_REGISTRY_PROFILE" not in overlay


def test_the_local_staging_overlay_is_explicit_and_unreachable_from_prod() -> None:
    # Milestone 19: the founder-facing staging stack. The overlay must
    # say exactly what it changes (profile + slots), and NOTHING in the
    # production path may reference it — activating staging is always a
    # deliberate, hand-typed act.
    overlay = (REPO / "infra/compose/local-staging.yml").read_text(encoding="utf-8")
    assert "INTELLIAI_REGISTRY_PROFILE: staging" in overlay
    # M24: the staging slot is E3-SPECIFIC — the generic base artifact
    # must never silently come back as the canary candidate.
    assert "whisper,qwen3-asr:qwen3-asr-0.6b-hi-ft-e3" in overlay
    assert "local-staging" not in PROD_OVERLAY
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    prod_targets = makefile[makefile.index("prod-up:") :]
    assert "local-staging" not in prod_targets


def test_the_local_prod_overlay_is_e3_shaped_and_unreachable_from_prod() -> None:
    # M25: the local production-shaped stack — the prod architecture
    # (Caddy edge) with the ONE staging difference (hi -> E3). It must
    # declare the E3-specific slot and the staging profile, must NEVER
    # set the production environment (the settings layer would refuse
    # the combination anyway — structural, not procedural), must keep
    # its edge loopback-bound (the tunnel is the only way in), and no
    # prod-* Make target may reference it.
    overlay = (REPO / "infra/compose/local-prod.yml").read_text(encoding="utf-8")
    assert "INTELLIAI_REGISTRY_PROFILE: staging" in overlay
    assert "whisper,qwen3-asr:qwen3-asr-0.6b-hi-ft-e3" in overlay
    assert "INTELLIAI_ENV: prod" not in overlay
    ports = re.findall(r'-\s*"([^"]+)"', overlay)
    for entry in ports:
        assert entry.startswith("127.0.0.1:"), f"local-prod edge beyond loopback: {entry}"
    assert "local-prod" not in PROD_OVERLAY
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    prod_targets = makefile[makefile.index("\nprod-check:") :]
    prod_targets = prod_targets[: prod_targets.index("\nbackup:")]
    assert "local-prod" not in prod_targets
    # No throwaway tunnel hostname may ever be committed as configuration.
    for text in (COMPOSE, PROD_OVERLAY, overlay, makefile):
        assert "trycloudflare" not in text


def test_research_artifacts_never_appear_in_committed_deployments() -> None:
    # Milestone 16 production-disabled guard, M26 form: the founder
    # promoted EXACTLY qwen3-asr-0.6b-hi-ft-e3 (docs/ops/model-rollout.md).
    # Research-only artifacts — the base challenger, E1, E2 — must never
    # reach a committed deployment declaration, and the base dev stack
    # still hosts the incumbent only.
    assert "qwen3" not in COMPOSE.lower()
    local_prod = (REPO / "infra/compose/local-prod.yml").read_text(encoding="utf-8")
    for overlay in (PROD_OVERLAY, local_prod):
        for research_only in (
            "qwen3-asr,",  # a bare family slot would resolve to the base artifact
            "qwen3-asr\n",
            "qwen3-asr-0.6b-hi-ft-e1",
            "qwen3-asr-0.6b-hi-ft-e2",
            "qwen3-asr:qwen3-asr-0.6b\n",
        ):
            assert research_only not in overlay
        # The one sanctioned declaration, exact:
        assert "qwen3-asr:qwen3-asr-0.6b-hi-ft-e3" in overlay


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
    for name in (
        "backup.sh",
        "backup-objects.sh",
        "restore-objects.sh",
        "prod-preflight.sh",
        "prod-smoke.sh",
        "restore-check.sh",
    ):
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


def test_the_makefile_exposes_the_deployment_verbs() -> None:
    # Milestone 20: the deployment sequence is executable documentation —
    # preflight, build, up, migrate, health, smoke, backup, restore-check.
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    for target in (
        "prod-check:",
        "prod-build:",
        "prod-health:",
        "prod-smoke:",
        "prod-backup:",
        "prod-restore-check:",
        "prod-down:",
    ):
        assert f"\n{target}" in makefile, f"missing Makefile target {target}"


def test_prod_migrate_refuses_to_run_without_a_fresh_backup() -> None:
    # The runbook's backup-before-migration rule, made mechanical: the
    # target must gate on a recent pg dump and name the override.
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    migrate = makefile[makefile.index("\nprod-migrate:") : makefile.index("\nprod-health:")]
    assert "pg-*.sql.gz" in migrate, "prod-migrate must check for a recent backup"
    assert "force" in migrate, "prod-migrate must offer an explicit first-deploy override"


def test_preflight_refuses_the_staging_profile_and_placeholder_secrets() -> None:
    script = (REPO / "infra/prod-preflight.sh").read_text(encoding="utf-8")
    assert "INTELLIAI_REGISTRY_PROFILE" in script, "preflight must refuse the staging profile"
    assert "api.yourdomain.com" in script, "preflight must reject the placeholder domain"
    for variable in ("INTELLIAI_AUTH_KEY_PEPPER", "POSTGRES_PASSWORD", "MINIO_ROOT_PASSWORD"):
        assert variable in script, f"preflight must require {variable}"


def test_the_smoke_script_checks_the_load_bearing_surfaces() -> None:
    script = (REPO / "infra/prod-smoke.sh").read_text(encoding="utf-8")
    for surface in (
        "/health/live",
        "/health/ready",
        "alembic",
        "401",  # auth is enforced
        "strict-transport-security",
        "0\\.0\\.0\\.0",  # the port-exposure sweep
    ):
        assert surface in script, f"smoke must verify {surface}"


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


# ── Timeout chain consistency (Milestones 19/20) ─────────────────────────


def test_the_admission_lease_outlasts_the_runtime_deadline() -> None:
    # The lease is eviction insurance for stuck requests. If it expires
    # below the gateway's own deadline, a healthy long-audio request
    # frees its admission slot while still running — silent
    # over-admission. M19 found exactly this (180 < the new deadline)
    # and re-sized both by measurement; this pins the relationship so no
    # future retuning can silently reopen it.
    from intelliai_api.core.config import LimitsSettings, RuntimeSettings

    deadline = RuntimeSettings().timeout_seconds
    assert deadline >= 450.0, "deadline sized to the measured worst 600 s chunked wall (M19)"
    assert LimitsSettings().lease_seconds > deadline


def test_the_prod_example_requires_generation_not_reuse() -> None:
    # Production secrets ship EMPTY: the operator must generate them.
    for variable in ("INTELLIAI_AUTH_KEY_PEPPER", "POSTGRES_PASSWORD", "MINIO_ROOT_PASSWORD"):
        assert re.search(rf"(?m)^{variable}=$", ENV_PROD_EXAMPLE), (
            f"{variable} must be empty in .env.prod.example"
        )
    # And the off-box backup interface is declared (empty until supplied).
    assert "INTELLIAI_BACKUP_S3_URL=" in ENV_PROD_EXAMPLE


def test_punctuation_ships_off_in_prod_and_on_only_in_the_local_stage() -> None:
    # M30: the Hindi punctuation stage is IMPLEMENTED but production stays
    # OFF until its own promotion decision — explicit in the overlay, never
    # inherited from a stray dev variable. The local production-shaped
    # stack is the ONLY committed deployment that enables it (the staging
    # battery runs there), and it whitelists exactly the approved route.
    assert 'INTELLIAI_STT_PUNCTUATION_ENABLED: "false"' in PROD_OVERLAY
    local_prod = (REPO / "infra/compose/local-prod.yml").read_text(encoding="utf-8")
    assert 'INTELLIAI_STT_PUNCTUATION_ENABLED: "true"' in local_prod
    assert "INTELLIAI_STT_PUNCTUATION_LANGUAGES: hi,hi-IN" in local_prod
    # The base compose must not default the stage on anywhere:
    assert "PUNCTUATION" not in COMPOSE


def test_english_punctuation_ships_off_in_prod_and_on_only_in_the_local_stage() -> None:
    # M50/M51: the English punctuation stage follows the SAME law as the
    # Hindi one — implemented, staged in the local production-shaped stack
    # only, and pinned OFF in production until its own promotion decision.
    assert 'INTELLIAI_STT_PUNCTUATION_EN_ENABLED: "false"' in PROD_OVERLAY
    local_prod = (REPO / "infra/compose/local-prod.yml").read_text(encoding="utf-8")
    assert 'INTELLIAI_STT_PUNCTUATION_EN_ENABLED: "true"' in local_prod
    assert "INTELLIAI_STT_PUNCTUATION_EN_LANGUAGES: en,en-US,en-IN" in local_prod
    # The guard scripts watch the English stage the same way they watch
    # the Hindi one — enable-without-artifact refuses at preflight, and
    # readiness must match the declaration at smoke time.
    preflight = (REPO / "infra/prod-preflight.sh").read_text(encoding="utf-8")
    assert "INTELLIAI_STT_PUNCTUATION_EN_ENABLED" in preflight
    assert "punct-en-kredor" in preflight
    smoke = (REPO / "infra/prod-smoke.sh").read_text(encoding="utf-8")
    assert '"punctuation_en"' in smoke


def test_realtime_stt_ships_off_in_prod_and_on_only_in_the_local_stage() -> None:
    # M53: realtime sessions follow the SAME law as every staged feature —
    # the local production-shaped stack is the ONLY committed deployment
    # that points the gateway at a realtime runtime; production pins the
    # URL EMPTY so no stray variable can open the WebSocket surface, and
    # the base compose never mentions it.
    assert 'INTELLIAI_RUNTIMES_STT_REALTIME_WS_URL: ""' in PROD_OVERLAY
    local_prod = (REPO / "infra/compose/local-prod.yml").read_text(encoding="utf-8")
    assert "INTELLIAI_RUNTIMES_STT_REALTIME_WS_URL: ws://" in local_prod
    assert "REALTIME" not in COMPOSE
    # The runtime-side flag defaults FALSE and no committed compose file
    # enables it in a container (the staging realtime runtime is a HOST
    # instance; containers stay batch-only).
    assert "INTELLIAI_STT_REALTIME_ENABLED" not in COMPOSE
    assert "INTELLIAI_STT_REALTIME_ENABLED" not in local_prod
    assert "INTELLIAI_STT_REALTIME_ENABLED" not in PROD_OVERLAY


def test_the_prepared_production_realtime_overlay_is_never_wired_in() -> None:
    # M54: the production realtime configuration exists as a REVIEWED
    # overlay, but enabling it must be a deliberate promotion-milestone
    # edit — nothing committed ever composes it in, and prod.yml still
    # pins the URL empty on its own.
    overlay = (REPO / "infra/compose/prod-realtime.yml").read_text(encoding="utf-8")
    assert "PREPARED, NOT ENABLED" in overlay
    assert "INTELLIAI_RUNTIMES_STT_REALTIME_WS_URL: ws://" in overlay
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    assert "prod-realtime" not in makefile
    preflight = (REPO / "infra/prod-preflight.sh").read_text(encoding="utf-8")
    assert "prod-realtime" not in preflight
    assert 'INTELLIAI_RUNTIMES_STT_REALTIME_WS_URL: ""' in PROD_OVERLAY


def test_preflight_refuses_an_enabled_stage_without_seeded_artifacts() -> None:
    preflight = (REPO / "infra/prod-preflight.sh").read_text(encoding="utf-8")
    assert "INTELLIAI_STT_PUNCTUATION_ENABLED" in preflight
    assert "punct-cap-seg-47/v1/punct_cap_seg_47lang.onnx" in preflight


def test_the_punctuation_stage_defaults_off_and_pins_the_hindi_whitelist() -> None:
    # The Settings default is the deployment law: OFF everywhere unless a
    # reviewed overlay says otherwise, and the v1 whitelist is the
    # promoted Hindi route only.
    import sys

    sys.path.insert(0, str(REPO / "services/stt-runtime/src"))
    from intelliai_stt_runtime.config import Settings as SttSettings

    defaults = SttSettings()
    assert defaults.punctuation_enabled is False
    assert defaults.punctuation_languages == "hi,hi-IN"
    assert defaults.punctuation_timeout_ms > 0


def test_seeding_is_a_prod_prerequisite_and_pinned() -> None:
    # M31: production declares the undownloadable E3 slot, so `prod-up`
    # must seed first — the same law local-prod-up always had. The seed
    # container is pinned (the repo's only formerly-unpinned image), and
    # the punctuation copy is conditional so a punctuation-less box
    # still seeds cleanly.
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    assert "\nprod-up: seed-models" in makefile
    assert "\nlocal-prod-up: staging-seed-models" in makefile
    seed = makefile[makefile.index("\nseed-models:") : makefile.index("\nstaging-seed-models:")]
    assert "alpine:3.20" in seed
    assert "if [ -d /src/punct-cap-seg-47/v1 ]" in seed
    # The M31 clean-Linux rehearsal: a root-owned seeded volume crash-loops
    # the non-root runtime on a fresh box. The seed must hand ownership to
    # the runtime's app user (uid 999) every time.
    assert "chown -R 999:999 /models" in seed
    assert ":latest" not in makefile


def test_the_edge_has_a_healthcheck_in_both_overlays() -> None:
    # The admin-endpoint probe is unique to the caddy service, so its
    # presence in the overlay text IS the caddy healthcheck.
    local_prod = (REPO / "infra/compose/local-prod.yml").read_text(encoding="utf-8")
    for overlay in (PROD_OVERLAY, local_prod):
        assert "healthcheck" in overlay
        assert "http://127.0.0.1:2019/config/" in overlay


def test_weights_and_backups_never_enter_a_build_context() -> None:
    dockerignore = (REPO / ".dockerignore").read_text(encoding="utf-8").splitlines()
    for entry in ("models/", "*.gguf", "backups/"):
        assert entry in dockerignore, f".dockerignore must exclude {entry}"


def test_prod_env_template_documents_the_m30_and_backup_knobs() -> None:
    assert "INTELLIAI_STT_PUNCTUATION_ENABLED=false" in ENV_PROD_EXAMPLE
    assert "INTELLIAI_BACKUP_KEEP" in ENV_PROD_EXAMPLE
    assert "INTELLIAI_SMOKE_API_KEY" in ENV_PROD_EXAMPLE
    # The local production-shaped example is committed (a fresh clone
    # must be able to run the staging battery without archaeology):
    assert (REPO / ".env.local-prod.example").exists()


def test_smoke_asserts_the_punctuation_posture() -> None:
    smoke = (REPO / "infra/prod-smoke.sh").read_text(encoding="utf-8")
    assert "INTELLIAI_STT_PUNCTUATION_ENABLED" in smoke
    assert '"punctuation"' in smoke


def test_the_edge_headers_carry_the_m31_hardening() -> None:
    caddyfile = (REPO / "infra/Caddyfile").read_text(encoding="utf-8")
    assert "max-age=31536000; includeSubDomains" in caddyfile
    assert 'X-Frame-Options "DENY"' in caddyfile
    assert "Permissions-Policy" in caddyfile
    assert "-Server" in caddyfile
    # No edge response timeout: the 450 s gateway deadline rules, and an
    # edge timeout below it would kill healthy 600 s chunked requests.
    assert "response_header_timeout" not in caddyfile


# ── M35: Kokoro English TTS hardening — deployment wiring guards ──────


def test_tts_dockerfile_ships_the_espeak_binary_but_bans_the_gpl_python_chain() -> None:
    dockerfile = (REPO / "infra/docker/tts-runtime.Dockerfile").read_text(encoding="utf-8")
    # The M35 exec-boundary posture: the BINARY ships via apt...
    assert "espeak-ng espeak-ng-data" in dockerfile
    # ...while the in-process GPL chain stays banned, build-fatally.
    assert "phonemizer-fork espeakng-loader" in dockerfile
    assert "banned = ['phonemizer', 'espeakng_loader']" in dockerfile


def test_dev_compose_declares_the_m35_tts_posture() -> None:
    compose = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
    assert "INTELLIAI_TTS_OOV_FALLBACK: ${INTELLIAI_TTS_OOV_FALLBACK:-espeak}" in compose


def test_local_prod_serves_tts_with_the_hardened_posture() -> None:
    # The production-shaped LOCAL stack serves TTS for the Web E2E, with
    # the posture pinned explicitly — since M42 it mirrors production.
    overlay = (REPO / "infra/compose/local-prod.yml").read_text(encoding="utf-8")
    assert "tts-runtime:" in overlay
    assert 'INTELLIAI_TTS_NORMALIZE_TEXT: "true"' in overlay
    assert "INTELLIAI_TTS_OOV_FALLBACK: espeak" in overlay
    assert 'INTELLIAI_RUNTIMES_TTS_ENABLED: "true"' in overlay
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    assert "docker compose --profile tts -f docker-compose.yml" in makefile


def test_the_prod_overlay_declares_the_promoted_tts_posture() -> None:
    # M42 (founder decision F-M42): speech synthesis is an APPROVED
    # production service. The overlay pins the exact posture the staging
    # validation proved — never inherited from a stray dev variable —
    # and the production compose actually brings the service up.
    prod = (REPO / "infra/compose/prod.yml").read_text(encoding="utf-8")
    assert "tts-runtime:" in prod
    assert "INTELLIAI_TTS_SLOTS: kokoro" in prod
    assert 'INTELLIAI_TTS_NORMALIZE_TEXT: "true"' in prod
    assert "INTELLIAI_TTS_OOV_FALLBACK: espeak" in prod
    assert "INTELLIAI_TTS_HINDI_G2P: espeak" in prod
    # Readiness must answer for what this deployment serves.
    assert 'INTELLIAI_RUNTIMES_TTS_ENABLED: "true"' in prod
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    assert (
        "PROD := docker compose --profile tts -f docker-compose.yml -f infra/compose/prod.yml"
        in makefile
    )
    # Every production target goes through that one definition.
    for target in ("$(PROD) build", "$(PROD) up -d --build", "$(PROD) down"):
        assert target in makefile


def test_the_preflight_requires_the_promoted_tts_artifact() -> None:
    # A production box must never depend on egress for a promoted
    # artifact: the preflight refuses a prod start whose TTS bytes are
    # not placed for seeding (the E3 rule, applied to synthesis).
    preflight = (REPO / "infra/prod-preflight.sh").read_text(encoding="utf-8")
    assert "models/kokoro-82m/v2" in preflight
    for pack in ("af_heart.pt", "am_michael.pt", "hf_alpha.pt", "hm_psi.pt"):
        assert pack in preflight
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    assert "/src/kokoro-82m/v2" in makefile  # seed-models places the same set


def test_the_production_smoke_covers_the_promoted_service() -> None:
    # A promoted service that nobody checks is a promise nobody keeps.
    smoke = (REPO / "infra/prod-smoke.sh").read_text(encoding="utf-8")
    assert "for service in caddy api stt-runtime tts-runtime postgres redis minio" in smoke
    assert "all seven services running" in smoke
    assert "8002/health/ready" in smoke
    assert '"hindi_g2p"' in smoke
    for voice in ("english-female", "english-male", "hindi-female", "hindi-male"):
        assert voice in smoke
    assert "/v1/audio/speech" in smoke  # one real synthesis, key-gated like transcription


def test_tts_smoke_is_the_stale_image_guard() -> None:
    # The M32 trap ("healthy, and wrong") must be mechanically catchable:
    # version floor, artifact identity, posture keys, and a real
    # gateway synthesis — all asserted by one script with a Make wrapper.
    smoke = (REPO / "infra/tts-smoke.sh").read_text(encoding="utf-8")
    assert 'VERSION_FLOOR="0.4.0"' in smoke  # M39: a pre-Hindi image FAILS
    assert "stale image" in smoke
    assert "kokoro-82m" in smoke
    assert "oov_fallback" in smoke
    assert "english-female" in smoke
    assert "RIFF" in smoke
    assert "x-runtime-envelope" in smoke
    # M39: the Hindi posture is smoke-checked BOTH ways — a deployment
    # declaring the component must serve both voices; one that does not
    # must serve neither.
    assert "hindi_g2p" in smoke
    assert "hindi-female" in smoke and "hindi-male" in smoke
    assert "without a declared hindi_g2p" in smoke
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    assert "tts-smoke:" in makefile
    assert "bash infra/tts-smoke.sh" in makefile
