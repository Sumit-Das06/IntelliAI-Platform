# Backup & Restore — IntelliAI STT v1

What must survive the loss of the box: **Postgres** (tenants, keys, usage ledger, samples, corrections, events) and **MinIO** (consented audio + training manifests). Redis is rate-limit state (expendable); the model cache re-downloads.

Three artifacts, three jobs (shaped by the two drills below):

| Artifact | Mechanism | Role |
| --- | --- | --- |
| `pg-<stamp>.sql.gz` | `pg_dump` (`infra/backup.sh`) | **Primary** database backup — restore proven |
| `objects-<stamp>/` | `mc mirror` through the S3 API (`infra/backup-objects.sh`) | **Primary** object backup — restore through a running server proven |
| `minio-<stamp>.tar.gz` | volume tar (`infra/backup.sh`) | Bit-archive of last resort — content-complete, **not servable as-is** (drill #1) |

## Backup
```bash
make backup            # pg dump + volume tar + object-level snapshot
make backup-objects    # object-level snapshot only
```
Nightly cron on the VPS:
```
10 3 * * * cd /opt/intelliai && ./infra/backup.sh >> backups/backup.log 2>&1
25 3 * * * cd /opt/intelliai && ./infra/backup-objects.sh >> backups/backup.log 2>&1
40 3 * * * rclone sync /opt/intelliai/backups remote:intelliai-backups
```
Local retention: newest 14 of each series (`INTELLIAI_BACKUP_KEEP`, `INTELLIAI_OBJECT_BACKUP_KEEP`).

**Off-box or it isn't a backup.** Two supported shapes:
- `INTELLIAI_BACKUP_S3_URL` + key/secret/bucket in the environment → `backup-objects.sh` mirrors straight to that S3-compatible remote under `objects-<stamp>/`; remote retention is the **provider's lifecycle rule** (recommended: expire `objects-*` after 14 days), never a delete from our side.
- No remote configured → local snapshot with a **loud warning**, and the rclone step above carries the whole `backups/` tree off-box.

The object script fails loudly on a source/destination count mismatch, never deletes or writes source data, and passes credentials only through the environment of a transient `mc` container (the same pinned image the stack runs).

## Pilot backup policy (14B)

- **Frequency:** nightly, all three artifacts (03:10 pg+tar, 03:25 objects, 03:40 off-box sync).
- **Retention:** 14 nightly sets locally; 14 days remotely via provider lifecycle. Erased personal data therefore ages out of every backup within 14 days (DATA_GOVERNANCE.md).
- **Encryption:** the VPS disk plus the transport (TLS to the remote). For an untrusted remote, wrap the rclone step with `rclone crypt` — configured at deployment, documented in the runbook; not required for a provider-managed private bucket.
- **Restore testing:** run the drill below **monthly** and after any storage-topology change; record every run in the drill log.

## Restore

```bash
# 1. fresh stack, empty volumes
make prod-up && make prod-migrate
# 2. postgres (proven path)
gunzip -c backups/pg-<stamp>.sql.gz | docker compose exec -T postgres psql -U intelliai intelliai
# 3. objects — THROUGH THE RUNNING SERVER's S3 API (proven path):
INTELLIAI_RESTORE_S3_URL=http://127.0.0.1:9000 \
INTELLIAI_RESTORE_S3_ACCESS_KEY=$MINIO_ROOT_USER \
INTELLIAI_RESTORE_S3_SECRET_KEY=$MINIO_ROOT_PASSWORD \
  ./infra/restore-objects.sh backups/objects-<stamp>
```

Verify, in this order: `/health/ready` all-ok → a known org's key authenticates → object count matches the snapshot → one audio object's bytes and one manifest's `sha256` against `dataset_preparations.manifest_checksum` → one read through the application path (Console → Speech Samples → play audio).

Do **not** restore the volume tar over a server (drill #1: bit-archive only). If the tar is ever the last copy standing, extract it and `mc mirror` the extracted bucket directory through a running server — objects restore; `.minio.sys` never travels.

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

### 2026-08-09 — drill #2: object-level mechanism (14B)

The answer to drill #1's FAIL, proven end to end on the dev stack with
disposable containers:

- **Object backup:** `backup-objects.sh` mirrored **41/41 objects**
  (speech audio + dataset manifests) into a dated snapshot; source and
  snapshot counts verified equal by the script itself; loud
  local-only warning emitted (no off-box remote configured yet).
- **Object restore:** `restore-objects.sh` mirrored the snapshot into a
  **fresh disposable MinIO** through its S3 API — 41/41 present.
- **Content verification, three ways:**
  1. dataset manifest: restored bytes hashed to the DB-recorded
     `sha256:e981…86a1` (1 755 bytes) — **PASS**;
  2. speech audio (`smp_27bd…`, 213 036 bytes): restored bytes
     byte-identical to live — **PASS**;
  3. **the application's own read path**: `S3ObjectStorage.get/head`
     (the exact production class) read the restored store — **PASS**.
- **Postgres re-drill:** fresh dump → isolated `postgres:16-alpine` →
  0 errors; orgs/samples/usage-events counts and alembic head
  (`bfe7e9613396`) identical to live — **PASS**.
- Live stack untouched; all drill containers/volumes removed.

Conclusion: **the platform is restorable end to end** — pg dump for the
database, `mc mirror` for objects. The volume tar remains a bit-archive
of last resort. Remaining gap: an actual off-box destination (needs
credentials; see deployment runbook).

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
