#!/usr/bin/env bash
# Daily backup: PostgreSQL pg_dump + uploads tarball
set -euo pipefail

DATA_ROOT="${DATA_ROOT:-/var/lib/azmus/data}"
BACKUP_PATH="${BACKUP_PATH:-$DATA_ROOT/backups}"
UPLOAD_PATH="${UPLOAD_PATH:-$DATA_ROOT/uploads}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
INCLUDE_UPLOADS="${BACKUP_INCLUDE_UPLOADS:-true}"

STAMP="$(date +%Y%m%d_%H%M%S)"
DAILY_DIR="$BACKUP_PATH/daily"
mkdir -p "$DAILY_DIR"

# Parse DATABASE_URL for pg_dump
# postgresql+psycopg2://user:pass@host:port/dbname
if [[ "${DATABASE_URL:-}" =~ postgresql(\+psycopg2)?://([^:]+):([^@]+)@([^:/]+)(:([0-9]+))?/([^?]+) ]]; then
  PGUSER="${BASH_REMATCH[2]}"
  PGPASSWORD="${BASH_REMATCH[3]}"
  PGHOST="${BASH_REMATCH[4]}"
  PGPORT="${BASH_REMATCH[6]:-5432}"
  PGDATABASE="${BASH_REMATCH[7]}"
  export PGPASSWORD
  DUMP_FILE="$DAILY_DIR/azmus_${STAMP}.dump"
  pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -Fc "$PGDATABASE" -f "$DUMP_FILE"
  echo "Database backup: $DUMP_FILE"
elif [[ -f "${DB_PATH:-$DATA_ROOT/database/azmus.db}" ]]; then
  # Fallback: SQLite copy (interim migration)
  cp "${DB_PATH:-$DATA_ROOT/database/azmus.db}" "$DAILY_DIR/azmus_${STAMP}.db"
  echo "SQLite backup: $DAILY_DIR/azmus_${STAMP}.db"
else
  echo "ERROR: No DATABASE_URL or SQLite DB_PATH" >&2
  exit 1
fi

if [[ "$INCLUDE_UPLOADS" == "true" && -d "$UPLOAD_PATH" ]]; then
  UPLOADS_ARCHIVE="$DAILY_DIR/uploads_${STAMP}.tar.gz"
  tar -czf "$UPLOADS_ARCHIVE" -C "$(dirname "$UPLOAD_PATH")" "$(basename "$UPLOAD_PATH")"
  echo "Uploads backup: $UPLOADS_ARCHIVE"
fi

find "$DAILY_DIR" -type f -mtime +"$RETENTION_DAYS" -delete
echo "Backup complete at $(date -Iseconds)"
