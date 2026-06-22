#!/usr/bin/env bash
# Build frontend and verify API URL before VPS deploy
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FRONTEND="${ROOT}/frontend"
TEMPLATE="${FRONTEND}/.env.production.template"
ENV_FILE="${FRONTEND}/.env.production"

cd "${FRONTEND}"

if [[ -f "${TEMPLATE}" ]]; then
  cp "${TEMPLATE}" "${ENV_FILE}"
fi

if ! grep -q '^VITE_API_URL=https://api.velcore.uz' "${ENV_FILE}"; then
  echo "ERROR: ${ENV_FILE} must set VITE_API_URL=https://api.velcore.uz" >&2
  exit 1
fi

export VITE_API_URL=https://api.velcore.uz
npm ci
npm run build

rm -f dist/remote-api.json public/remote-api.json 2>/dev/null || true

if [[ -f dist/remote-api.json ]]; then
  echo "ERROR: dist/remote-api.json exists — remove before deploy" >&2
  exit 1
fi

if grep -R -l '127\.0\.0\.1:8000' dist/assets/*.js 2>/dev/null; then
  echo "ERROR: dist still contains 127.0.0.1:8000" >&2
  exit 1
fi

if ! grep -R -q 'api\.velcore\.uz' dist/assets/*.js 2>/dev/null; then
  echo "ERROR: api.velcore.uz not found in dist bundle" >&2
  exit 1
fi

echo "OK: frontend dist ready at ${FRONTEND}/dist"
ls -la dist/index.html dist/assets/index-*.js | head -5
