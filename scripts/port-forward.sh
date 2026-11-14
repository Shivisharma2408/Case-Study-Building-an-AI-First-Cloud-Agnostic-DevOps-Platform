#!/usr/bin/env bash
# Self-healing port-forward to an environment's frontend Service, for machines where the ingress
# controller is unavailable (see README I-15 / I-27). Use with APP_BASE_URL_<ENV>.
#
#   scripts/port-forward.sh staging 18081 &
#   scripts/port-forward.sh production 18082 &
#   scripts/port-forward.sh preview-feature-x 18083 idea-board-feature-x-frontend &   (preview releases)
#
# `kubectl port-forward svc/...` binds to ONE pod. When a rollout replaces that pod the process often
# stays alive but every connection fails, so this watchdog health-checks the tunnel every second
# and restarts it after two consecutive failures (recovery in roughly 3 seconds).
source "$(dirname "$0")/lib.sh"
require kubectl curl

env_name="${1:?usage: port-forward.sh <environment> <local port> [service]}"
port="${2:?usage: port-forward.sh <environment> <local port> [service]}"
service="${3:-idea-board-frontend}"
context="$(kube_context_for "$env_name")"
log "port-forward $env_name svc/$service -> 127.0.0.1:$port (context $context)"

pid=""
trap '[[ -n "$pid" ]] && kill "$pid" 2>/dev/null; exit 0' INT TERM EXIT
while true; do
  kubectl --context "$context" -n "$env_name" port-forward "svc/$service" "$port:8080" >/dev/null 2>&1 &
  pid=$!
  sleep 2
  fails=0
  while kill -0 "$pid" 2>/dev/null; do
    if curl -s -o /dev/null -m 2 "http://127.0.0.1:$port/nginx-health"; then fails=0; else fails=$((fails + 1)); fi
    if (( fails >= 2 )); then
      warn "port-forward $env_name unhealthy - restarting"
      kill "$pid" 2>/dev/null || true
      break
    fi
    sleep 1
  done
  wait "$pid" 2>/dev/null || true
  sleep 1
done
