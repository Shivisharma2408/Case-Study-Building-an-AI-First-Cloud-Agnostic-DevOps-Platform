#!/usr/bin/env bash
# Local pipeline runner - executes the SAME stage scripts as azure-pipelines.yml.
#
#   scripts/pipeline.sh                    # = all: lint-test build deploy-staging verify-staging promote-production
#   scripts/pipeline.sh full               # platform + all
#   scripts/pipeline.sh <stage> [arg]      # a single stage
#   scripts/pipeline.sh simulate           # cluster-free demo run (fake work, real state machine + AI env-config)
#
# Stages:
#   platform              kind cluster + terraform apply (stack: local)
#   lint-test             ruff, pytest (api + AI validators), eslint, build, compose config, helm lint, terraform validate
#   build                 docker build (SHA tag) + kind load
#   deploy-staging        AI env-config -> helm upgrade -> AI health gate (auto-rollback)
#   verify-staging        smoke tests through the ingress
#   promote-production    approval gate -> deploy + verify production with the SAME image tag
#   preview "<trigger>"   AI-planned, allowlist-validated preview deploy/destroy
#   generate-iac <spec>   AI Generative IaC gated by helm lint + terraform validate
#   demo-rollback         deploy a broken backend image to staging to exercise the AI rollback
#   status                show whether the local LLM is available
#
# Every run (except `status`) records its state in artifacts/runs/<runId>/run.json and streams
# one log per job to artifacts/runs/<runId>/logs/<job>.log, so the /pipelines UI shows live progress.
#
# Approval gate for promote-production:
#   PIPELINE_APPROVAL=ui    (default) wait for Approve/Reject in the UI or `runstate.py decide`
#   PIPELINE_APPROVAL=auto  approve immediately (Azure Pipelines: its Environment approvals gate instead)
source "$(dirname "$0")/lib.sh"
STAGES="$REPO_ROOT/scripts/stages"
RUNS_ROOT="$ARTIFACTS_DIR/runs"
PIPELINE_APPROVAL="${PIPELINE_APPROVAL:-ui}"
RUN_DIR=""

runstate() {
  MSYS_NO_PATHCONV=1 "$(python_bin)" "$REPO_ROOT/scripts/runstate.py" ${RUN_DIR:+--run-dir "$RUN_DIR"} "$@"
}

collect_ai() { runstate collect-ai --audit-dir "$ARTIFACTS_DIR/ai" --incidents-dir "$ARTIFACTS_DIR/incidents" || true; }

# Exit code of a job script -> run.json status. deploy.sh/verify.sh exit 2 after an automatic rollback.
status_for() { case "$1" in 0) echo succeeded ;; 2) echo rolledBack ;; *) echo failed ;; esac; }

# run_job <stage> <job> <command...>: output goes to the terminal AND the job log as it happens.
run_job() {
  local stage_name="$1" job="$2"; shift 2
  local log="$RUN_DIR/logs/$job.log" rc
  runstate job-start "$stage_name" "$job"
  section "JOB: $job"
  # Simulated runs keep the real stage/job graph but replace the work (no cluster needed).
  [[ "${SIMULATE:-0}" == 1 ]] && set -- "$STAGES/simulate.sh" "$job"
  set +e
  { echo "[$(date -u +%FT%TZ)] job $job started (stage $stage_name)"; "$@"; } 2>&1 | tee -a "$log"
  rc=${PIPESTATUS[0]}
  set -e
  echo "[$(date -u +%FT%TZ)] job $job finished with exit code $rc" >> "$log"
  runstate job-end "$stage_name" "$job" "$(status_for "$rc")"
  return "$rc"
}

# end_run <status> <exit code>
end_run() {
  RUN_FINISHED=1
  collect_ai
  runstate finish "$1"
  [[ "$1" == succeeded ]] && ok "run $(basename "$RUN_DIR") succeeded - artifacts/runs/$(basename "$RUN_DIR")" \
    || warn "run $(basename "$RUN_DIR") finished: $1 - artifacts/runs/$(basename "$RUN_DIR")"
  exit "$2"
}

