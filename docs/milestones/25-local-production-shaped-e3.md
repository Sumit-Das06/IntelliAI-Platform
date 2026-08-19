# Milestone 25 — Local Production-Shaped Qwen E3 Integration

| | |
|---|---|
| **Status** | COMPLETE — the stack is production-shaped and REAL Web and Android sessions (founder-driven, both languages) verified the full path through a live Cloudflare Tunnel |
| **Date** | 2026-08-19 |
| **Objective** | The exact backend/container/configuration we intend to deploy to Hostinger later, already working locally, reachable by the real Web and Android clients over HTTPS |

Labels: **[EVIDENCE]** committed JSON under `research/experiments/25-local-prod-e3/` ·
**[FACT]** verified/recorded · **[FOUNDER]** requires the founder at a browser/phone.

## 1. Starting state → 2. Local architecture

M20's production stack (base compose + Caddy TLS overlay) + M24's E3
promotion evidence. M25 adds ONE new composition —
`infra/compose/local-prod.yml` — which is the prod overlay's Caddy edge
plus the staging registry profile (hi → `qwen3-asr-0.6b-hi-ft-e3`) plus
the E3-specific runtime slot:

```
Internet → Cloudflare quick tunnel → Caddy :443 (loopback-bound) → api
                                        → stt-runtime (whisper + E3, one process)
                                        → Postgres / Redis / MinIO (private)
```

Only Caddy is tunnel-reachable; every stateful port stays on loopback
(smoke-verified). The separation from production is STRUCTURAL: the
settings layer refuses the staging profile under `INTELLIAI_ENV=prod`,
so no prod-env composition can ever serve E3; guard tests pin the
overlay's shape, the E3-specific slot string, and that no prod-* Make
target references the overlay.

## 3. Docker changes [FACT]

- `infra/compose/local-prod.yml` (new): Caddy edge (127.0.0.1:443/80),
  staging profile, E3 slot. Same images, same Dockerfiles, same base.
- `Makefile`: `local-prod-{check,build,up,migrate,health,smoke,down}`
  mirroring the prod flow; `staging-seed-models` now seeds the E3 GGUF
  too (its `.invalid` URL makes seeding mandatory, by design).
- `infra/prod-preflight.sh` / `infra/prod-smoke.sh`: gained
  `INTELLIAI_COMPOSE_OVERLAY` so the SAME battery runs against either
  shape; the preflight's posture check is overlay-aware (prod demands
  prod env; local-prod REFUSES it).
- `infra/docker/stt-runtime.Dockerfile`: `UV_HTTP_TIMEOUT=300` and
  `apt Acquire::Retries=5` — resilience hardening for large pinned
  wheels over slow links; the frozen lockfile means contents are
  byte-identical.

## 4. E3 packaging [FACT + EVIDENCE]

The stt image carries the pinned Linux llama.cpp b10344 layer
(checksum at fetch + six-hash verify at load, unchanged from M17/M20).
The rebuilt image's admission table registers E3 (M23), and the OLD
image REFUSED the E3 slot declaration with the exact guard message —
the admission law demonstrated itself during bring-up. Model bytes are
volume-seeded and store-hash-verified at load; `ready` is the artifact
check. E3 cannot resolve to base/E1/E2/latest: identity re-verified in
M24 (`identity.json`), distinctness guard-tested.

## 5. Routing [EVIDENCE — edge-gateway-drills.json + routing matrix]

Through the Caddy HTTPS edge: `hi`/`hi-IN` → E3 (runtime log names the
artifact), `en` → whisper-small, undeclared → default route
(whisper-small), `xx` → clean 400 `param=language`, missing/invalid
key → 401. The PRODUCTION profile still refuses E3 (settings
validator + live-registry pin, test-held).

## 6. HTTPS/Caddy + 7. Cloudflare Tunnel [FACT + EVIDENCE]

