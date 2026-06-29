# Step 5A — VPS Web Console Deployment (VelcoreERP private repo)

**Server:** `89.39.95.189` · Ubuntu 24.04 · run as **root** in provider web console  
**Repo:** https://github.com/Tursunov2025/VelcoreERP (private)  
**Stop before:** Nginx, systemd, SSL

---

## 1. GitHub deployment plan (private repo)

### Recommended: **Deploy key (read-only)** — safest for VPS

| Aspect | Deploy key | Fine-grained PAT | Classic PAT |
|--------|------------|------------------|-------------|
| Scope | Single repo only | Configurable | Often too broad |
| Revocation | Remove key from repo | Revoke token | Revoke token |
| Shell history | No secret in clone URL | Risk if URL logged | Risk if URL logged |
| Rotation | Generate new key on VPS | Regenerate token | Regenerate token |

**Steps on GitHub:**

1. Open **VelcoreERP** → **Settings** → **Deploy keys** → **Add deploy key**
2. Title: `velcore-vps-89.39.95.189`
3. Paste public key from VPS (script generates it on first run)
4. Enable **Allow read access** only (do **not** allow write unless needed)
5. Save

**Clone URL:** `git@github.com:Tursunov2025/VelcoreERP.git`

### Alternative: **Fine-grained personal access token**

1. GitHub → **Settings** → **Developer settings** → **Fine-grained tokens**
2. Resource owner: your account
3. Repository access: **Only VelcoreERP**
4. Permissions: **Contents → Read-only**
5. Copy token once; use as `GITHUB_TOKEN` (never commit)

**Clone URL pattern:** `https://x-access-token:TOKEN@github.com/Tursunov2025/VelcoreERP.git`

---

## 2. Safest clone method (summary)

**Use deploy key + SSH clone.** Token in HTTPS URLs can appear in `~/.bash_history`, `/proc`, and process lists. Deploy keys are repo-scoped and read-only.

---

## 3–12. One-shot console commands

### Path A — Deploy key (recommended)

Paste into VPS web console as **root**:

```bash
set -e
LOG=/var/log/velcore-step5a.log
mkdir -p /var/www/velcore /etc/velcore /var/lib/velcore/data/{uploads,backups,logs,migrations}

# Fetch bootstrap script from public raw URL won't work (private repo).
# Option 1: paste script from repo deploy/enterprise/scripts/vps_step5a_bootstrap.sh
# Option 2: manual commands below

# Generate deploy key (first time only)
mkdir -p /root/.ssh && chmod 700 /root/.ssh
if [ ! -f /root/.ssh/velcore_deploy ]; then
  ssh-keygen -t ed25519 -C "velcore-vps-deploy" -f /root/.ssh/velcore_deploy -N ""
  echo "===== ADD THIS KEY TO GITHUB DEPLOY KEYS ====="
  cat /root/.ssh/velcore_deploy.pub
  echo "============================================="
  echo "After adding key on GitHub, run the clone block again."
  exit 0
fi

export USE_DEPLOY_KEY=1
# If script is on server:
# bash /var/www/velcore/deploy/enterprise/scripts/vps_step5a_bootstrap.sh
```

After deploy key is on GitHub:

```bash
export USE_DEPLOY_KEY=1
bash vps_step5a_bootstrap.sh   # after uploading script to /root/
```

### Path B — Fine-grained PAT (one session)

```bash
read -s GITHUB_TOKEN
echo
export GITHUB_TOKEN
bash vps_step5a_bootstrap.sh
unset GITHUB_TOKEN
history -c
```

### Manual command sequence (if not using script)

```bash
# Directories
mkdir -p /var/www/velcore /etc/velcore /var/lib/velcore/data/{uploads,backups,logs,migrations}
chmod 750 /etc/velcore

# PostgreSQL
sudo -u postgres psql -c "ALTER USER azmus WITH PASSWORD 'YOUR_STRONG_PASSWORD';"
sudo -u postgres psql -c "\du azmus"
sudo -u postgres psql -c "\l azmus_erp"

# Clone (deploy key)
GIT_SSH_COMMAND="ssh -i /root/.ssh/velcore_deploy -o IdentitiesOnly=yes" \
  git clone git@github.com:Tursunov2025/VelcoreERP.git /var/www/velcore

# Verify structure
ls -la /var/www/velcore
test -d /var/www/velcore/backend
test -d /var/www/velcore/frontend
test -d /var/www/velcore/deploy
test -d /var/www/velcore/driver-app

# Venv + deps
python3 -m venv /var/www/velcore/backend/.venv
/var/www/velcore/backend/.venv/bin/pip install -U pip wheel
/var/www/velcore/backend/.venv/bin/pip install -r /var/www/velcore/backend/requirements.txt psycopg2-binary

# /etc/velcore/.env  (edit YOUR_STRONG_PASSWORD and JWT)
cat >/etc/velcore/.env <<'EOF'
ENVIRONMENT=production
AZMUS_ENV_FILE=/etc/velcore/.env
DATA_ROOT=/var/lib/velcore/data
UPLOAD_PATH=/var/lib/velcore/data/uploads
BACKUP_PATH=/var/lib/velcore/data/backups
LOG_PATH=/var/lib/velcore/data/logs
MIGRATION_BACKUP_PATH=/var/lib/velcore/data/migrations
DATABASE_URL=postgresql+psycopg2://azmus:YOUR_STRONG_PASSWORD@127.0.0.1:5432/azmus_erp
JWT_SECRET_KEY=REPLACE_WITH_openssl_rand_hex_32
CORS_ORIGINS=https://erp.velcore.uz
DATABASE_GUARD=false
SKIP_DEMO_SEED=true
EOF
chmod 600 /etc/velcore/.env

# Start + verify
export AZMUS_ENV_FILE=/etc/velcore/.env
cd /var/www/velcore/backend
nohup .venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 \
  >>/var/lib/velcore/data/logs/uvicorn.out.log 2>>/var/lib/velcore/data/logs/uvicorn.err.log &
sleep 5
curl -v http://127.0.0.1:8000/
```

---

## Expected success output

```json
{"status":"ok","service":"Azmus CRM API",...}
```

(or similar root JSON from FastAPI)

---

## After running — send back

```bash
cat /var/log/velcore-step5a.log
curl -s http://127.0.0.1:8000/
git -C /var/www/velcore rev-parse HEAD
```

---

## Detected app metadata (from repo)

| Item | Value |
|------|--------|
| Backend entry | `backend/main.py` → `main:app` |
| Start command | `.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000` |
| Requirements | `backend/requirements.txt` + `psycopg2-binary` |
| Frontend build | `cd frontend && npm ci && npm run build` → `frontend/dist/` |
| Env loader | `AZMUS_ENV_FILE=/etc/velcore/.env` required |

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `Permission denied (publickey)` on clone | Add deploy key to GitHub or use valid PAT |
| `ModuleNotFoundError: psycopg2` | `pip install psycopg2-binary` |
| `JWT_SECRET_KEY is missing` | Set in `/etc/velcore/.env` |
| `Database guard blocked` | Set `DATABASE_GUARD=false` for fresh Postgres |
| Port 8000 in use | `pkill -f "uvicorn main:app"` |
