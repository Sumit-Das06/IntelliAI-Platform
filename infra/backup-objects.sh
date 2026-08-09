#!/usr/bin/env bash
# IntelliAI object-level backup: mirror the audio/dataset bucket through
# the S3 API into a dated snapshot. This is the PRIMARY object backup —
# drill #1 (docs/ops/backup.md) proved that tarring the MinIO volume
# yields a bit-archive, not a servable restore; mirroring through the
# API restores through the API, which is the path that provably works.
#
# Run on the deployment host, from the repository root:
#   ./infra/backup-objects.sh
# Cron (03:25 UTC nightly, between the pg dump and the off-box sync):
#   25 3 * * * cd /opt/intelliai && ./infra/backup-objects.sh >> backups/backup.log 2>&1
#
# Destination:
#   - INTELLIAI_BACKUP_S3_URL unset  -> local snapshot directory
#     backups/objects-<stamp>/ with retention pruning. LOUDLY marked
#     local-only: a backup on the same disk is a convenience copy, not
#     disaster recovery — the off-box step is rclone/`mc mirror` of the
#     backups/ tree, or a direct remote here once credentials exist.
#   - INTELLIAI_BACKUP_S3_URL + _ACCESS_KEY + _SECRET_KEY + _BUCKET set
#     -> mirror straight to that S3-compatible remote under
#     objects-<stamp>/. Remote retention is the provider's lifecycle
#     rule (documented in docs/ops/backup.md), never this script's rm.
#
# Credentials: source-side come from the stack's own .env (MinIO root),
# destination-side from the INTELLIAI_BACKUP_S3_* variables. They travel
# via environment into a transient container — never argv, never logged,
# never echoed. Nothing here ever deletes or writes source objects
# (mirror src -> dst only; retention prunes SNAPSHOTS, never the bucket).
set -euo pipefail

# Git Bash on Windows rewrites absolute-looking container paths before
# Docker sees them; disable so the script behaves identically on the
# Linux VPS and a Windows dev machine.
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'

PROJECT="${INTELLIAI_PROJECT:-intelliai}"
NETWORK="${PROJECT}_intelliai"
BACKUP_DIR="${INTELLIAI_BACKUP_DIR:-./backups}"
KEEP="${INTELLIAI_OBJECT_BACKUP_KEEP:-14}"
BUCKET="${INTELLIAI_STORAGE_BUCKET:-intelliai-audio}"
# The SAME pinned image the stack already runs — it ships `mc`, so the
# backup tool can never drift from the server version.
MC_IMAGE="${INTELLIAI_MC_IMAGE:-minio/minio:RELEASE.2025-09-07T16-13-09Z}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"

# Source credentials: the stack's own root credentials, from the same
# .env compose reads. Allow real env to take precedence (prod hosts may
# export instead of using a file).
if [[ -z "${MINIO_ROOT_USER:-}" || -z "${MINIO_ROOT_PASSWORD:-}" ]]; then
  if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
  fi
fi
: "${MINIO_ROOT_USER:?MINIO_ROOT_USER not set (source .env or export it)}"
: "${MINIO_ROOT_PASSWORD:?MINIO_ROOT_PASSWORD not set (source .env or export it)}"

mkdir -p "$BACKUP_DIR"
ABS_BACKUP_DIR="$(cd "$BACKUP_DIR" && pwd)"

run_mc() {
  # $1 = shell snippet executed inside the transient mc container.
  # Aliases are configured from env INSIDE the container (mc alias set),
  # so credentials never appear in argv or in this script's output.
  docker run --rm --network "$NETWORK" \
    -e SRC_URL="http://minio:9000" \
    -e SRC_KEY="$MINIO_ROOT_USER" \
    -e SRC_SECRET="$MINIO_ROOT_PASSWORD" \
    -e DST_URL="${INTELLIAI_BACKUP_S3_URL:-}" \
    -e DST_KEY="${INTELLIAI_BACKUP_S3_ACCESS_KEY:-}" \
    -e DST_SECRET="${INTELLIAI_BACKUP_S3_SECRET_KEY:-}" \
    -v "$ABS_BACKUP_DIR:/backup" \
    --entrypoint sh "$MC_IMAGE" -c "$1"
}

if [[ -n "${INTELLIAI_BACKUP_S3_URL:-}" ]]; then
  : "${INTELLIAI_BACKUP_S3_ACCESS_KEY:?set with INTELLIAI_BACKUP_S3_URL}"
  : "${INTELLIAI_BACKUP_S3_SECRET_KEY:?set with INTELLIAI_BACKUP_S3_URL}"
  : "${INTELLIAI_BACKUP_S3_BUCKET:?set with INTELLIAI_BACKUP_S3_URL}"
  DEST_DESC="remote ${INTELLIAI_BACKUP_S3_URL}/${INTELLIAI_BACKUP_S3_BUCKET}/objects-$STAMP"
  run_mc "
    mc alias set src \"\$SRC_URL\" \"\$SRC_KEY\" \"\$SRC_SECRET\" >/dev/null &&
    mc alias set dst \"\$DST_URL\" \"\$DST_KEY\" \"\$DST_SECRET\" >/dev/null &&
    mc mirror --quiet src/$BUCKET dst/$INTELLIAI_BACKUP_S3_BUCKET/objects-$STAMP
  "
  SRC_COUNT=$(run_mc "mc alias set src \"\$SRC_URL\" \"\$SRC_KEY\" \"\$SRC_SECRET\" >/dev/null && mc ls --recursive src/$BUCKET" | wc -l | tr -d ' ')
  DST_COUNT=$(run_mc "mc alias set dst \"\$DST_URL\" \"\$DST_KEY\" \"\$DST_SECRET\" >/dev/null && mc ls --recursive dst/$INTELLIAI_BACKUP_S3_BUCKET/objects-$STAMP" | wc -l | tr -d ' ')
else
  DEST_DESC="LOCAL $ABS_BACKUP_DIR/objects-$STAMP (NOT off-box — see docs/ops/backup.md)"
  run_mc "
    mc alias set src \"\$SRC_URL\" \"\$SRC_KEY\" \"\$SRC_SECRET\" >/dev/null &&
    mc mirror --quiet src/$BUCKET /backup/objects-$STAMP
  "
  SRC_COUNT=$(run_mc "mc alias set src \"\$SRC_URL\" \"\$SRC_KEY\" \"\$SRC_SECRET\" >/dev/null && mc ls --recursive src/$BUCKET" | wc -l | tr -d ' ')
  DST_COUNT=$(find "$ABS_BACKUP_DIR/objects-$STAMP" -type f | wc -l | tr -d ' ')

  # Retention prunes local SNAPSHOT DIRECTORIES only — never the bucket.
  ls -1dt "$ABS_BACKUP_DIR"/objects-*/ 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -rf --
fi

# Fail LOUDLY on a count mismatch: a partial backup that reports success
# is worse than no backup.
if [[ "$SRC_COUNT" != "$DST_COUNT" ]]; then
  echo "OBJECT BACKUP FAILED: source has $SRC_COUNT objects, snapshot has $DST_COUNT" >&2
  exit 1
fi

echo "object backup complete: $SRC_COUNT objects -> $DEST_DESC (keeping $KEEP local snapshots)"
if [[ -z "${INTELLIAI_BACKUP_S3_URL:-}" ]]; then
  echo "WARNING: snapshot is on the SAME HOST as the data. Configure the" >&2
  echo "         off-box step (INTELLIAI_BACKUP_S3_* or rclone of backups/)" >&2
  echo "         before calling this a production backup." >&2
fi
