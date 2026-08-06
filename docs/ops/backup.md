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

## Notes
- Deleted-data law: user deletions are honored in the live system immediately; backups age the data out within the retention window. Never restore over a deletion without repeating the deletion.
- When MinIO is replaced by managed S3 (same API, ADR-0011), the object half of this doc becomes the provider's versioning/replication.
