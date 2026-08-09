# Backup & Restore — IntelliAI STT v1

What must survive the loss of the box: **Postgres** (tenants, keys, usage ledger, samples, corrections, events) and **MinIO** (consented audio). Redis is rate-limit state (expendable); the model cache re-downloads.

## Backup
```bash
make backup            # → ./backups/pg-<stamp>.sql.gz + minio-<stamp>.tar.gz
```
Nightly cron on the VPS:
```
10 3 * * * cd /opt/intelliai && ./infra/backup.sh >> backups/backup.log 2>&1
```
Retention: newest 14 of each series (override `INTELLIAI_BACKUP_KEEP`).

**Off-box or it isn't a backup** — second cron step, e.g.:
```
40 3 * * * rclone sync /opt/intelliai/backups remote:intelliai-backups
```
(any rsync/rclone target: your machine, B2, S3).

## Restore (drill this once after deploying)
```bash
# fresh stack, empty volumes
make prod-up && make prod-migrate
# postgres
gunzip -c backups/pg-<stamp>.sql.gz | docker compose exec -T postgres psql -U intelliai intelliai
# minio objects
docker run --rm -v intelliai_miniodata:/data -v $(pwd)/backups:/backup alpine:3.20 \
  sh -c "cd /data && tar xzf /backup/minio-<stamp>.tar.gz"
docker compose restart minio
```
Verify: `/health/ready` ok, a known org's key still authenticates, a known sample row + its audio object both present.

**Restore rules learned in the 2026-08-09 drill (below) — not optional:**

1. **First boot of a restored MinIO volume MUST use the original root
   credentials.** `.minio.sys` is bound to them; booting with different
   credentials triggered a destructive pool re-format in the drill.
   The credentials live in the same password manager as the `.env`.
2. **A tar of the live MinIO volume restores the BYTES, not a servable
   server.** In the drill, every object's `xl.meta` came back
   bit-identical, but the restored server answered `NoSuchBucket`/
   `NoSuchKey`, and `xl-single` mode has no `mc admin heal`. Volume
   tars are therefore a **bit-archive of last resort** (content is
   recoverable and was cryptographically verified), not an operational
   restore path.
3. **Action (14B, before launch): add object-level backup** — a second
   step mirroring bucket contents through the S3 API (`mc mirror
   local/intelliai-audio remote-target`), whose restore is simply
   mirroring back through a RUNNING server. Keep the volume tar as the
   secondary archive. When managed S3 replaces MinIO, provider
   versioning/replication supersedes both.

## Drill record

### 2026-08-09 — first full drill (dev stack, isolated containers)

- Backup: `infra/backup.sh` against the live dev stack →
  `pg-20260809-092937.sql.gz` (2.1 MB) + `minio-20260809-092937.tar.gz`
  (3.4 MB). Production data: none exists yet; the dev stack carried 100
  organizations, 39 speech samples, 3 frozen dataset versions, 3 READY
  preparations.
- Postgres restore into an isolated `postgres:16-alpine` container:
  **PASS** — zero SQL errors; row counts exactly 100/39/3/3; alembic
  head `bfe7e9613396` identical to live.
- Object content: **PASS (cryptographically)** — the restored volume's
  manifest `xl.meta` was md5-identical to the live volume's, and the
  inline manifest bytes hashed to the DB-recorded checksum
  `sha256:e981…86a1` (1755 bytes, 9 lines). A restored keyboard
  sample's object directory was present with its `part.1`.
- MinIO server-level restore: **FAIL** — findings 1–3 above. The tar's
  bytes are complete; the server would not serve them.
- Live stack: untouched throughout (verified healthy after teardown);
  drill containers and volumes removed.

## Notes
- Deleted-data law: user deletions are honored in the live system immediately; backups age the data out within the retention window. Never restore over a deletion without repeating the deletion.
- When MinIO is replaced by managed S3 (same API, ADR-0011), the object half of this doc becomes the provider's versioning/replication.
