# Test Results and Verification Evidence

| Document | Test results: The Idea Board platform |
|---|---|
| Date of execution | 2026-11-13 / 2026-11-14 |
| Environment | Windows 11 ARM64, Git Bash, Docker Desktop, kind (single node, Kubernetes v1.32.0) |
| Commit | `16dc127` (+ `scripts/port-forward.sh`, uncommitted at build time, hence image tag `16dc12755450-dirty`) |
| Related | [README](../README.md): see section 13 (summary) and section 14 (issues register) |

All output below is copied **verbatim** from the actual runs (ANSI colours removed; lines longer than 220 characters
are shortened with `…`). Nothing was edited by hand.

**Conditions to keep in mind when reading this report**

- **No LLM was installed.** Every AI step ran in its documented **deterministic-fallback** mode
  (`[AI FALLBACK] … Ollama not reachable`). The LLM path is covered by the unit tests in section 2.
- **The ingress controller image couldn't be downloaded on this network** (README I-15). Cluster traffic therefore
  went through `scripts/port-forward.sh` (`APP_BASE_URL_<ENV>=http://127.0.0.1:1808x`) with the correct `Host`
  header. Everything behind the ingress (Ingress objects, Services, NetworkPolicies, PSA, quotas, probes) ran for real.

## Summary

