#!/usr/bin/env bash
# Stage: AI-assisted preview environments.
#   scripts/stages/preview.sh "deploy-preview/feature-x"
#   scripts/stages/preview.sh "/deploy-preview feature-x with 2 backend replicas"
#   scripts/stages/preview.sh "/destroy-preview feature-x"
# The LLM proposes the steps; aiops validates them against an allowlist (kubectl/helm,
# preview-* namespaces only, allowlisted chart/values/--set keys) before anything runs.
source "$(dirname "$0")/../lib.sh"
require kubectl helm
cd "$REPO_ROOT"

trigger="${1:?usage: preview.sh <branch-name | PR comment>}"
tag="${IMAGE_TAG:-$(cat "$ARTIFACTS_DIR/image-tag" 2>/dev/null || image_tag)}"
mode=(--execute)
[[ "${DRY_RUN:-0}" == "1" ]] && mode=(--execute --dry-run)

section "AI: preview plan for '$trigger'"
aiops preview --trigger "$trigger" --image-tag "$tag" --context "$KUBE_CONTEXT" \
  --ingress-port "$INGRESS_HTTP_PORT" "${mode[@]}"
