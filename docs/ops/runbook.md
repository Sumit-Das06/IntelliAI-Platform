# Operations Runbook — IntelliAI STT v1

## Health
- `https://$DOMAIN/health/live` — process up (Docker restarts on failure of this only).
- `https://$DOMAIN/health/ready` — db/redis/storage checks; what the uptime monitor watches.
- Every response carries `X-Request-ID`; every log line for that request carries the same id. Debugging starts by grepping the id from the customer's error envelope.

## Look at things
```bash
docker compose ps                             # what's running
docker compose logs -f api                    # gateway (structured JSON)
docker compose logs -f stt-runtime            # engine
docker compose --profile tools up -d adminer  # DB browser on 127.0.0.1:8081 (ssh tunnel)
```

## Common situations
| Symptom | Meaning | Action |
|---|---|---|
| STT calls 503 `runtime_unavailable` | stt-runtime down/starting | `docker compose ps`; first boot downloads the model (≤10 min); `docker compose restart stt-runtime` |
| `collection.store_failed` in logs, requests still 200 | MinIO degraded — **by design collection fails open** | fix MinIO; nothing customer-facing happened |
| TTS calls 503 | correct — V1 is STT-only (compose profile) | nothing |
| Disk filling | audio objects + backups | check `docker system df`, MinIO volume, backup retention |

## Collection controls
```bash
make grant-consent org=org_... ref="<consent-doc>"   # tenant opt-in
make revoke-consent org=org_...                      # stops future collection immediately
# Platform-wide kill switch: INTELLIAI_COLLECTION_ENABLED=false in .env,
# then docker compose up -d api   (restart required; consent is untouched)
```

## Deletion requests (until the console ships)
Operator act: find the tenant's rows (`speech_samples` by organization), delete rows (events cascade), delete objects under `speech/{org_public_id}/` in MinIO, note the request date. Backups age out within the retention window (14 days).

## Secrets
Live only in `/opt/intelliai/.env` + your password manager. Rotating `INTELLIAI_AUTH_KEY_PEPPER` invalidates **every** API key — never casually. DB/MinIO password rotation: update `.env`, `make prod-up`.