| # | Test area | Result |
|---|---|---|
| 1 | Toolchain versions | recorded |
| 2 | Backend unit/API tests (pytest) | **30 / 30 passed** |
| 3 | AI tooling tests (pytest) | **87 / 87 passed** |
| 4 | Frontend: ESLint, Vitest, Playwright | **lint clean, 20 / 20, 2 / 2 passed** |
| 5 | Pipeline stage `lint-test` + `build` (run #20261114.10) | **passed** |
| 6 | Docker Compose stack + smoke tests | **3 / 3 healthy, 7 / 7 passed** |
| 7 | `deploy-staging` + `verify-staging` (run #20261114.10) | **healthy, 7 / 7 passed** |
| 8 | `promote-production` (run 2026-11-13) | **healthy, 7 / 7 passed** |
| 9 | Cluster state (kind) | **all workloads Running / Ready** |
| 10 | Automatic rollback (`demo-rollback`) | **detected and rolled back as designed** |
| 11 | Preview environment lifecycle | **deployed, 7 / 7 passed, destroyed** |
| 12 | Pipelines API security checks | **all rejected as expected** |

---

## 1. Toolchain versions

```text
$ docker --version; docker compose version; kind version; kubectl version --client; helm version --short; terraform version; python --version; node --version
Docker version 29.9.3, build 5457199
Docker Compose version v5.7.0
kind v0.26.0 go1.23.4 windows/amd64
Client Version: v1.36.1
v3.16.4
Terraform v1.9.8
Python 3.12.10
v26.12.1
```

## 2. Backend tests: `cd backend && python -m pytest -vv`

```text
tests/test_api.py::test_healthz PASSED
tests/test_api.py::test_readyz PASSED
tests/test_api.py::test_list_is_empty_initially PASSED
tests/test_api.py::test_create_returns_created_idea PASSED
tests/test_api.py::test_list_returns_newest_first PASSED
tests/test_api.py::test_invalid_payloads_are_rejected[payload0] PASSED
tests/test_api.py::test_invalid_payloads_are_rejected[payload1] PASSED
tests/test_api.py::test_invalid_payloads_are_rejected[payload2] PASSED
tests/test_api.py::test_invalid_payloads_are_rejected[payload3] PASSED
tests/test_api.py::test_invalid_payloads_are_rejected[payload4] PASSED
tests/test_api.py::test_invalid_payloads_are_rejected[payload5] PASSED
tests/test_api.py::test_invalid_payloads_are_rejected[payload6] PASSED
tests/test_api.py::test_settings_build_url_from_discrete_vars PASSED
tests/test_api.py::test_database_url_takes_precedence PASSED
tests/test_pipelines.py::test_list_runs_newest_first PASSED
tests/test_pipelines.py::test_get_run PASSED
tests/test_pipelines.py::test_get_log_is_plain_text PASSED
tests/test_pipelines.py::test_missing_log_is_empty_not_error PASSED
tests/test_pipelines.py::test_unknown_run_is_404 PASSED
tests/test_pipelines.py::test_path_traversal_and_bad_ids_are_rejected[/api/pipelines/..%2Fsecret.txt] PASSED
tests/test_pipelines.py::test_path_traversal_and_bad_ids_are_rejected[/api/pipelines/..%2F..%2Fetc] PASSED
tests/test_pipelines.py::test_path_traversal_and_bad_ids_are_rejected[/api/pipelines/20261114-100000-aaaa/logs/..%2F..%2F..%2Fsecret] PASSED
tests/test_pipelines.py::test_path_traversal_and_bad_ids_are_rejected[/api/pipelines/20261114-100000-aaaa/logs/build.log] PASSED
tests/test_pipelines.py::test_path_traversal_and_bad_ids_are_rejected[/api/pipelines/20261114-100000-aaaa/logs/BUILD] PASSED
tests/test_pipelines.py::test_path_traversal_and_bad_ids_are_rejected[/api/pipelines/not-a-run-id] PASSED
tests/test_pipelines.py::test_approve_records_decision PASSED
tests/test_pipelines.py::test_reject_records_decision PASSED
tests/test_pipelines.py::test_approve_requires_waiting_run PASSED
tests/test_pipelines.py::test_approve_validates_body PASSED
tests/test_pipelines.py::test_runs_disabled_without_directory PASSED
======================== 30 passed, 1 warning in 1.69s ========================
```

## 3. AI tooling tests: `cd ai && python -m pytest -vv`

```text
tests/test_commands.py::test_baseline_upgrade_is_valid PASSED
tests/test_commands.py::test_dangerous_commands_are_rejected[argv0-not allowlisted] PASSED
tests/test_commands.py::test_dangerous_commands_are_rejected[argv1-not allowlisted] PASSED
tests/test_commands.py::test_dangerous_commands_are_rejected[argv2-not allowlisted] PASSED
tests/test_commands.py::test_dangerous_commands_are_rejected[argv3-secrets] PASSED
tests/test_commands.py::test_dangerous_commands_are_rejected[argv4-differs from the expected] PASSED
tests/test_commands.py::test_dangerous_commands_are_rejected[argv5-forbidden] PASSED
tests/test_commands.py::test_dangerous_commands_are_rejected[argv6-forbidden] PASSED
tests/test_commands.py::test_dangerous_commands_are_rejected[argv7-not an allowlisted local chart] PASSED
tests/test_commands.py::test_dangerous_commands_are_rejected[argv8-not an allowlisted local chart] PASSED
tests/test_commands.py::test_dangerous_commands_are_rejected[argv9---install] PASSED
tests/test_commands.py::test_dangerous_commands_are_rejected[argv10-release 'other-app'] PASSED
tests/test_commands.py::test_dangerous_commands_are_rejected[argv11-not permitted] PASSED
tests/test_commands.py::test_dangerous_commands_are_rejected[argv12-not permitted] PASSED
tests/test_commands.py::test_dangerous_commands_are_rejected[argv13-not permitted] PASSED
tests/test_commands.py::test_dangerous_commands_are_rejected[argv14-forbidden characters] PASSED
tests/test_commands.py::test_dangerous_commands_are_rejected[argv15-forbidden characters] PASSED
tests/test_commands.py::test_dangerous_commands_are_rejected[argv16-forbidden] PASSED
tests/test_commands.py::test_set_keys_are_allowlisted[backend.replicaCount=2-True] PASSED
tests/test_commands.py::test_set_keys_are_allowlisted[ingress.host=feature-x.preview.ideaboard.localhost-True] PASSED
tests/test_commands.py::test_set_keys_are_allowlisted[database.existingSecret=prod-db-False] PASSED
tests/test_commands.py::test_set_keys_are_allowlisted[backend.image.tag=a,frontend.image.tag=b-False] PASSED
tests/test_commands.py::test_set_keys_are_allowlisted[networkPolicy.enabled=false-False] PASSED
tests/test_commands.py::test_values_files_are_allowlisted PASSED
tests/test_commands.py::test_preview_policy_never_touches_production PASSED
tests/test_commands.py::test_destroy_policy_allows_only_the_expected_namespace PASSED
tests/test_commands.py::test_rollback_policy PASSED
tests/test_commands.py::test_plan_size_limits PASSED
tests/test_commands.py::test_execute_refuses_invalid_plan_and_never_runs_anything PASSED
tests/test_commands.py::test_execute_injects_context_and_stops_on_failure PASSED
tests/test_commands.py::test_execute_dry_run PASSED
tests/test_envconfig.py::test_classify[Cost-sensitive staging. Verify releases before production.-cost-sensitive] PASSED
tests/test_envconfig.py::test_classify[High-availability production, zero downtime-high-availability] PASSED
tests/test_envconfig.py::test_classify[Just a normal environment-balanced] PASSED
tests/test_envconfig.py::test_classify[Cost-sensitive staging environment. It is used by the team to verify releases before\nproduction, carries almos … ] PASSED
tests/test_envconfig.py::test_classify[High-availability production environment. It must survive the loss of a pod or a node\nand node drains during m … ] PASSED
tests/test_envconfig.py::test_safe_defaults_satisfy_their_own_policy[cost-sensitive] PASSED
tests/test_envconfig.py::test_safe_defaults_satisfy_their_own_policy[balanced] PASSED
tests/test_envconfig.py::test_safe_defaults_satisfy_their_own_policy[high-availability] PASSED
tests/test_envconfig.py::test_valid_llm_profile_is_used PASSED
tests/test_envconfig.py::test_llm_cannot_downgrade_high_availability PASSED
tests/test_envconfig.py::test_invalid_llm_profiles_fall_back[<lambda>-cpu request exceeds limit] PASSED
tests/test_envconfig.py::test_invalid_llm_profiles_fall_back[<lambda>-replicaCount] PASSED
tests/test_envconfig.py::test_invalid_llm_profiles_fall_back[<lambda>-memory] PASSED
tests/test_envconfig.py::test_invalid_llm_profiles_fall_back[<lambda>-PDB minAvailable] PASSED
tests/test_envconfig.py::test_invalid_llm_profiles_fall_back[<lambda>-Additional properties] PASSED
tests/test_envconfig.py::test_invalid_llm_profiles_fall_back[<lambda>-minReplicas] PASSED
tests/test_envconfig.py::test_budget_is_enforced PASSED
tests/test_envconfig.py::test_helm_values_are_chart_compatible PASSED
tests/test_health.py::test_healthy_release_has_no_findings PASSED
tests/test_health.py::test_crashloop_is_critical PASSED
tests/test_health.py::test_image_pull_failure_is_critical PASSED
tests/test_health.py::test_probe_errors_are_critical_and_latency_is_warning PASSED
tests/test_health.py::test_single_restart_and_few_errors_are_warnings PASSED
tests/test_health.py::test_no_pods_is_critical PASSED
tests/test_health.py::test_failed_install_relabelled_superseded_is_not_a_rollback_target PASSED
tests/test_health.py::test_previous_good_revision PASSED
tests/test_health.py::test_llm_cannot_veto_rule_mandated_rollback PASSED
tests/test_health.py::test_llm_escalation_needs_corroboration PASSED
tests/test_health.py::test_contradictory_llm_verdict_is_rejected PASSED
tests/test_health.py::test_fallback_summary_mentions_findings PASSED
tests/test_health.py::test_gate_rolls_back_and_writes_incident PASSED
tests/test_health.py::test_gate_first_install_cannot_roll_back PASSED
tests/test_health.py::test_gate_healthy PASSED
tests/test_llm_and_geniac.py::test_ollama_client_happy_path PASSED
tests/test_llm_and_geniac.py::test_ollama_client_missing_model PASSED
tests/test_llm_and_geniac.py::test_ollama_client_unreachable PASSED
tests/test_llm_and_geniac.py::test_load_example_spec PASSED
tests/test_llm_and_geniac.py::test_invalid_spec_is_rejected PASSED
tests/test_llm_and_geniac.py::test_geniac_fallback_renders_files PASSED
tests/test_llm_and_geniac.py::test_geniac_rejects_inconsistent_llm_sizing PASSED
tests/test_preview.py::test_parse_branch_trigger PASSED
tests/test_preview.py::test_parse_comment_trigger_with_instructions PASSED
tests/test_preview.py::test_parse_destroy_comment PASSED
tests/test_preview.py::test_parse_rejects_non_triggers[main] PASSED
tests/test_preview.py::test_parse_rejects_non_triggers[deploy-preview/] PASSED
tests/test_preview.py::test_parse_rejects_non_triggers[/deploy-preview] PASSED
tests/test_preview.py::test_parse_rejects_non_triggers[feature/x] PASSED
tests/test_preview.py::test_parse_rejects_bad_image_tag PASSED
tests/test_preview.py::test_llm_unavailable_falls_back_to_deterministic_plan PASSED
tests/test_preview.py::test_valid_llm_plan_is_accepted_and_audited PASSED
tests/test_preview.py::test_malicious_llm_plan_is_rejected[malicious_step0] PASSED
tests/test_preview.py::test_malicious_llm_plan_is_rejected[malicious_step1] PASSED
tests/test_preview.py::test_malicious_llm_plan_is_rejected[malicious_step2] PASSED
tests/test_preview.py::test_llm_plan_must_pin_image_tag PASSED
tests/test_preview.py::test_non_json_output_falls_back PASSED
tests/test_preview.py::test_ai_disabled PASSED
============================= 87 passed in 0.31s ==============================
```

## 4. Frontend

### 4.1 ESLint and Vitest

```text
$ npm run lint
> idea-board-frontend@1.0.0 lint
> eslint . --max-warnings 0
(exit 0: no problems)

$ npx vitest run --reporter=verbose
 ✓ src/pipelines/status.test.ts > status → colour mapping > succeeded is green
 ✓ src/pipelines/status.test.ts > status → colour mapping > failed is red
 ✓ src/pipelines/status.test.ts > status → colour mapping > skipped is grey
 ✓ src/pipelines/status.test.ts > status → colour mapping > pending is grey
 ✓ src/pipelines/status.test.ts > status → colour mapping > running is blue
 ✓ src/pipelines/status.test.ts > status → colour mapping > waitingApproval is amber
 ✓ src/pipelines/status.test.ts > status → colour mapping > rolledBack is orange
 ✓ src/pipelines/status.test.ts > status → colour mapping > covers every status in the run.json contract
 ✓ src/pipelines/status.test.ts > status → colour mapping > falls back safely for unknown values
 ✓ src/pipelines/status.test.ts > status → colour mapping > only running and waitingApproval keep polling alive
 ✓ src/pipelines/status.test.ts > formatting > formats durations like the Azure DevOps run view
 ✓ src/pipelines/status.test.ts > formatting > formats relative times
 ✓ src/pipelines/StageGraph.test.tsx > StageGraph > renders every stage from run.json in order with its status
 ✓ src/pipelines/StageGraph.test.tsx > StageGraph > shows job rows only for expanded stages, with status and duration
 ✓ src/pipelines/StageGraph.test.tsx > StageGraph > toggles a stage and selects a job on click
 ✓ src/pipelines/StageGraph.test.tsx > StageGraph > disables not-started and skipped jobs
 ✓ src/pipelines/StageGraph.test.tsx > StageGraph > shows the approval gate and forwards the decision
 ✓ src/pipelines/StageGraph.test.tsx > AI panel and rollback banner > marks fallback and failed validation
 ✓ src/pipelines/StageGraph.test.tsx > AI panel and rollback banner > shows the incident summary for a rolled-back run
 ✓ src/pipelines/StageGraph.test.tsx > AI panel and rollback banner > shows no banner for a healthy run
 Test Files  2 passed (2)
      Tests  20 passed (20)
```

### 4.2 Playwright end-to-end: `PW_CHANNEL=msedge npx playwright test`

```text
Running 2 tests using 1 worker
  ✓  1 [chromium] › pipelines.spec.ts:18:1 › pipelines page shows the latest run, its stages and a job log (1.9s)
  ✓  2 [chromium] › pipelines.spec.ts:38:1 › navigation keeps the Idea Board reachable (909ms)
  2 passed (8.6s)
```

## 5. Pipeline run #20261114.10: stages `lint-test` and `build`

Command: `bash scripts/pipeline.sh` (with `HEALTH_SETTLE_SECONDS=20` and `APP_BASE_URL_<ENV>` port-forwards).

```text
==> STAGE: lint-test
==> JOB: lint-test
==> Python: ruff (backend + ai)
All checks passed!
All checks passed!
==> Backend: pytest
30 passed, 1 warning in 2.67s
==> AI tooling: pytest (validators, fallbacks, health gate)
87 passed in 0.53s
==> Frontend: eslint + vitest + typecheck + build
 Test Files  2 passed (2)
      Tests  20 passed (20)
✓ built in 1.30s
==> docker compose config
[ ok ] docker-compose.yml is valid
==> Helm: lint (all environment value sets) + render
==> Linting deploy/helm/idea-board
1 chart(s) linted, 0 chart(s) failed
==> Linting deploy/helm/idea-board
1 chart(s) linted, 0 chart(s) failed
==> Linting deploy/helm/idea-board
1 chart(s) linted, 0 chart(s) failed
==> Linting deploy/helm/idea-board
1 chart(s) linted, 0 chart(s) failed
==> Linting deploy/helm/service
1 chart(s) linted, 0 chart(s) failed
==> Terraform: fmt + validate (local, aws, gcp roots)
[ ok ] variables-common.tf identical across provider roots
[20:58:28] stack=local cloud=local root=infra/terraform/providers/local cmd=validate
Success! The configuration is valid.
[20:58:39] stack=staging cloud=aws root=infra/terraform/providers/aws cmd=validate
Success! The configuration is valid.
[20:58:59] stack=production cloud=aws root=infra/terraform/providers/aws cmd=validate
Success! The configuration is valid.
[ ok ] lint-test stage passed
[ ok ] stage 'lint-test' succeeded in 81s
==> STAGE: build
==> JOB: build
==> Build images (tag 16dc12755450-dirty)
#15 naming to docker.io/library/idea-board-backend:16dc12755450-dirty done
#18 naming to docker.io/library/idea-board-frontend:16dc12755450-dirty
#18 naming to docker.io/library/idea-board-frontend:16dc12755450-dirty done
==> Load images into kind cluster 'idea-board'
Image: "idea-board-backend:16dc12755450-dirty" with ID "sha256:0713116de9d6f6e73a1ca20d88b5f2390c91055829ca59e42597578bc5a61bd7" not yet present on node "idea-board-control-plane", loading...
Image: "idea-board-frontend:16dc12755450-dirty" with ID "sha256:086a4b38e14c17bb64cb503f2db64a4a23963acb5f40d0ca9c3b3643f292ea7a" not yet present on node "idea-board-control-plane", loading...
[ ok ] images idea-board-{backend,frontend}:16dc12755450-dirty
[ ok ] stage 'build' succeeded in 32s
```

## 6. Docker Compose stack

```text
$ docker compose ps
SERVICE    IMAGE                                                                     STATUS                       PORTS
backend    sha256:9e27bcf060056ecf782038231709cfc6b6c36e4ac6503c8f5f477e7616805b7a   Up 42 minutes (healthy)      0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
frontend   idea-board-frontend:dev                                                   Up 39 minutes (healthy)      0.0.0.0:3000->8080/tcp, [::]:3000->8080/tcp
postgres   postgres:16.6-alpine3.21                                                  Up About an hour (healthy)   127.0.0.1:5432->5432/tcp

$ BASE_URL=http://localhost:3000 APP_HOST=localhost bash scripts/smoke-test.sh compose
[21:01:17] smoke testing http://localhost (via http://localhost:3000)
[ ok ] GET /healthz returns 200 with {"status":"ok"} (got 200)
[ ok ] POST /api/ideas returns 201 (got 201)
[ ok ] POST response echoes the content
[ ok ] GET /api/ideas contains the new idea
[ ok ] GET /api/ideas returns a JSON array
[ ok ] POST blank content is rejected with 422 (got 422)
[ ok ] GET / serves the React app
[ ok ] all smoke checks passed for compose

$ docker compose exec backend id
uid=10001(app) gid=10001(app) groups=10001(app)

$ curl -sI http://localhost:3000/ (security headers)
HTTP/1.1 200 OK
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: default-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'
```

## 7. Pipeline run #20261114.10: `deploy-staging` and `verify-staging`

The run then stopped at the production approval gate, **awaiting a human decision** (README I-26).

```text
==> STAGE: deploy-staging
==> JOB: deploy-staging
[2026-11-14T15:29:55Z] job deploy-staging started (stage deploy-staging)
==> AI: environment configuration for staging
[AI FALLBACK] deterministic logic used - LLM unavailable: Ollama not reachable at http://localhost:11434: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
profile: cost-sensitive -> C:\Users\<user>\Desktop\assesment\artifacts\generated\values-staging.ai.yaml
audit: C:\Users\<user>\Desktop\assesment\artifacts\ai\20261114T153001088980Z-env-config-staging.json
==> Render manifests (chart schema + server-side validation)
[ ok ] rendered 7 objects -> artifacts/manifests-staging.yaml
==> helm upgrade --install idea-board (staging, image 16dc12755450-dirty)
Release "idea-board" has been upgraded. Happy Helming!
STATUS: deployed
REVISION: 11
==> AI: post-deploy health gate
waiting 20s for the release to settle...
[AI FALLBACK] deterministic logic used - LLM unavailable: Ollama not reachable at http://localhost:11434: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
verdict: HEALTHY - healthy by rules (with warnings)
  [warning] 15 Kubernetes warning event(s)
summary: Release 'idea-board' in 'staging' is healthy with 1 warning(s): 15 Kubernetes warning event(s)
[ ok ] staging healthy: http://staging.ideaboard.localhost (context kind-idea-board)
[ ok ] stage 'deploy-staging' succeeded in 55s
==> STAGE: verify-staging
==> JOB: verify-staging
[2026-11-14T15:30:49Z] job verify-staging started (stage verify-staging)
==> Smoke tests: staging
[21:00:52] smoke testing http://staging.ideaboard.localhost (via http://127.0.0.1:18081)
[ ok ] GET /healthz returns 200 with {"status":"ok"} (got 200)
[ ok ] POST /api/ideas returns 201 (got 201)
[ ok ] POST response echoes the content
[ ok ] GET /api/ideas contains the new idea
[ ok ] GET /api/ideas returns a JSON array
[ ok ] POST blank content is rejected with 422 (got 422)
[ ok ] GET / serves the React app
[ ok ] all smoke checks passed for staging
[ ok ] staging verified: http://staging.ideaboard.localhost via http://127.0.0.1:18081
[ ok ] stage 'verify-staging' succeeded in 5s
==> STAGE: promote-production
[warn] waiting up to 1800s for approval of 'promote-production':
```

## 8. `promote-production` (run on 2026-11-13, same pipeline code path)

High-availability profile: 2 + 2 replicas, HPA, PDB, topology spread.

```text
==> STAGE: deploy-production
==> AI: environment configuration for production
[AI FALLBACK] deterministic logic used - LLM unavailable: Ollama not reachable at http://localhost:11434: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
profile: high-availability -> C:\Users\<user>\Desktop\assesment\artifacts\generated\values-production.ai.yaml
audit: C:\Users\<user>\Desktop\assesment\artifacts\ai\20261113T180348098126Z-env-config-production.json
==> Render manifests (chart schema + server-side validation)
[ ok ] rendered 11 objects -> artifacts/manifests-production.yaml
==> helm upgrade --install idea-board (production, image a43c82a051bf)
Release "idea-board" does not exist. Installing it now.
STATUS: deployed
REVISION: 1
==> AI: post-deploy health gate
waiting 5s for the release to settle...
[AI FALLBACK] deterministic logic used - LLM unavailable: Ollama not reachable at http://localhost:11434: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
verdict: HEALTHY - healthy by rules (with warnings)
  [warning] 2 Kubernetes warning event(s)
summary: Release 'idea-board' in 'production' is healthy with 1 warning(s): 2 Kubernetes warning event(s)
[ ok ] production healthy: http://ideaboard.localhost:8080/
[ ok ] stage 'deploy-production' finished in 27s
==> STAGE: verify-production
==> Smoke tests: production
[23:34:10] smoke testing http://ideaboard.localhost (via http://127.0.0.1:18082)
[ ok ] GET /healthz returns 200 with {"status":"ok"} (got 200)
[ ok ] POST /api/ideas returns 201 (got 201)
[ ok ] POST response echoes the content
[ ok ] GET /api/ideas contains the new idea
[ ok ] GET /api/ideas returns a JSON array
[ ok ] POST blank content is rejected with 422 (got 422)
[ ok ] GET / serves the React app
[ ok ] all smoke checks passed for production
[ ok ] production verified: http://ideaboard.localhost:8080/
[ ok ] stage 'verify-production' finished in 2s
[ ok ] pipeline complete - artifacts in artifacts/
exit=0
```

## 9. Cluster state after the runs

The Helm history also records the rollbacks exercised during testing: revisions 3→4 and 5→6 are the
`demo-rollback` tests; 7→8 and 9→10 are the port-forward false alarms described in README I-27.

```text
$ kubectl get nodes
NAME                       STATUS   ROLES           AGE   VERSION
idea-board-control-plane   Ready    control-plane   22h   v1.32.0

$ kubectl -n staging get deploy,sts,hpa,pdb,netpol,pods
NAME                                  READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/idea-board-backend    1/1     1            1           21h
deployment.apps/idea-board-frontend   1/1     1            1           21h

NAME                        READY   AGE
statefulset.apps/postgres   1/1     21h

NAME                                                     POD-SELECTOR                                                                                                   AGE
networkpolicy.networking.k8s.io/idea-board-backend       app.kubernetes.io/component=backend,app.kubernetes.io/instance=idea-board,app.kubernetes.io/name=idea-board    21h
networkpolicy.networking.k8s.io/idea-board-frontend      app.kubernetes.io/component=frontend,app.kubernetes.io/instance=idea-board,app.kubernetes.io/name=idea-board   21h
networkpolicy.networking.k8s.io/postgres-allow-clients   app.kubernetes.io/instance=postgres,app.kubernetes.io/name=postgres                                            22h

NAME                                       READY   STATUS    RESTARTS   AGE
pod/idea-board-backend-85bf5bc884-8rgfz    1/1     Running   0          80s
pod/idea-board-frontend-5cccdf5874-mf4hm   1/1     Running   0          80s
pod/postgres-0                             1/1     Running   0          21h

$ kubectl -n production get deploy,sts,hpa,pdb,netpol,pods
NAME                                  READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/idea-board-backend    2/2     2            2           21h
deployment.apps/idea-board-frontend   2/2     2            2           21h

NAME                        READY   AGE
statefulset.apps/postgres   1/1     21h

NAME                                                      REFERENCE                        TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
horizontalpodautoscaler.autoscaling/idea-board-backend    Deployment/idea-board-backend    cpu: 5%/70%   2         4         2          21h
horizontalpodautoscaler.autoscaling/idea-board-frontend   Deployment/idea-board-frontend   cpu: 4%/70%   2         3         2          21h

NAME                                             MIN AVAILABLE   MAX UNAVAILABLE   ALLOWED DISRUPTIONS   AGE
poddisruptionbudget.policy/idea-board-backend    1               N/A               1                     21h
poddisruptionbudget.policy/idea-board-frontend   1               N/A               1                     21h

NAME                                                     POD-SELECTOR                                                                                                   AGE
networkpolicy.networking.k8s.io/idea-board-backend       app.kubernetes.io/component=backend,app.kubernetes.io/instance=idea-board,app.kubernetes.io/name=idea-board    21h
networkpolicy.networking.k8s.io/idea-board-frontend      app.kubernetes.io/component=frontend,app.kubernetes.io/instance=idea-board,app.kubernetes.io/name=idea-board   21h
networkpolicy.networking.k8s.io/postgres-allow-clients   app.kubernetes.io/instance=postgres,app.kubernetes.io/name=postgres                                            22h

NAME                                       READY   STATUS    RESTARTS   AGE
pod/idea-board-backend-79d8886d8c-kflgv    1/1     Running   0          21h
pod/idea-board-backend-79d8886d8c-ms5bl    1/1     Running   0          21h
pod/idea-board-frontend-64bbd66fbd-9phvm   1/1     Running   0          21h
pod/idea-board-frontend-64bbd66fbd-gzs5m   1/1     Running   0          21h
pod/postgres-0                             1/1     Running   0          21h

$ kubectl get ns staging production --show-labels
NAME         STATUS   AGE   LABELS
staging      Active   22h   app.kubernetes.io/part-of=idea-board,idea-board/environment=staging,kubernetes.io/metadata.name=staging,pod-security.kubernetes.io/enforce=restricted,pod-security.kubernetes.io/warn=restricted
production   Active   22h   app.kubernetes.io/part-of=idea-board,idea-board/environment=production,kubernetes.io/metadata.name=production,pod-security.kubernetes.io/enforce=restricted,pod-security.kubernetes.io/warn=rest …

$ kubectl -n staging describe quota default
Resource                Used   Hard
--------                ----   ----
limits.cpu              850m   3
limits.memory           768Mi  3Gi
persistentvolumeclaims  1      5
pods                    3      15
requests.cpu            110m   1
requests.memory         256Mi  1Gi
services.loadbalancers  0      0

$ helm -n staging history idea-board
REVISION	UPDATED                 	STATUS    	CHART           	APP VERSION	DESCRIPTION                                           
2       	Fri Nov 13 23:32:51 2026	superseded	idea-board-1.0.0	1.0.0      	Upgrade complete                                      
3       	Fri Nov 13 23:34:33 2026	failed    	idea-board-1.0.0	1.0.0      	Upgrade "idea-board" failed: context deadline exceeded
4       	Fri Nov 13 23:36:16 2026	superseded	idea-board-1.0.0	1.0.0      	Rollback to 2                                         
5       	Sat Nov 14 20:39:56 2026	failed    	idea-board-1.0.0	1.0.0      	Upgrade "idea-board" failed: context deadline exceeded
6       	Sat Nov 14 20:41:40 2026	superseded	idea-board-1.0.0	1.0.0      	Rollback to 4                                         
7       	Sat Nov 14 20:50:41 2026	superseded	idea-board-1.0.0	1.0.0      	Upgrade complete                                      
8       	Sat Nov 14 20:51:23 2026	superseded	idea-board-1.0.0	1.0.0      	Rollback to 6                                         
9       	Sat Nov 14 20:55:38 2026	superseded	idea-board-1.0.0	1.0.0      	Upgrade complete                                      
10      	Sat Nov 14 20:56:33 2026	superseded	idea-board-1.0.0	1.0.0      	Rollback to 8                                         
11      	Sat Nov 14 21:00:02 2026	deployed  	idea-board-1.0.0	1.0.0      	Upgrade complete                                      

$ terraform output app_urls (stack local)
{
  "production" = "http://ideaboard.localhost:8080/"
  "staging" = "http://staging.ideaboard.localhost:8080/"
}
```

## 10. Resilience test: automatic rollback (`scripts/pipeline.sh demo-rollback`)

Expected behaviour: a deliberately broken backend image is detected and rolled back automatically, an incident
report is written, and the stage ends as `rolledBack` (exit code 2). **Result: as expected.**

```text
PS C:\Users\<user>\Desktop\assesment> & "C:\Program Files\Git\bin\bash.exe" scripts/pipeline.sh demo-rollback
[20:39:47] run 20261114-150946-82b4 started - view it at http://localhost:3000/pipelines
==> STAGE: demo-rollback
[warn] deploying a deliberately broken backend image to staging
==> JOB: demo-rollback
[2026-11-14T15:09:48Z] job demo-rollback started (stage demo-rollback)
==> AI: environment configuration for staging
[AI FALLBACK] deterministic logic used - LLM unavailable: Ollama not reachable at http://localhost:11434
profile: cost-sensitive -> C:\Users\<user>\Desktop\assesment\artifacts\generated\values-staging.ai.yaml
==> Render manifests (chart schema + server-side validation)
[ ok ] rendered 7 objects -> artifacts/manifests-staging.yaml
==> helm upgrade --install idea-board (staging, image a43c82a051bf)
Error: UPGRADE FAILED: context deadline exceeded
[warn] helm did not converge - handing over to the health gate
==> AI: post-deploy health gate
waiting 5s for the release to settle...
[AI FALLBACK] deterministic logic used - LLM unavailable: Ollama not reachable at http://localhost:11434
verdict: UNHEALTHY - rules: 3 critical finding(s) (authoritative)
  [critical] helm upgrade --wait did not converge (timeout or failed resources)
  [critical] pod idea-board-backend-668c4cc9b7-wkbjf is waiting: ImagePullBackOff
  [critical] synthetic probe error rate 100% ({'conn_error': 10})
  [warning] 7 error log line(s) since rollout
  [warning] 4 Kubernetes warning event(s)
summary: Release 'idea-board' in 'staging' is UNHEALTHY: 3 critical finding(s). - helm upgrade --wait did not converge (timeout or failed resources). - pod idea-board-backend-668c4cc9b7-wkbjf is waiting: ImagePullBackOff …
$ helm --kube-context kind-idea-board rollback idea-board 4 -n staging --wait --timeout 5m
Rollback was a success! Happy Helming!
rolled back to revision 4 successfully
incident summary written to C:\Users\<user>\Desktop\assesment\artifacts\incidents\20261114T151142Z-staging-idea-board.md
[warn] staging was UNHEALTHY and has been rolled back automatically - see artifacts/incidents/
[warn] run 20261114-150946-82b4 finished: rolledBack - artifacts/runs/20261114-150946-82b4
```

## 11. Preview environment lifecycle (AI command generation, deterministic fallback)

```text
$ bash scripts/pipeline.sh preview "deploy-preview/feature-x"
Ollama not usable (Ollama not reachable at http://localhost:11434: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>). AI features will use deterministic fallback …
[21:01:49] run 20261114-153149-b3f6 started - view it at http://localhost:3000/pipelines
==> STAGE: preview
==> JOB: preview
[2026-11-14T15:31:50Z] job preview started (stage preview)
==> AI: preview plan for 'deploy-preview/feature-x'
[AI FALLBACK] deterministic logic used - LLM unavailable: Ollama not reachable at http://localhost:11434: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
preview: action=deploy namespace=preview-feature-x release=idea-board-feature-x host=feature-x.preview.ideaboard.localhost
  1. Install or upgrade the self-contained preview release
     helm upgrade --install idea-board-feature-x deploy/helm/idea-board -n preview-feature-x --create-namespace -f deploy/helm/idea-board/values-preview.yaml --set ingress.host=feature-x.preview.ideaboard.localhost --set …
  2. Wait for the backend rollout
     kubectl rollout status deployment/idea-board-feature-x-backend -n preview-feature-x --timeout=120s
  3. Show what was deployed
     kubectl get pods,ingress -n preview-feature-x -o wide
audit: C:\Users\<user>\Desktop\assesment\artifacts\ai\20261114T153156024537Z-preview-plan-deploy.json
$ helm --kube-context kind-idea-board upgrade --install idea-board-feature-x deploy/helm/idea-board -n preview-feature-x --create-namespace -f deploy/helm/idea-board/values-preview.yaml --set ingress.host=feature-x.previ …
Release "idea-board-feature-x" does not exist. Installing it now.
NAME: idea-board-feature-x
STATUS: deployed
REVISION: 1
The Idea Board (preview) is deployed as release "idea-board-feature-x" in namespace "preview-feature-x".
$ kubectl --context kind-idea-board rollout status deployment/idea-board-feature-x-backend -n preview-feature-x --timeout=120s
deployment "idea-board-feature-x-backend" successfully rolled out
$ kubectl --context kind-idea-board get pods,ingress -n preview-feature-x -o wide
NAME                                                 READY   STATUS    RESTARTS   AGE   IP            NODE                       NOMINATED NODE   READINESS GATES
pod/idea-board-feature-x-backend-647fb6fb9f-pb28r    1/1     Running   0          39s   10.244.0.39   idea-board-control-plane   <none>           <none>
pod/idea-board-feature-x-frontend-9cb954947-5pzhn    1/1     Running   0          39s   10.244.0.37   idea-board-control-plane   <none>           <none>
pod/idea-board-feature-x-postgres-5cf95fd7cc-xvwvr   1/1     Running   0          39s   10.244.0.38   idea-board-control-plane   <none>           <none>
NAME                                             CLASS   HOSTS                                   ADDRESS   PORTS   AGE
ingress.networking.k8s.io/idea-board-feature-x   nginx   feature-x.preview.ideaboard.localhost             80      39s
preview ready: http://feature-x.preview.ideaboard.localhost:8080/
[ ok ] stage 'preview' succeeded in 48s
[ ok ] run 20261114-153149-b3f6 succeeded - artifacts/runs/20261114-153149-b3f6

$ BASE_URL=http://127.0.0.1:18083 APP_HOST=feature-x.preview.ideaboard.localhost bash scripts/smoke-test.sh preview-feature-x
[21:12:10] smoke testing http://feature-x.preview.ideaboard.localhost (via http://127.0.0.1:18083)
[ ok ] GET /healthz returns 200 with {"status":"ok"} (got 200)
[ ok ] POST /api/ideas returns 201 (got 201)
[ ok ] POST response echoes the content
[ ok ] GET /api/ideas contains the new idea
[ ok ] GET /api/ideas returns a JSON array
[ ok ] POST blank content is rejected with 422 (got 422)
[ ok ] GET / serves the React app
[ ok ] all smoke checks passed for preview-feature-x

$ bash scripts/pipeline.sh preview "/destroy-preview feature-x"
[21:12:18] run 20261114-154218-ae59 started - view it at http://localhost:3000/pipelines
==> STAGE: preview
==> JOB: preview
[2026-11-14T15:42:19Z] job preview started (stage preview)
==> AI: preview plan for '/destroy-preview feature-x'
[AI FALLBACK] deterministic logic used - LLM unavailable: Ollama not reachable at http://localhost:11434: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
preview: action=destroy namespace=preview-feature-x release=idea-board-feature-x host=feature-x.preview.ideaboard.localhost
  1. Remove the preview release
     helm uninstall idea-board-feature-x -n preview-feature-x --wait
  2. Delete the preview namespace
     kubectl delete namespace preview-feature-x
audit: C:\Users\<user>\Desktop\assesment\artifacts\ai\20261114T154225395243Z-preview-plan-destroy.json
$ helm --kube-context kind-idea-board uninstall idea-board-feature-x -n preview-feature-x --wait
release "idea-board-feature-x" uninstalled
$ kubectl --context kind-idea-board delete namespace preview-feature-x
namespace "preview-feature-x" deleted
[ ok ] stage 'preview' succeeded in 14s
[ ok ] run 20261114-154218-ae59 succeeded - artifacts/runs/20261114-154218-ae59
$ kubectl get ns preview-feature-x
Error from server (NotFound): namespaces "preview-feature-x" not found
```

## 12. Pipelines API: security and contract checks

```text
$ for each traversal / bad id: curl http://localhost:8000/api/pipelines/<path>
..%2F..%2Fetc                                           -> {"detail":"Not Found"} [HTTP 404]
..%2Fruns                                               -> {"detail":"Not Found"} [HTTP 404]
not-a-run-id                                            -> {"detail":"invalid run id"} [HTTP 400]
20261114-152800-f9d5/logs/..%2F..%2F..%2Fapp%2Fmain     -> {"detail":"Not Found"} [HTTP 404]
20261114-152800-f9d5/logs/run.json                      -> {"detail":"invalid job name"} [HTTP 400]
20261114-152800-f9d5/logs/BUILD                         -> {"detail":"invalid job name"} [HTTP 400]

$ curl -X POST .../api/pipelines/<finished run>/approve -d {"decision":"approve"}
{"detail":"this run is not waiting for approval"} [HTTP 409]
$ curl -X POST .../approve -d {"decision":"maybe"}
[HTTP 422]
```
