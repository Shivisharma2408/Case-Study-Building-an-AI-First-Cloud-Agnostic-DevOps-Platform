#!/usr/bin/env bash
# Stage: lint + unit tests + static validation of every deliverable. No cluster needed.
source "$(dirname "$0")/../lib.sh"
cd "$REPO_ROOT"
PY="$(python_bin)"

if [[ "${INSTALL_DEPS:-0}" == "1" ]]; then
  section "Install dependencies"
  "$PY" -m pip install -q -r backend/requirements-dev.txt -r ai/requirements-dev.txt
  (cd frontend && npm ci --no-audit --no-fund)
fi

section "Python: ruff (backend + ai)"
"$PY" -m ruff check backend ai
"$PY" -m ruff format --check backend ai
"$PY" -m ruff check --config ai/pyproject.toml scripts/runstate.py
"$PY" -m ruff format --check --config ai/pyproject.toml scripts/runstate.py

section "Backend: pytest"
(cd backend && "$PY" -m pytest)

section "AI tooling: pytest (validators, fallbacks, health gate)"
(cd ai && "$PY" -m pytest)

section "Frontend: eslint + vitest + typecheck + build"
(cd frontend && { [[ -d node_modules ]] || npm ci --no-audit --no-fund; } && npm run lint && npm test && npm run build)

section "docker compose config"
if has docker; then
  docker compose --env-file .env.example config -q && ok "docker-compose.yml is valid"
else
  warn "docker not available - skipped compose validation"
fi

section "Helm: lint (all environment value sets) + render"
for values in "" values-staging.yaml values-production.yaml values-preview.yaml; do
  args=(lint "$HELM_CHART" --strict)
  [[ -n "$values" ]] && args+=(-f "$HELM_CHART/$values")
  helm_cmd "${args[@]}"
done
helm_cmd lint deploy/helm/service --strict

section "Terraform: fmt + validate (local, aws, gcp roots)"
TF_WORKDIR="infra/terraform" terraform_cmd fmt -check -recursive
for root in aws gcp; do
  cmp -s infra/terraform/providers/local/variables-common.tf "infra/terraform/providers/$root/variables-common.tf" \
    || die "providers/$root/variables-common.tf drifted from providers/local (they must be identical)"
done
ok "variables-common.tf identical across provider roots"
"$REPO_ROOT/scripts/tf.sh" local validate
if [[ "${TF_VALIDATE_CLOUDS:-1}" == "1" ]]; then
  "$REPO_ROOT/scripts/tf.sh" staging validate      # aws
  "$REPO_ROOT/scripts/tf.sh" production validate   # aws
fi

if has shellcheck; then
  section "shellcheck"
  shellcheck -x scripts/*.sh scripts/stages/*.sh
fi

ok "lint-test stage passed"
