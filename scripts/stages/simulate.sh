#!/usr/bin/env bash
# SIMULATED job for `scripts/pipeline.sh simulate`: exercises the run-state machine, live logs,
# approval gate and AI panel without a cluster. Nothing is built or deployed. The deploy jobs DO
# call the real AI env-config step (fallback without Ollama), so the AI artifacts are genuine.
#   SIMULATE_FAIL_JOB=<job>   make that job fail (to see a failed run)
#   SIMULATE_STEP_SECONDS=1   pause between log lines
source "$(dirname "$0")/../lib.sh"
cd "$REPO_ROOT"

job="${1:?usage: simulate.sh <job>}"
pause="${SIMULATE_STEP_SECONDS:-1}"
say() { echo "[$(date -u +%T)] $*"; sleep "$pause"; }

say "SIMULATED job '$job' - no real work is performed"
case "$job" in
  lint-test)
    for step in "ruff check backend ai" "pytest backend" "pytest ai" "eslint + vite build" "helm lint" "terraform validate"; do
      say "==> $step"; say "    ok"
    done ;;
  build)
    say "==> docker build idea-board-backend:$(image_tag)"
    say "==> docker build idea-board-frontend:$(image_tag)"
    say "==> kind load (skipped in simulation)" ;;
  deploy-staging|deploy-production)
    env_name="${job#deploy-}"
    say "==> AI: environment configuration for $env_name (real call)"
    aiops env-config --environment "$env_name" --spec-file "deploy/env-specs/$env_name.txt" \
      --out "$ARTIFACTS_DIR/generated/values-$env_name.ai.yaml"
    say "==> helm upgrade --install idea-board ($env_name) [simulated]"
    say "==> health gate: pods ready, probe 10/10 OK [simulated]" ;;
  verify-staging|verify-production)
    for check in "GET /healthz" "POST /api/ideas" "GET /api/ideas" "POST blank -> 422" "GET /"; do
      say "[ ok ] $check [simulated]"
    done ;;
  *) say "nothing to simulate for '$job'" ;;
esac

if [[ "${SIMULATE_FAIL_JOB:-}" == "$job" ]]; then
  echo "SIMULATED failure requested for '$job'" >&2
  exit 1
fi
say "done"
