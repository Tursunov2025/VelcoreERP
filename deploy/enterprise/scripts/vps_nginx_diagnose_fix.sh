#!/usr/bin/env bash
# Nginx diagnose + fix for api.velcore.uz — run as root on VPS
set -euo pipefail

SITE="api.velcore.uz"
SITE_FILE="/etc/nginx/sites-available/${SITE}"
ENABLED="/etc/nginx/sites-enabled/${SITE}"
PROJECT="/var/www/velcore"
LOG="/var/log/velcore-nginx-diagnose.log"

exec > >(tee -a "$LOG") 2>&1
run() { echo ""; echo "=== RUN: $* ==="; "$@"; }

echo "=== Velcore Nginx diagnose $(date -Iseconds) ==="

run test -d "$PROJECT"
run systemctl is-active nginx
run systemctl is-active uvicorn 2>/dev/null || pgrep -af "uvicorn main:app" || true
run curl -sf http://127.0.0.1:8000/ | head -c 300 || true
echo ""

run ss -tlnp | grep -E ':80|:8000' || true
run ufw status verbose 2>/dev/null || true

run getent hosts "$SITE" || true
run dig +short "$SITE" 2>/dev/null || true

if [[ ! -s "$SITE_FILE" ]]; then
  echo "Writing ${SITE_FILE}..."
  cat >"$SITE_FILE" <<'EOF'
upstream velcore_api {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 80;
    listen [::]:80;
    server_name api.velcore.uz;

    client_max_body_size 20M;

    location / {
        proxy_pass http://velcore_api;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_read_timeout 120s;
    }
}
EOF
else
  echo "Site file exists ($(wc -c <"$SITE_FILE") bytes)"
  run head -n 40 "$SITE_FILE"
fi

if [[ ! -L "$ENABLED" ]]; then
  run ln -sf "$SITE_FILE" "$ENABLED"
fi

for d in /etc/nginx/sites-enabled/default /etc/nginx/sites-enabled/000-default; do
  if [[ -e "$d" ]]; then
    run rm -f "$d"
  fi
done

run ls -la /etc/nginx/sites-enabled/

echo "=== server_name conflicts (nginx -T grep) ==="
nginx -T 2>/dev/null | grep -E "listen 80|server_name" | sort || true

run nginx -t
run systemctl restart nginx
run systemctl is-active nginx

echo "=== curl tests ==="
run curl -sS -D- -H "Host: ${SITE}" http://127.0.0.1/ -o /tmp/velcore-api-localhost.body | head -n 20
run head -c 400 /tmp/velcore-api-localhost.body
echo ""
run curl -sS -w "\nHTTP:%{http_code}\n" "http://${SITE}/" | tail -n 5 || true
run curl -sS -w "\nHTTP:/docs %{http_code}\n" "http://${SITE}/docs" | tail -n 3 || true

if [[ -f /etc/velcore/.env ]] && grep -q '^ENVIRONMENT=production' /etc/velcore/.env; then
  echo "NOTE: ENVIRONMENT=production disables /docs in FastAPI (docs_url=None). Use /openapi.json off or set ENVIRONMENT=development for docs."
fi

echo "=== DONE log: ${LOG} ==="
