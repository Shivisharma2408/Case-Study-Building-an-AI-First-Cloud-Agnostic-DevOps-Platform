#!/usr/bin/env bash
# Smoke tests THROUGH THE INGRESS (same path a user takes):
#   GET /healthz, POST /api/ideas, GET /api/ideas contains it, validation rejects bad input, SPA served.
#   scripts/smoke-test.sh <environment>          (staging | production | preview-<name>)
#   BASE_URL / APP_HOST may be overridden (e.g. to test docker-compose: BASE_URL=http://localhost:3000 APP_HOST=localhost)
source "$(dirname "$0")/lib.sh"
require curl

env_name="${1:?usage: smoke-test.sh <environment>}"
host="${APP_HOST:-$(app_host "$env_name")}"
base="${BASE_URL:-$(app_base_url)}"
report="$ARTIFACTS_DIR/smoke-$env_name.txt"
: > "$report"
failures=0

# *.localhost names are resolved by the Host header so this works without DNS/hosts-file changes.
req() { curl -sS --max-time 10 -H "Host: $host" "$@"; }

check() { # name condition-result
  if [[ "$2" == "0" ]]; then ok "$1"; echo "PASS $1" >> "$report"
  else warn "FAILED: $1"; echo "FAIL $1" >> "$report"; failures=$((failures + 1)); fi
}

log "smoke testing http://$host (via $base)"

# 1. /healthz - allow time for ingress endpoints to update after a rollout.
#    The body is checked too: a SPA fallback (index.html with 200) must not count as healthy.
code=000; health=""
for _ in $(seq 1 30); do
  health="$(req -w $'\n%{http_code}' "$base/healthz" 2>/dev/null || true)"
  code="$(tail -n1 <<<"$health")"
  [[ "$code" == "200" && "$health" == *'"status":"ok"'* ]] && break
  sleep 3
done
check "GET /healthz returns 200 with {\"status\":\"ok\"} (got $code)" \
  "$([[ $code == 200 && $health == *'"status":"ok"'* ]]; echo $?)"

# 2. POST a unique idea.
content="smoke test ${env_name} $(date +%s)-$RANDOM"
resp="$(req -X POST -H 'Content-Type: application/json' -d "{\"content\":\"$content\"}" -w $'\n%{http_code}' "$base/api/ideas" || true)"
code="$(tail -n1 <<<"$resp")"; body="$(sed '$d' <<<"$resp")"
check "POST /api/ideas returns 201 (got $code)" "$([[ $code == 201 ]]; echo $?)"
check "POST response echoes the content" "$([[ $body == *"$content"* ]]; echo $?)"

# 3. GET lists it.
list="$(req "$base/api/ideas" || true)"
check "GET /api/ideas contains the new idea" "$([[ $list == *"$content"* ]]; echo $?)"
check "GET /api/ideas returns a JSON array" "$([[ $list == \[* ]]; echo $?)"

# 4. Validation is enforced at the edge.
code="$(req -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d '{"content":"   "}' "$base/api/ideas" || true)"
check "POST blank content is rejected with 422 (got $code)" "$([[ $code == 422 ]]; echo $?)"

# 5. Frontend is served.
page="$(req "$base/" || true)"
check "GET / serves the React app" "$([[ $page == *'id="root"'* ]]; echo $?)"

if (( failures > 0 )); then
  warn "$failures smoke check(s) failed - see $report"
  exit 1
fi
ok "all smoke checks passed for $env_name"
