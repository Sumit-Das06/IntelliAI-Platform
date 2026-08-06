#!/usr/bin/env bash
# IntelliAI backup: Postgres logical dump + MinIO (consented audio) volume.
# Run on the deployment host, from the repository root:
#   ./infra/backup.sh
# Cron (03:10 UTC nightly):
#   10 3 * * * cd /opt/intelliai && ./infra/backup.sh >> backups/backup.log 2>&1
# Backups are useless on the same disk as the data — copy them OFF-BOX
# (rsync/rclone) as a second step; see docs/ops/backup.md.
set -euo pipefail

# Git Bash on Windows rewrites absolute-looking container paths (/backup)
# into host paths before Docker sees them; disable that so the script
# behaves identically on the Linux VPS and a Windows dev machine.
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'

PROJECT="${INTELLIAI_PROJECT:-intelliai}"
BACKUP_DIR="${INTELLIAI_BACKUP_DIR:-./backups}"
KEEP="${INTELLIAI_BACKUP_KEEP:-14}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"

POSTGRES_USER="${POSTGRES_USER:-intelliai}"
POSTGRES_DB="${POSTGRES_DB:-intelliai}"

mkdir -p "$BACKUP_DIR"
ABS_BACKUP_DIR="$(cd "$BACKUP_DIR" && pwd)"

# 1. Postgres: logical dump through the running container (no extra creds
#    — pg_dump runs as the container's own superuser).
docker compose -p "$PROJECT" exec -T postgres \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$ABS_BACKUP_DIR/pg-$STAMP.sql.gz"

# 2. MinIO: snapshot the volume bytes (the consented audio objects).
#    Read-only mount; tar preserves keys exactly.
docker run --rm \
  -v "${PROJECT}_miniodata:/data:ro" \
  -v "$ABS_BACKUP_DIR:/backup" \
  alpine:3.20 tar czf "/backup/minio-$STAMP.tar.gz" -C /data .

# 3. Retention: keep the newest $KEEP of each series.
ls -1t "$ABS_BACKUP_DIR"/pg-*.sql.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm --
ls -1t "$ABS_BACKUP_DIR"/minio-*.tar.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm --

echo "backup complete: pg-$STAMP.sql.gz + minio-$STAMP.tar.gz in $ABS_BACKUP_DIR (keeping $KEEP)"
