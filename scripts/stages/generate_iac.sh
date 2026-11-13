#!/usr/bin/env bash
# Stage: Generative IaC. A service spec becomes Helm values + a Terraform landing-zone stub,
# accepted into services/<name>/ ONLY if `helm lint` and `terraform validate` both pass.
#   scripts/stages/generate_iac.sh ai/examples/notifications.service.yaml
source "$(dirname "$0")/../lib.sh"
cd "$REPO_ROOT"

spec="${1:?usage: generate_iac.sh <service-spec.yaml>}"
section "AI: generate IaC from $spec"
result="$(aiops geniac --spec "$spec" --out services | tee /dev/stderr | tail -n1)"
candidate="$("$(python_bin)" -c 'import json,sys; print(json.loads(sys.argv[1])["candidate_dir"])' "$result")"
candidate="${candidate//\\//}"
candidate_rel="services/$(basename "$candidate")"
name="$(basename "$candidate" .candidate)"

reject() {
  mkdir -p "$ARTIFACTS_DIR/rejected"
  rm -rf "$ARTIFACTS_DIR/rejected/$name"
  mv "$candidate_rel" "$ARTIFACTS_DIR/rejected/$name"
  die "generated IaC for '$name' rejected: $1 (kept in artifacts/rejected/$name)"
}

section "Gate 1: helm lint"
helm_cmd lint deploy/helm/service -f "$candidate_rel/helm/values.yaml" --strict || reject "helm lint failed"
helm_cmd template "$name" deploy/helm/service -f "$candidate_rel/helm/values.yaml" > /dev/null || reject "helm template failed"

section "Gate 2: terraform fmt + validate"
export TF_WORKDIR="$candidate_rel/terraform" TF_DATA_DIR=".terraform"
(cd "$candidate_rel/terraform" && terraform_cmd fmt -check && terraform_cmd init -backend=false -input=false >/dev/null && terraform_cmd validate) \
  || reject "terraform validate failed"
rm -rf "$candidate_rel/terraform/.terraform" "$candidate_rel/terraform/.terraform.lock.hcl"

rm -rf "services/$name"
mv "$candidate_rel" "services/$name"
ok "accepted: services/$name (review and commit it like any other change)"
