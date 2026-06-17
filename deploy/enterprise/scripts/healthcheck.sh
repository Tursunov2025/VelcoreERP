#!/usr/bin/env bash
# Probe API + UI; send Telegram alert on state change
set -euo pipefail

API_URL="${HEALTHCHECK_API_URL:-https://api.azmus.uz/}"
UI_URL="${HEALTHCHECK_UI_URL:-https://erp.azmus.uz/}"
STATE_FILE="${DATA_ROOT:-/var/lib/azmus/data}/logs/healthcheck.state"
TOKEN="${TELEGRAM_BOT_TOKEN:-}"
CHAT="${TELEGRAM_CHAT_ID:-}"

mkdir -p "$(dirname "$STATE_FILE")"

api_ok=0
ui_ok=0

if curl -sf --max-time 15 "$API_URL" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"'; then
  api_ok=1
fi
if curl -sf --max-time 15 -o /dev/null -w "%{http_code}" "$UI_URL" | grep -qE '^(200|304)$'; then
  ui_ok=1
fi

current=0
[[ $api_ok -eq 1 && $ui_ok -eq 1 ]] && current=1

prev=-1
[[ -f "$STATE_FILE" ]] && prev=$(cat "$STATE_FILE" || echo -1)
echo "$current" > "$STATE_FILE"

send_tg() {
  local text="$1"
  [[ -z "$TOKEN" || -z "$CHAT" ]] && return 0
  curl -sf -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    -d "chat_id=${CHAT}" \
    --data-urlencode "text=${text}" \
    -d "parse_mode=HTML" >/dev/null || true
}

if [[ $current -eq 0 && "$prev" != "0" ]]; then
  send_tg "🔴 <b>Velcore ERP DOWN</b>
API: $API_URL → $([[ $api_ok -eq 1 ]] && echo OK || echo FAIL)
UI: $UI_URL → $([[ $ui_ok -eq 1 ]] && echo OK || echo FAIL)
$(date -Iseconds)"
elif [[ $current -eq 1 && "$prev" == "0" ]]; then
  send_tg "🟢 <b>Velcore ERP recovered</b>
$(date -Iseconds)"
fi

exit 0