# stage <name> [arg]: runs every job of the stage; ends the run on failure/rollback.
stage() {
  local name="$1" arg="${2:-}" rc=0 start=$SECONDS
  section "STAGE: $name"
  runstate stage-start "$name"
  case "$name" in
    platform)       run_job "$name" platform "$STAGES/platform.sh" || rc=$? ;;
    lint-test)      run_job "$name" lint-test "$STAGES/lint_test.sh" || rc=$? ;;
    build)          run_job "$name" build "$STAGES/build.sh" || rc=$? ;;
    deploy-staging) run_job "$name" deploy-staging "$STAGES/deploy.sh" staging || rc=$? ;;
    verify-staging) run_job "$name" verify-staging "$STAGES/verify.sh" staging || rc=$? ;;
    promote-production)
      approval_gate "$name" || rc=$?
      if (( rc == 0 )); then
        run_job "$name" deploy-production "$STAGES/deploy.sh" production || rc=$?
      fi
      if (( rc == 0 )); then
        run_job "$name" verify-production "$STAGES/verify.sh" production || rc=$?
      fi
      ;;
    preview)        run_job "$name" preview "$STAGES/preview.sh" "$arg" || rc=$? ;;
    generate-iac)   run_job "$name" generate-iac "$STAGES/generate_iac.sh" "$arg" || rc=$? ;;
    demo-rollback)
      warn "deploying a deliberately broken backend image to staging"
      run_job "$name" demo-rollback env BACKEND_IMAGE_TAG=does-not-exist HELM_TIMEOUT="${HELM_TIMEOUT:-90s}" \
        "$STAGES/deploy.sh" staging || rc=$?
      ;;
    *) die "unknown stage '$name'" ;;
  esac

  if (( rc == 3 || rc == 4 )); then   # approval rejected / timed out: stage already marked skipped
    collect_ai
    end_run failed 1
  fi
  local status; status="$(status_for "$rc")"
  runstate stage-end "$name" "$status"
  collect_ai
  case "$status" in
    succeeded)  ok "stage '$name' succeeded in $((SECONDS - start))s" ;;
    rolledBack) end_run rolledBack 2 ;;
    *)          end_run failed "$rc" ;;
  esac
}

approval_gate() {
  local stage_name="$1"
  if [[ "$PIPELINE_APPROVAL" == auto ]]; then
    log "approval: PIPELINE_APPROVAL=auto - proceeding to production"
    return 0
  fi
  local timeout="${PIPELINE_APPROVAL_TIMEOUT:-1800}"
  warn "waiting up to ${timeout}s for approval of '$stage_name':"
  warn "  UI : http://localhost:3000/pipelines  (Approve / Reject)"
  warn "  CLI: python scripts/runstate.py --run-dir \"$RUN_DIR\" decide approve"
  runstate wait-approval "$stage_name" --timeout "$timeout"
}

plan_for() {
  local promote="promote-production:deploy-production+verify-production"
  case "$1" in
    all|simulate) echo "lint-test build deploy-staging verify-staging $promote" ;;
    full)     echo "platform lint-test build deploy-staging verify-staging $promote" ;;
    promote-production) echo "$promote" ;;
    *)        echo "$1" ;;
  esac
}

trigger_for() { # -> "<trigger>|<detail>"
  if [[ -n "${PIPELINE_TRIGGER:-}" ]]; then echo "$PIPELINE_TRIGGER|${PIPELINE_TRIGGER_DETAIL:-}"; return; fi
  if [[ -n "${TF_BUILD:-}" ]]; then
    case "${BUILD_REASON:-}" in
      PullRequest) echo "pr|Azure Pipelines pull request validation" ;;
      Manual)      echo "manual|Azure Pipelines (queued by ${BUILD_REQUESTEDFOR:-a user})" ;;
      *)           echo "ci|Azure Pipelines ${BUILD_REASON:-CI}" ;;
    esac
    return
  fi
  if [[ "${1:-}" == preview ]]; then
    if [[ "${2:-}" == /* ]]; then echo "pr-comment|${2:-}"; else echo "branch|${2:-}"; fi
    return
  fi
  echo "manual|scripts/pipeline.sh ${*:-all}"
}

# ---------------------------------------------------------------------------------------------
target="${1:-all}"
if [[ "$target" == status ]]; then aiops status; exit 0; fi
case "$target" in
  all|full|simulate|platform|lint-test|build|deploy-staging|verify-staging|promote-production|demo-rollback) ;;
  preview|generate-iac) [[ -n "${2:-}" ]] || die "$target needs an argument (see header of $0)" ;;
  *) die "unknown stage '$target' (see header of $0)" ;;
esac

aiops status || true
IFS='|' read -r trigger trigger_detail <<<"$(trigger_for "$@")"
pipeline_name="idea-board"
if [[ "$target" == simulate ]]; then pipeline_name="idea-board (simulated)"; export SIMULATE=1; fi
branch="${BUILD_SOURCEBRANCHNAME:-$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)}"
RUN_DIR="$(runstate init --runs-root "$RUNS_ROOT" --plan "$(plan_for "$target")" --pipeline "$pipeline_name" \
  --branch "$branch" --commit "$(git_sha)" --commit-message "$(git -C "$REPO_ROOT" log -1 --format=%s 2>/dev/null)" \
  --trigger "$trigger" --trigger-detail "$trigger_detail")"
export RUN_DIR
log "run $(basename "$RUN_DIR") started - view it at http://localhost:3000/pipelines"
RUN_FINISHED=""
# Ctrl+C / unexpected error: never leave a run looking "running" forever.
trap 'if [[ -z "$RUN_FINISHED" ]]; then runstate finish failed || true; fi' EXIT

for spec in $(plan_for "$target"); do
  stage "${spec%%:*}" "${2:-}"
done
end_run succeeded 0
