#!/usr/bin/env bash
# Terraform wrapper: picks the provider root from the stack's `cloud` variable.
#
#   scripts/tf.sh <stack> <init|validate|plan|apply|destroy|output> [extra terraform args]
#
#   stack = a folder in infra/terraform/environments (local, staging, production)
#   The stack's terraform.tfvars contains `cloud = "local" | "aws" | "gcp"`; that single
#   value selects infra/terraform/providers/<cloud> and environments/<stack>/<cloud>.tfvars.
source "$(dirname "$0")/lib.sh"

[[ $# -ge 2 ]] || die "usage: $0 <stack> <init|validate|plan|apply|destroy|output> [args]"
stack="$1"; cmd="$2"; shift 2

TF_ROOT="infra/terraform"
env_dir="$REPO_ROOT/$TF_ROOT/environments/$stack"
[[ -f "$env_dir/terraform.tfvars" ]] || die "unknown stack '$stack' (no $env_dir/terraform.tfvars)"

cloud="$(sed -nE 's/^cloud[[:space:]]*=[[:space:]]*"([a-z0-9]+)".*/\1/p' "$env_dir/terraform.tfvars" | head -1)"
[[ -n "$cloud" ]] || die "$env_dir/terraform.tfvars must set cloud = \"...\""
[[ -d "$REPO_ROOT/$TF_ROOT/providers/$cloud" ]] || die "no provider root for cloud '$cloud'"
[[ -f "$env_dir/$cloud.tfvars" ]] || die "missing $env_dir/$cloud.tfvars"

export TF_WORKDIR="$TF_ROOT/providers/$cloud"
export TF_DATA_DIR=".terraform-$stack"   # per-stack plugin/module cache inside the root
export TF_IN_AUTOMATION=1
cd "$REPO_ROOT/$TF_WORKDIR"

var_files=(-var-file="../../environments/$stack/terraform.tfvars" -var-file="../../environments/$stack/$cloud.tfvars")

init() {
  local backend_args=()
  if [[ "$cloud" == "local" ]]; then
    mkdir -p "$REPO_ROOT/.state"
    backend_args=(-backend-config="path=../../../../.state/$stack.tfstate")
  elif [[ "${1:-}" == "--no-backend" ]]; then
    backend_args=(-backend=false)
  elif [[ -f "$env_dir/backend.hcl" ]]; then
    backend_args=(-backend-config="../../environments/$stack/backend.hcl")
  else
    die "remote backend for '$stack' not configured: create $env_dir/backend.hcl (see README)"
  fi
  terraform_cmd init -input=false -reconfigure "${backend_args[@]}" >/dev/null
}

log "stack=$stack cloud=$cloud root=$TF_WORKDIR cmd=$cmd"
case "$cmd" in
  init)     init "$@" ;;
  validate) init --no-backend; terraform_cmd validate ;;
  plan)     init; terraform_cmd plan -input=false "${var_files[@]}" "$@" ;;
  apply)
    init
    approve=()
    [[ -n "${CI:-}${TF_BUILD:-}" || "${AUTO_APPROVE:-}" == "1" ]] && approve=(-auto-approve)
    terraform_cmd apply -input=false "${var_files[@]}" "${approve[@]}" "$@"
    ;;
  destroy)  init; terraform_cmd destroy -input=false "${var_files[@]}" "$@" ;;
  output)   init; terraform_cmd output "$@" ;;
  *) die "unknown command '$cmd'" ;;
esac
