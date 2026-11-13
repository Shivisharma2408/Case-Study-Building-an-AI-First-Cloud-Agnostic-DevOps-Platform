#!/usr/bin/env bash
# Local pipeline runner - executes the SAME stage scripts as azure-pipelines.yml.
#
#   scripts/pipeline.sh                    # = all: lint-test build deploy-staging verify-staging promote-production
#   scripts/pipeline.sh full               # platform + all
#   scripts/pipeline.sh <stage> [arg]      # a single stage
#
# Stages:
#   platform              kind cluster + terraform apply (stack: local)
#   lint-test             ruff, pytest (api + AI validators), eslint, build, compose config, helm lint, terraform validate
#   build                 docker build (SHA tag) + kind load
#   deploy-staging        AI env-config -> helm upgrade -> AI health gate (auto-rollback)
#   verify-staging        smoke tests through the ingress
#   promote-production    deploy + verify production with the SAME image tag
#   preview "<trigger>"   AI-planned, allowlist-validated preview deploy/destroy
#   generate-iac <spec>   AI Generative IaC gated by helm lint + terraform validate
#   demo-rollback         deploy a broken backend image to staging to exercise the AI rollback
#   status                show whether the local LLM is available
source "$(dirname "$0")/lib.sh"
STAGES="$REPO_ROOT/scripts/stages"

run_stage() {
  local name="$1"; shift
  local start=$SECONDS
  section "STAGE: $name"
  "$@"
  ok "stage '$name' finished in $((SECONDS - start))s"
}

stage() {
  case "$1" in
    platform)           run_stage platform "$STAGES/platform.sh" ;;
    lint-test)          run_stage lint-test "$STAGES/lint_test.sh" ;;
    build)              run_stage build "$STAGES/build.sh" ;;
    deploy-staging)     run_stage deploy-staging "$STAGES/deploy.sh" staging ;;
    verify-staging)     run_stage verify-staging "$STAGES/verify.sh" staging ;;
    promote-production)
      run_stage deploy-production "$STAGES/deploy.sh" production
      run_stage verify-production "$STAGES/verify.sh" production ;;
    preview)            run_stage preview "$STAGES/preview.sh" "${2:?preview needs a trigger}" ;;
    generate-iac)       run_stage generate-iac "$STAGES/generate_iac.sh" "${2:?generate-iac needs a spec file}" ;;
    demo-rollback)
      warn "deploying a deliberately broken backend image to staging"
      set +e
      BACKEND_IMAGE_TAG="does-not-exist" HELM_TIMEOUT="${HELM_TIMEOUT:-90s}" run_stage demo-rollback "$STAGES/deploy.sh" staging
      rc=$?
      set -e
      (( rc != 0 )) && ok "health gate caught the bad release (exit $rc) - see artifacts/incidents/"
      kubectl_ctx -n staging get pods -l app.kubernetes.io/instance="$RELEASE_NAME"
      ;;
    status)             aiops status ;;
    *) die "unknown stage '$1' (see header of $0)" ;;
  esac
}

aiops status || true
case "${1:-all}" in
  all)  for s in lint-test build deploy-staging verify-staging promote-production; do stage "$s"; done ;;
  full) for s in platform lint-test build deploy-staging verify-staging promote-production; do stage "$s"; done ;;
  *)    stage "$@" ;;
esac
ok "pipeline complete - artifacts in ${ARTIFACTS_DIR#"$REPO_ROOT"/}/"
