#!/usr/bin/env bash
# Velcore ERP — VPS Step 5 bootstrap (run as root on Ubuntu 24.04)
# Usage:
#   export GITHUB_TOKEN="ghp_..."   # required for private VelcoreERP clone
#   bash vps_step5_bootstrap.sh
set -euo pipefail

APP_DIR="/var/www/velcore"
ENV_DIR="/etc/velcore"
ENV_FILE="${ENV_DIR}/.env"
DATA_ROOT="/var/lib/velcore/data"
REPO_URL="https://github.com/Tursunov2025/VelcoreERP.git"
VENV="${APP_DIR}/backend/.venv"
LOG="/tmp/velcore-step5.log"

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG"; }

log "=== Velcore Step 5 bootstrap ==="

apt-get install -y python3-venv python3-pip libpq-dev build-essential curl >/dev/null 2>&1 || true

mkdir -p "$APP_DIR" "$ENV_DIR" \
  "$DATA_ROOT/uploads" "$DATA_ROOT/backups" "$DATA_ROOT/logs" "$DATA_ROOT/migrations"
chmod 750 "$ENV_DIR"

# --- PostgreSQL: ensure azmus / azmus_erp ---
log "Checking PostgreSQL..."
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='azmus'" | grep -q 1; then
  log "Creating PostgreSQL user azmus..."
  sudo -u postgres createuser -d azmus
fi
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='azmus_erp'" | grep -q 1; then
  log "Creating database azmus_erp..."
  sudo -u postgres createdb -O azmus azmus_erp
fi

DB_PASS="${VELCORE_DB_PASSWORD:-}"
if [[ -z "$DB_PASS" ]]; then
  if [[ -f "${ENV_FILE}" ]] && grep -q '^DATABASE_URL=' "${ENV_FILE}"; then
    DB_PASS="$(grep '^DATABASE_URL=' "${ENV_FILE}" | sed -n 's#.*://azmus:\([^@]*\)@.*#\1#p')"
  fi
fi
if [[ -z "$DB_PASS" ]]; then
  DB_PASS="$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 24)"
  log "Generated new PostgreSQL password for user azmus"
fi
sudo -u postgres psql -c "ALTER USER azmus WITH PASSWORD '${DB_PASS}';"

# --- Clone ---
if [[ -d "${APP_DIR}/.git" ]]; then
  log "Repo exists — git pull"
  git -C "$APP_DIR" pull --ff-only
else
  log "Cloning VelcoreERP..."
  if [[ -n "${GITHUB_TOKEN:-}" ]]; then
    git clone "https://${GITHUB_TOKEN}@github.com/Tursunov2025/VelcoreERP.git" "$APP_DIR"
  else
    git clone "$REPO_URL" "$APP_DIR"
  fi
fi

log "Repository structure:"
ls -la "$APP_DIR"
test -d "$APP_DIR/backend" && test -d "$APP_DIR/frontend"

# --- Python venv + deps ---
log "Creating venv..."
python3 -m venv "$VENV"
"${VENV}/bin/pip" install --upgrade pip wheel
"${VENV}/bin/pip" install -r "${APP_DIR}/backend/requirements.txt" psycopg2-binary

JWT_SECRET="${VELCORE_JWT_SECRET:-$(openssl rand -hex 32)}"

# --- /etc/velcore/.env ---
log "Writing ${ENV_FILE}..."
cat >"${ENV_FILE}" <<EOF
ENVIRONMENT=production
AZMUS_ENV_FILE=${ENV_FILE}

DATA_ROOT=${DATA_ROOT}
UPLOAD_PATH=${DATA_ROOT}/uploads
BACKUP_PATH=${DATA_ROOT}/backups
LOG_PATH=${DATA_ROOT}/logs
MIGRATION_BACKUP_PATH=${DATA_ROOT}/migrations

DATABASE_URL=postgresql+psycopg2://azmus:${DB_PASS}@127.0.0.1:5432/azmus_erp

JWT_SECRET_KEY=${JWT_SECRET}
CORS_ORIGINS=https://erp.velcore.uz,http://localhost:5173

HOST=127.0.0.1
PORT=8000
DATABASE_GUARD=false
SKIP_DEMO_SEED=true

AUTO_BACKUP_ENABLED=true
BACKUP_HOUR=2
BACKUP_MINUTE=0
BACKUP_RETENTION_DAYS=30
BACKUP_INCLUDE_UPLOADS=true
REMINDER_TIMEZONE=Asia/Tashkent
REMINDER_HOUR=9
REMINDER_MINUTE=0

TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
APP_URL=https://erp.velcore.uz
EOF
chmod 600 "${ENV_FILE}"

# --- Test backend ---
export AZMUS_ENV_FILE="${ENV_FILE}"
cd "${APP_DIR}/backend"

pkill -f "uvicorn main:app" 2>/dev/null || true
sleep 1
nohup "${VENV}/bin/uvicorn" main:app --host 127.0.0.1 --port 8000 \
  >>"${DATA_ROOT}/logs/uvicorn-step5.out.log" 2>>"${DATA_ROOT}/logs/uvicorn-step5.err.log" &
UV_PID=$!
log "Started uvicorn pid=${UV_PID}"

for i in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:8000/" >/dev/null; then
    log "OK: http://127.0.0.1:8000 responds"
    curl -s "http://127.0.0.1:8000/" | head -c 500
    echo
    exit 0
  fi
  sleep 2
done

log "FAIL: backend did not respond on :8000"
tail -n 40 "${DATA_ROOT}/logs/uvicorn-step5.err.log" || true
exit 1
