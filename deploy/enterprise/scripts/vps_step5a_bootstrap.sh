#!/usr/bin/env bash
# Velcore ERP — Step 5A (VPS web console as root)
# Logs every command + output to /var/log/velcore-step5a.log
#
# Option A — deploy key (recommended): set USE_DEPLOY_KEY=1 after adding key to GitHub
# Option B — PAT: export GITHUB_TOKEN="github_pat_..." before running
#
#   bash vps_step5a_bootstrap.sh
set -euo pipefail

LOG="/var/log/velcore-step5a.log"
APP_DIR="/var/www/velcore"
ENV_DIR="/etc/velcore"
ENV_FILE="${ENV_DIR}/.env"
DATA_ROOT="/var/lib/velcore/data"
VENV="${APP_DIR}/backend/.venv"
DEPLOY_KEY="/root/.ssh/velcore_deploy"
REPO_SSH="git@github.com:Tursunov2025/VelcoreERP.git"
REPO_HTTPS="https://github.com/Tursunov2025/VelcoreERP.git"

exec > >(tee -a "$LOG") 2>&1

run() {
  echo ""
  echo "=================================================================="
  echo "[$(date -Iseconds)] RUN: $*"
  echo "=================================================================="
  "$@"
}

log() { echo "[$(date -Iseconds)] $*"; }

log "=== Velcore Step 5A bootstrap started ==="
log "Log file: ${LOG}"

run apt-get update -qq
run apt-get install -y git python3 python3-venv python3-pip libpq-dev build-essential curl openssl

run mkdir -p "$APP_DIR" "$ENV_DIR"
run mkdir -p "$DATA_ROOT/uploads" "$DATA_ROOT/backups" "$DATA_ROOT/logs" "$DATA_ROOT/migrations"
run chmod 750 "$ENV_DIR"

# --- PostgreSQL ---
log "--- PostgreSQL: user azmus, database azmus_erp ---"
if ! run sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='azmus'" | grep -q 1; then
  run sudo -u postgres createuser -d azmus
fi
if ! run sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='azmus_erp'" | grep -q 1; then
  run sudo -u postgres createdb -O azmus azmus_erp
fi

DB_PASS="${VELCORE_DB_PASSWORD:-}"
if [[ -z "$DB_PASS" ]]; then
  DB_PASS="$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 24)"
  log "Generated PostgreSQL password for azmus"
fi
run sudo -u postgres psql -c "ALTER USER azmus WITH PASSWORD '${DB_PASS}';"
run sudo -u postgres psql -c "\\du azmus"
run sudo -u postgres psql -c "\\l azmus_erp"

# --- Clone private repo ---
log "--- Clone VelcoreERP (private) ---"
if [[ -d "${APP_DIR}/.git" ]]; then
  log "Repository already present — git pull"
  if [[ "${USE_DEPLOY_KEY:-0}" == "1" && -f "$DEPLOY_KEY" ]]; then
    run env GIT_SSH_COMMAND="ssh -i ${DEPLOY_KEY} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new" \
      git -C "$APP_DIR" pull --ff-only
  elif [[ -n "${GITHUB_TOKEN:-}" ]]; then
    run env GIT_TERMINAL_PROMPT=0 \
      git -C "$APP_DIR" pull --ff-only "https://x-access-token:${GITHUB_TOKEN}@github.com/Tursunov2025/VelcoreERP.git"
  else
    run git -C "$APP_DIR" pull --ff-only
  fi
else
  if [[ "${USE_DEPLOY_KEY:-0}" == "1" ]]; then
    if [[ ! -f "$DEPLOY_KEY" ]]; then
      run mkdir -p /root/.ssh
      run chmod 700 /root/.ssh
      run ssh-keygen -t ed25519 -C "velcore-vps-deploy" -f "$DEPLOY_KEY" -N ""
      log "ADD THIS DEPLOY KEY to GitHub → VelcoreERP → Settings → Deploy keys (read-only):"
      run cat "${DEPLOY_KEY}.pub"
      log "Then re-run: USE_DEPLOY_KEY=1 bash vps_step5a_bootstrap.sh"
      exit 2
    fi
    run env GIT_SSH_COMMAND="ssh -i ${DEPLOY_KEY} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new" \
      git clone "$REPO_SSH" "$APP_DIR"
  elif [[ -n "${GITHUB_TOKEN:-}" ]]; then
    run env GIT_TERMINAL_PROMPT=0 \
      git clone "https://x-access-token:${GITHUB_TOKEN}@github.com/Tursunov2025/VelcoreERP.git" "$APP_DIR"
    unset GITHUB_TOKEN || true
  else
    log "ERROR: No auth. Set GITHUB_TOKEN or USE_DEPLOY_KEY=1 (see deploy/enterprise/VPS_STEP5A_CONSOLE.md)"
    exit 1
  fi
