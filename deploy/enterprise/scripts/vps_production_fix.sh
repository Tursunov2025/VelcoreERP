#!/usr/bin/env bash
# Velcore ERP — production fix (Ubuntu VPS, run as root)
set -euo pipefail

APP=/var/www/velcore
ENV=/etc/velcore/.env
VENV=${APP}/backend/.venv
LOG=/var/log/velcore-production-fix.log

exec > >(tee -a "$LOG") 2>&1
echo "=== Velcore production fix $(date -Iseconds) ==="

# --- 1. Stop manual uvicorn ---
pkill -f "uvicorn main:app" 2>/dev/null || true
sleep 2

# --- 2. Pull latest code ---
cd "$APP"
git pull origin main

# --- 3. Ensure /etc/velcore/.env ---
mkdir -p /etc/velcore /var/lib/velcore/data/{uploads,backups,logs,migrations}
if [[ ! -f "$ENV" ]]; then
  cp "$APP/deploy/enterprise/env.production.example" "$ENV"
  JWT=$(openssl rand -hex 32)
  sed -i "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=${JWT}|" "$ENV"
  echo "Created $ENV — set DATABASE_URL password before continuing"
fi
chmod 600 "$ENV"

grep -q '^JWT_SECRET_KEY=.\+' "$ENV" || { echo "ERROR: JWT_SECRET_KEY missing in $ENV"; exit 1; }
grep -q '^DATABASE_URL=.\+' "$ENV" || { echo "ERROR: DATABASE_URL missing in $ENV"; exit 1; }
grep -q '^CORS_ORIGINS=.*erp.velcore.uz' "$ENV" || sed -i 's|^CORS_ORIGINS=.*|CORS_ORIGINS=https://erp.velcore.uz|' "$ENV"
grep -q '^ENABLE_API_DOCS=' "$ENV" || echo "ENABLE_API_DOCS=true" >> "$ENV"
grep -q '^AZMUS_ENV_FILE=' "$ENV" || echo "AZMUS_ENV_FILE=${ENV}" >> "$ENV"
grep -q '^DATABASE_GUARD=' "$ENV" || echo "DATABASE_GUARD=false" >> "$ENV"

# backend/.env must not override /etc/velcore/.env on VPS
for stray_env in "${APP}/backend/.env" "${APP}/.env"; do
  if [[ -f "$stray_env" ]] && grep -q '^DATABASE_URL=' "$stray_env"; then
    echo "WARNING: Removing DATABASE_URL from $stray_env (use $ENV only)"
    sed -i '/^DATABASE_URL=/d' "$stray_env"
  fi
done

# --- 4. Python deps ---
"${VENV}/bin/pip" install -U pip wheel
"${VENV}/bin/pip" install -r "${APP}/backend/requirements.txt"

# --- 5. DB connectivity + admin user ---
set -a
# shellcheck disable=SC1090
source "$ENV"
set +a
export AZMUS_ENV_FILE="$ENV"
cd "${APP}/backend"
"${VENV}/bin/python" -c "
from config.database_guard import verify_database_connectivity
verify_database_connectivity()
print('Database connectivity OK')
"
"${VENV}/bin/python" scripts/ensure_admin_user.py

# --- 6. systemd velcore.service ---
cp "${APP}/deploy/enterprise/systemd/velcore.service" /etc/systemd/system/velcore.service
systemctl daemon-reload
systemctl enable velcore.service
systemctl restart velcore.service
sleep 3
systemctl is-active velcore.service
curl -sf http://127.0.0.1:8000/ | head -c 200
echo ""
curl -sf http://127.0.0.1:8000/auth/login-users | head -c 200
echo ""

# --- 7. Rebuild frontend with correct API URL ---
cp "${APP}/frontend/.env.production.example" "${APP}/frontend/.env.production"
cd "${APP}/frontend"
if command -v npm >/dev/null 2>&1; then
  export VITE_API_URL=https://api.velcore.uz
  npm ci
  npm run build
  rm -f dist/remote-api.json public/remote-api.json 2>/dev/null || true
fi

# --- 8. nginx reload ---
nginx -t
systemctl reload nginx

echo "=== Tests ==="
curl -sf https://api.velcore.uz/ | head -c 120 || curl -sf http://127.0.0.1:8000/ | head -c 120
echo ""
curl -sf https://api.velcore.uz/auth/login-users | head -c 200
echo ""
echo "Login: admin / 1234 (change after first login)"
echo "Log: $LOG"
