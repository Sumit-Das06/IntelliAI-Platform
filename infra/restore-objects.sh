#!/usr/bin/env bash
# IntelliAI object-level restore: mirror a snapshot back into a bucket
# THROUGH A RUNNING SERVER's S3 API — the restore path drill #1 proved
# is the only dependable one (raw volume restores are not servable).
#
# Usage:
#   INTELLIAI_RESTORE_S3_URL=http://127.0.0.1:59000 \
#   INTELLIAI_RESTORE_S3_ACCESS_KEY=... \
#   INTELLIAI_RESTORE_S3_SECRET_KEY=... \
#   ./infra/restore-objects.sh backups/objects-<stamp> [bucket]
#
# The target is EXPLICIT, always: there are no defaults, so this script
# cannot accidentally point at production. For a production restore the
# target is the freshly started stack's own MinIO; for a drill it is a
# disposable container. Restoring is additive (mirror snapshot -> bucket,
# --overwrite): it never deletes objects that already exist in the
# target and are absent from the snapshot — reconciliation beyond that
# is the operator's deliberate act, not this script's.
#
# After restoring, VERIFY (docs/ops/backup.md): object count, one audio
# object's bytes, one manifest's sha256 against dataset_preparations.
set -euo pipefail

export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'

SNAPSHOT="${1:?usage: restore-objects.sh <snapshot-dir> [bucket]}"
BUCKET="${2:-${INTELLIAI_STORAGE_BUCKET:-intelliai-audio}}"
MC_IMAGE="${INTELLIAI_MC_IMAGE:-minio/minio:RELEASE.2025-09-07T16-13-09Z}"

: "${INTELLIAI_RESTORE_S3_URL:?set the RESTORE TARGET explicitly (no defaults, ever)}"
: "${INTELLIAI_RESTORE_S3_ACCESS_KEY:?restore target access key}"
: "${INTELLIAI_RESTORE_S3_SECRET_KEY:?restore target secret key}"

[[ -d "$SNAPSHOT" ]] || { echo "snapshot directory not found: $SNAPSHOT" >&2; exit 1; }
ABS_SNAPSHOT="$(cd "$SNAPSHOT" && pwd)"

# --network host reaches loopback-published drill/production targets on
# Linux; on Docker Desktop use the special host.docker.internal URL.
docker run --rm --network host \
  -e DST_URL="$INTELLIAI_RESTORE_S3_URL" \
  -e DST_KEY="$INTELLIAI_RESTORE_S3_ACCESS_KEY" \
  -e DST_SECRET="$INTELLIAI_RESTORE_S3_SECRET_KEY" \
  -v "$ABS_SNAPSHOT:/snapshot:ro" \
  --entrypoint sh "$MC_IMAGE" -c "
    mc alias set dst \"\$DST_URL\" \"\$DST_KEY\" \"\$DST_SECRET\" >/dev/null &&
    mc mb --ignore-existing dst/$BUCKET &&
    mc mirror --overwrite --quiet /snapshot dst/$BUCKET
  "

RESTORED=$(docker run --rm --network host \
  -e DST_URL="$INTELLIAI_RESTORE_S3_URL" \
  -e DST_KEY="$INTELLIAI_RESTORE_S3_ACCESS_KEY" \
  -e DST_SECRET="$INTELLIAI_RESTORE_S3_SECRET_KEY" \
  --entrypoint sh "$MC_IMAGE" -c "
    mc alias set dst \"\$DST_URL\" \"\$DST_KEY\" \"\$DST_SECRET\" >/dev/null &&
    mc ls --recursive dst/$BUCKET
  " | wc -l | tr -d ' ')
EXPECTED=$(find "$ABS_SNAPSHOT" -type f | wc -l | tr -d ' ')

if [[ "$RESTORED" -lt "$EXPECTED" ]]; then
  echo "OBJECT RESTORE INCOMPLETE: snapshot has $EXPECTED objects, target lists $RESTORED" >&2
  exit 1
fi
echo "object restore complete: $EXPECTED snapshot objects present in $BUCKET (target lists $RESTORED)"
echo "now VERIFY content per docs/ops/backup.md (count, audio bytes, manifest sha256)"