fi

run ls -la "$APP_DIR"
for d in backend frontend deploy driver-app; do
  if [[ -d "${APP_DIR}/${d}" ]]; then
    log "OK: ${APP_DIR}/${d} exists"
  else
    log "ERROR: missing ${APP_DIR}/${d}"
    exit 1
  fi
done
run git -C "$APP_DIR" rev-parse HEAD
run git -C "$APP_DIR" log -1 --oneline

# --- Python venv ---
log "--- Python venv + requirements ---"
run python3 --version
run python3 -m venv "$VENV"
run "${VENV}/bin/pip" install --upgrade pip wheel
run "${VENV}/bin/pip" install -r "${APP_DIR}/backend/requirements.txt"
if ! "${VENV}/bin/pip" show psycopg2-binary >/dev/null 2>&1; then
  run "${VENV}/bin/pip" install psycopg2-binary
else
  log "psycopg2-binary already installed"
fi
run "${VENV}/bin/pip" list | grep -E 'fastapi|uvicorn|sqlalchemy|psycopg2'

JWT_SECRET="${VELCORE_JWT_SECRET:-$(openssl rand -hex 32)}"

# --- /etc/velcore/.env ---
log "--- Writing ${ENV_FILE} ---"
run tee "$ENV_FILE" >/dev/null <<EOF
ENVIRONMENT=production
AZMUS_ENV_FILE=${ENV_FILE}

DATA_ROOT=${DATA_ROOT}
UPLOAD_PATH=${DATA_ROOT}/uploads
BACKUP_PATH=${DATA_ROOT}/backups
LOG_PATH=${DATA_ROOT}/logs
MIGRATION_BACKUP_PATH=${DATA_ROOT}/migrations

DATABASE_URL=postgresql+psycopg2://azmus:${DB_PASS}@127.0.0.1:5432/azmus_erp

JWT_SECRET_KEY=${JWT_SECRET}
CORS_ORIGINS=https://erp.velcore.uz,http://127.0.0.1:5173

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
run chmod 600 "$ENV_FILE"
run ls -la "$ENV_FILE"

# --- Start backend ---
log "--- Start uvicorn (local test, no systemd) ---"
export AZMUS_ENV_FILE="${ENV_FILE}"
run pkill -f "uvicorn main:app" || true
sleep 2
cd "${APP_DIR}/backend"
nohup "${VENV}/bin/uvicorn" main:app --host 127.0.0.1 --port 8000 \
  >>"${DATA_ROOT}/logs/uvicorn-step5a.out.log" 2>>"${DATA_ROOT}/logs/uvicorn-step5a.err.log" &
UV_PID=$!
log "uvicorn pid=${UV_PID}"

OK=0
for i in $(seq 1 45); do
  if curl -sf "http://127.0.0.1:8000/" >/dev/null 2>&1; then
    OK=1
    break
  fi
  sleep 2
done

if [[ "$OK" -eq 1 ]]; then
  run curl -sS -D- "http://127.0.0.1:8000/" -o /tmp/velcore-root-body.json
  run head -c 800 /tmp/velcore-root-body.json
  echo ""
  log "=== STEP 5A SUCCESS ==="
  log "Backend: http://127.0.0.1:8000"
  log "Full log: ${LOG}"
  exit 0
else
  log "=== STEP 5A FAILED — backend not responding ==="
  run tail -n 60 "${DATA_ROOT}/logs/uvicorn-step5a.err.log" || true
  run tail -n 20 "${DATA_ROOT}/logs/uvicorn-step5a.out.log" || true
  exit 1
fi
