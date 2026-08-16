#!/usr/bin/env bash
# IntelliAI restore check: prove the NEWEST Postgres backup actually
# restores, into a disposable container that never touches the live
# database. Run from the repository root:
#   ./infra/restore-check.sh
# This is the mechanical half of the restore drill in docs/ops/backup.md
# (the full drill also restores the MinIO snapshot and swaps services —
# that stays a documented, human-driven procedure). Read-only toward
# production data; the scratch container is destroyed on exit.
set -euo pipefail

export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'

BACKUP_DIR="${INTELLIAI_BACKUP_DIR:-./backups}"
SCRATCH="intelliai-restore-check"

fail() { echo "RESTORE CHECK FAILED: $*" >&2; exit 1; }

newest="$(ls -1t "$BACKUP_DIR"/pg-*.sql.gz 2>/dev/null | head -1 || true)"
[ -n "$newest" ] || fail "no pg-*.sql.gz in $BACKUP_DIR — run make prod-backup first"
echo "checking: $newest"

cleanup() { docker rm -f "$SCRATCH" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

# A generated throwaway credential for a data-free scratch container
# that lives for the length of this script — never a literal, never
# reused. The ROLE matches the dump's owner (same default as backup.sh)
# so OWNER TO statements restore without error noise.
SCRATCH_USER="${POSTGRES_USER:-intelliai}"
SCRATCH_CRED="scratch-$(date -u +%s)-$$"
docker run -d --name "$SCRATCH" \
  -e POSTGRES_USER=$SCRATCH_USER -e POSTGRES_PASSWORD=$SCRATCH_CRED -e POSTGRES_DB=restorecheck \
  postgres:16-alpine >/dev/null

# Wait for the scratch server (fresh container, no data — seconds).
for _ in $(seq 1 30); do
  if docker exec "$SCRATCH" pg_isready -U "$SCRATCH_USER" -d restorecheck >/dev/null 2>&1; then
    ready=1; break
  fi
  sleep 1
done
[ "${ready:-}" = "1" ] || fail "scratch postgres did not come up"

gunzip -c "$newest" | docker exec -i "$SCRATCH" psql -q -v ON_ERROR_STOP=1 -U "$SCRATCH_USER" -d restorecheck >/dev/null \
  || fail "psql rejected the dump — the backup is not restorable"

# The restored schema must carry a migration stamp and real tables.
revision="$(docker exec "$SCRATCH" psql -tA -U "$SCRATCH_USER" -d restorecheck \
  -c 'SELECT version_num FROM alembic_version' 2>/dev/null || true)"
[ -n "$revision" ] || fail "restored database has no alembic_version stamp"
tables="$(docker exec "$SCRATCH" psql -tA -U "$SCRATCH_USER" -d restorecheck \
  -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")"
[ "$tables" -gt 1 ] || fail "restored database has no tables"

echo "RESTORE CHECK OK — $newest restores cleanly ($tables tables, migration $revision)"
echo "note: this proves the DATABASE backup; the full drill in docs/ops/backup.md also covers objects"
