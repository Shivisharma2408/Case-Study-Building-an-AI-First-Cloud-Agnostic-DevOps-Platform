#!/usr/bin/env bash
# Stage: deploy one environment.
#   1. AI env-config: goal text (deploy/env-specs/<env>.txt) -> schema/policy-validated Helm values
#   2. Render with the chart's values.schema.json (fails fast on bad values)
#   3. helm upgrade --install (no --atomic: the AI health gate owns rollback so it can explain it)
#   4. AI health gate: signals -> rules + LLM -> verdict -> automatic rollback + incident summary
#
#   scripts/stages/deploy.sh <staging|production>
source "$(dirname "$0")/../lib.sh"
require kubectl helm
cd "$REPO_ROOT"

env_name="${1:?usage: deploy.sh <staging|production>}"
case "$env_name" in staging|production) ;; *) die "unknown environment '$env_name'" ;; esac
namespace="$env_name"
host="$(app_host "$env_name")"
tag="${IMAGE_TAG:-$(cat "$ARTIFACTS_DIR/image-tag" 2>/dev/null || image_tag)}"
backend_tag="${BACKEND_IMAGE_TAG:-$tag}"   # override only used by the rollback demo

# Request budgets keep AI proposals inside each namespace's ResourceQuota (minus the database).
case "$env_name" in
  staging)    cpu_budget=800;  mem_budget=768 ;;
  production) cpu_budget=1500; mem_budget=1536 ;;
esac

kubectl_ctx get namespace "$namespace" >/dev/null 2>&1 \
  || die "namespace '$namespace' missing - run 'scripts/pipeline.sh platform' (kind + terraform apply) first"

section "AI: environment configuration for $env_name"
ai_values="$ARTIFACTS_DIR/generated/values-$env_name.ai.yaml"
aiops env-config --environment "$env_name" --spec-file "deploy/env-specs/$env_name.txt" \
  --out "$ai_values" --cpu-budget "$cpu_budget" --memory-budget "$mem_budget"
sed -n '1,6p' "$ai_values"

values_args=(-f "$HELM_CHART/values-$env_name.yaml" -f "$ai_values"
  --set "backend.image.tag=$backend_tag" --set "frontend.image.tag=$tag")

section "Render manifests (chart schema validation)"
helm template "$RELEASE_NAME" "$HELM_CHART" -n "$namespace" "${values_args[@]}" > "$ARTIFACTS_DIR/manifests-$env_name.yaml"
ok "rendered $(grep -c '^kind:' "$ARTIFACTS_DIR/manifests-$env_name.yaml") objects -> artifacts/manifests-$env_name.yaml"

section "helm upgrade --install $RELEASE_NAME ($namespace, image $tag)"
deploy_failed=0
helm_ctx upgrade --install "$RELEASE_NAME" "$HELM_CHART" -n "$namespace" "${values_args[@]}" \
  --wait --timeout "${HELM_TIMEOUT:-4m}" --history-max 10 || deploy_failed=1
(( deploy_failed )) && warn "helm did not converge - handing over to the health gate"

section "AI: post-deploy health gate"
health_args=(--namespace "$namespace" --release "$RELEASE_NAME" --context "$KUBE_CONTEXT"
  --base-url "http://127.0.0.1:$INGRESS_HTTP_PORT" --host "$host" --settle "${HEALTH_SETTLE_SECONDS:-5}")
(( deploy_failed )) && health_args+=(--deploy-failed)
set +e
aiops health "${health_args[@]}"
rc=$?
set -e
case "$rc" in
  0) ok "$env_name healthy: http://$host:$INGRESS_HTTP_PORT/" ;;
  2) die "$env_name was UNHEALTHY and has been rolled back automatically - see artifacts/incidents/" ;;
  *) die "$env_name is UNHEALTHY and could not be rolled back automatically - see artifacts/incidents/" ;;
esac