Caddy terminates TLS (self-signed for `localhost`; production would
use Let's Encrypt with a real domain — same Caddyfile byte-for-byte),
enforces the 30 MB body ceiling, and its security headers (HSTS,
nosniff, no Server fingerprint) ride through Cloudflare to the public
client. The tunnel is the credential-free QUICK TUNNEL:

```
cloudflared tunnel --url https://localhost:443 --no-tls-verify \
    --http-host-header localhost --origin-server-name localhost
```

(`--http-host-header` is required: Caddy's site block matches the
`localhost` host; full workflow + troubleshooting in
docs/ops/local-tunnel.md. The URL is ephemeral, printed at start,
never committed.)

## 8. Web verification [EVIDENCE + FOUNDER]

API-level, through the REAL public tunnel URL
(`tunnel-gateway-drills.json`): auth 401s, hi → E3 in 0.75 s, en →
incumbent, verbose_json single clean segment, collection ON/OFF,
correction (original immutable), malformed/empty/tiny → clean 400s,
**300 s complete through the tunnel (84 s wall)**, 602 s refused and
billed zero. Console page serves 200 through the tunnel; everything is
same-origin (the gateway serves the console), so no CORS surface
exists. **[FOUNDER]** The browser screenshot session: open
`<tunnel-url>/console/playground`, run the §3 checklist of
docs/ops/local-staging.md, capture screenshots into
`research/experiments/25-local-prod-e3/evidence/`.

## 9. Android verification [FOUNDER + FACT]

No code change: the keyboard's server address is a runtime setting —
set it to the tunnel URL, paste the API key, dictate. The release
configuration is untouched (guard: scope tests unchanged). Documented
limits: the Android call cap (150 s) binds before the backend's
600 s — SHORT dictation is the Android test surface; long audio is
Web/local-edge territory. Raising the client timeout stays a future
dedicated milestone.

## 10–12. Metering / collection / correction / long audio [EVIDENCE]

Through the production-shaped edge (`edge-gateway-drills.json`, ZERO
violations): one usage event per success, **+300.0 s and +600.0 s
exact**, 602 s refused naming the limit and billed zero, one sample
under consent, contribution-off honored, correction immutable-original.
Long audio: 300 s → 4 segments (84 s), 600 s → 7 segments (196 s),
space-join == text, real offsets — the containerized Linux runtime
matches the native walls. Through the TUNNEL: 300 s completes; 600 s
hits Cloudflare's ~100 s quick-tunnel response cap (524) and the
backend then **cancels cleanly — no partial transcript, zero billing**
(the M19 whole-request law re-proven through a real internet edge).
Test-path property only: Hostinger has no Cloudflare proxy in front.

## 13. Failure / restart [EVIDENCE — failure-drill.json]

Inside the container, two kill cycles of the llama child: readiness
truthful in **0.98 s / 0.49 s**, supervised recovery in **3.01 s /
2.77 s**, whisper served 200s during both outages, exactly one
llama-server process at the end, zero orphans, zero message leaks.
Missing-artifact refusal was demonstrated live by the old image
(admission guard); bad key → 401; invalid audio → 400; overload →
clean 503 at the admission boundary (canary + M24 ladders); >600 s →
400 billed zero.

## 14. Canary simulation [EVIDENCE — canary-sim-*.json]

Against the containerized runtime, 100 requests per share:
10% / 25% / 50% / 75% challenger — **400/400 success, zero failures**,
incumbent p50 ~1.86 s flat, challenger p50 ~1.4 s flat. Local
simulation only; no production claim.

## 15. Rollback [EVIDENCE — rollback-drill.json]

Recreating ONLY the api service from the base compose (no staging
profile) flipped Hindi back to **whisper-small** through the same
edge in seconds — no rebuild, no runtime restart, no client change;
flipping the overlay back restored E3 equally cleanly. Production
equivalence: the git revert of the promotion commit
(`ROLLBACK_HINDI_ROUTE` restates the target verbatim, test-pinned).

## 16. Production parity checklist [FACT]

| Dimension | Local production-shaped | Future Hostinger | Parity |
|---|---|---|---|
| Compose architecture | base + overlay (Caddy edge) | base + prod.yml | SAME shape; overlays differ in 3 env lines |
| Dockerfiles / images | identical files, identical builds | identical | SAME |
| Runtime image structure | vendored pinned llama + volume-seeded models | identical | SAME |
| Caddy | same Caddyfile, DOMAIN=localhost (self-signed) | real DOMAIN (Let's Encrypt) | SAME file; value differs |
| Health/readiness | same endpoints, slot-truthful | same | SAME |
| Security posture | loopback internals, headers, body ceiling, auth | same | SAME |
| Backup/migration tooling | same scripts/targets | same | SAME |
| Env variable names | same (`.env.local-prod.example` documents) | `.env.prod.example` | SAME names; values differ |
| Registry profile | staging (hi → E3) | production (hi → whisper) until promotion | THE one intended difference |
| TLS entry | Cloudflare quick tunnel → Caddy | DNS → Caddy | infrastructure-specific |

## 17. Deployment package [FACT]

Complete and Hostinger-value-free: Dockerfiles, compose files,
Caddyfile, `.env.prod.example` + `.env.local-prod.example`, Makefile
flows, model pins + seed target, healthchecks, preflight/smoke/backup/
restore scripts, runbook (docs/ops/deployment.md), and now the tunnel
guide. Hostinger needs only: VPS access, domain/DNS, production
secrets, off-box backup destination, monitoring account.

## 18–20. Tests / CI / evidence

Guard tests extended (overlay shape, E3 slot pin, prod-target
isolation, no committed tunnel hostnames); full suites + lint + mypy +
CI on the closing commit. Evidence JSONs committed under
`research/experiments/25-local-prod-e3/`:
edge-gateway-drills, tunnel-gateway-drills, failure-drill,
canary-sim-{0.10,0.25,0.50,0.75}, rollback-drill; screenshots land in
`evidence/` during the founder session.

## 21. Remaining Hostinger-only inputs

VPS access · domain + DNS · production secrets (generated on the box)
· off-box backup destination · monitoring account. Plus the M24
blockers for the ROUTE change itself: founder approval of the pending
proposal; Linux runtime re-ladder on VPS hardware.

## 22. Limitations

- Quick-tunnel edge caps held responses ≈100 s → 600 s audio cannot
  complete through THIS test path (300 s can; the local edge does both).
- Android's 150 s call cap limits phone-side long-audio testing.
- The Web/Android SCREENSHOT halves of Phases 9–10 need the founder at
  a browser/phone; every API contract those clients consume is already
  verified through the tunnel.

## 23. Exact next step once Hostinger is available

Follow docs/ops/deployment.md on the VPS with the PROD overlay
(hi → whisper) → re-ladder the Linux runtime on that hardware → the
founder's promotion decision (M24 proposal) → flip the route by the
promotion commit → 90/10 canary.

---

    LOCAL PRODUCTION-SHAPED STACK READY: YES

    WEB THROUGH TUNNEL VERIFIED: YES — founder-driven real browser session
        2026-08-19: Hindi (webm, 30.4 s) served by qwen3-asr-0.6b-hi-ft-e3,
        English (webm, 32.4 s) by whisper-small; plus the API-level battery
        incl. 300 s (real-client-verification.json)

    ANDROID THROUGH TUNNEL VERIFIED: YES — founder-driven real device session
        2026-08-19 (the existing demo APK, verified current; server address
        set at runtime, release config untouched): Hindi (wav, 23.7 s) served
        by qwen3-asr-0.6b-hi-ft-e3, English (wav, 22.1 s) by whisper-small

    HOSTINGER DEPLOYED: NO

    PRODUCTION ROUTING CHANGED: NO
