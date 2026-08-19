# Operations Runbook — IntelliAI STT v1

## Health
- `https://$DOMAIN/health/live` — process up (Docker restarts on failure of this only).
- `https://$DOMAIN/health/ready` — db/redis/storage/stt-runtime checks (a degraded runtime slot fails the runtime check); what the uptime monitor watches.
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

## Deletion requests
First-class CLI verbs since 14A (policy: docs/DATA_GOVERNANCE.md — objects before rows, ledger retained, poisoned manifests revoked loudly):

```bash
make erase-sample org=org_... sample=smp_...   # one sample
make erase-user-data org=org_... user=key_...  # one person (their key)
make erase-org org=org_...                     # whole tenant's data
```

Note the request date alongside the printed report. Backups age erased data out within the retention window (14 days). If the store is unreachable the command aborts retryably — nothing is ever *recorded* as erased that might still exist.

## Observability triage (launch minimum)
External uptime monitor on `https://$DOMAIN/health/ready` (14C sets it up); everything else is the structured logs:

```bash
docker compose logs api --since 1h | grep -c '"status_code": 401'   # bad keys
docker compose logs api --since 1h | grep -c '"status_code": 429'   # limits/quota
docker compose logs api --since 1h | grep -c '"status_code": 503'   # runtime down
docker compose logs api --since 1h | grep 'collection.failed\|collection.store_failed'
docker compose logs api --since 1h | grep 'storage_unavailable'
docker compose logs api --since 1h | grep '"event": "transcription.completed"' | grep -o '"latency_ms": [0-9.]*' | sort -t: -k2 -n | tail -5
docker compose exec api sh -c 'test -s usage-fallback.jsonl && echo "LEDGER FALLBACK NON-EMPTY — investigate NOW" || echo ok'
```

A non-empty metering fallback file is a page-the-operator signal: the customer got a response the ledger could not record.

## Secrets
Live only in `/opt/intelliai/.env` + your password manager. Rotating `INTELLIAI_AUTH_KEY_PEPPER` invalidates **every** API key — never casually. DB/MinIO password rotation: update `.env`, `make prod-up`.
