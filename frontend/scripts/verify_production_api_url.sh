#!/usr/bin/env bash
# Verify production dist does not call localhost API
set -euo pipefail

DIST="${1:-dist}"
if [[ ! -d "$DIST" ]]; then
  echo "ERROR: $DIST not found — run npm run build first" >&2
  exit 1
fi

if [[ -f "$DIST/remote-api.json" ]]; then
  echo "ERROR: $DIST/remote-api.json must be removed before deploy (overrides API URL)" >&2
  exit 1
fi

if rg -l "127\.0\.0\.1:8000" "$DIST/assets"/*.js 2>/dev/null; then
  echo "ERROR: dist still contains 127.0.0.1:8000 — check .env.production" >&2
  exit 1
fi

if ! rg -q "api\.velcore\.uz" "$DIST/assets"/*.js 2>/dev/null; then
  echo "ERROR: api.velcore.uz not found in dist bundle" >&2
  exit 1
fi

echo "OK: production dist uses https://api.velcore.uz"
