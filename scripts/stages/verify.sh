#!/usr/bin/env bash
# Stage: verify an environment through the ingress. A failed smoke test triggers the
# health gate (and therefore an automatic rollback + incident summary) and fails the stage.
source "$(dirname "$0")/../lib.sh"
cd "$REPO_ROOT"

env_name="${1:?usage: verify.sh <staging|production>}"
KUBE_CONTEXT="$(kube_context_for "$env_name")"
section "Smoke tests: $env_name"
if "$REPO_ROOT/scripts/smoke-test.sh" "$env_name"; then
  ok "$env_name verified: http://$(app_host "$env_name") via $(app_base_url "$env_name")"
  exit 0
fi

section "Smoke tests failed - running health gate (may roll back)"
set +e
aiops health --namespace "$env_name" --release "$RELEASE_NAME" --context "$KUBE_CONTEXT" \
  --base-url "$(app_base_url "$env_name")" --host "$(app_host "$env_name")" --deploy-failed
rc=$?
set -e
if (( rc == 2 )); then
  warn "verification of $env_name failed - release rolled back automatically"
  exit 2   # distinct code: the pipeline records the stage as rolledBack
fi
die "verification of $env_name failed"
