#!/usr/bin/env bash
# Shared helpers for every pipeline script. Sourced, never executed.
# Works on Linux/macOS, Git Bash on Windows, and Azure Pipelines agents.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
_REPO_ROOT_POSIX="$REPO_ROOT"   # PATH entries must stay POSIX (a "C:" would split on the colon)
# Windows (Git Bash / Cygwin): use C:/... form, understood by bash AND native tools
# (python.exe, kind.exe, docker) in arguments and environment variables alike.
if command -v cygpath >/dev/null 2>&1; then
  REPO_ROOT="$(cygpath -m "$REPO_ROOT")"
fi
export REPO_ROOT
ARTIFACTS_DIR="${ARTIFACTS_DIR:-$REPO_ROOT/artifacts}"
export ARTIFACTS_DIR
mkdir -p "$ARTIFACTS_DIR"

# Optional repo-local tool directory (scripts/install-tools.sh puts kind/helm/terraform here).
if [[ -d "$_REPO_ROOT_POSIX/.tools/bin" ]]; then
  PATH="$_REPO_ROOT_POSIX/.tools/bin:$PATH"
fi

# Load .env (git-ignored) if present, without overriding variables already set.
if [[ -f "$REPO_ROOT/.env" ]]; then
  while IFS='=' read -r key value; do
    [[ -z "$key" || "$key" == \#* ]] && continue
    if [[ -z "${!key+x}" ]]; then export "$key=$value"; fi
  done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$REPO_ROOT/.env" | tr -d '\r')
fi

KIND_CLUSTER_NAME="${KIND_CLUSTER_NAME:-idea-board}"
KUBE_CONTEXT="${KUBE_CONTEXT:-kind-$KIND_CLUSTER_NAME}"
INGRESS_HTTP_PORT="${INGRESS_HTTP_PORT:-8080}"
HELM_CHART="deploy/helm/idea-board"
RELEASE_NAME="${RELEASE_NAME:-idea-board}"
export KIND_CLUSTER_NAME KUBE_CONTEXT INGRESS_HTTP_PORT HELM_CHART RELEASE_NAME

TERRAFORM_IMAGE="hashicorp/terraform:1.9.8"
HELM_IMAGE="alpine/helm:3.16.4"

if [[ -t 1 ]]; then
  _c_info=$'\e[36m' _c_ok=$'\e[32m' _c_warn=$'\e[33m' _c_err=$'\e[31m' _c_off=$'\e[0m'
else
  _c_info="" _c_ok="" _c_warn="" _c_err="" _c_off=""
fi

log()  { printf '%s[%s]%s %s\n' "$_c_info" "$(date +%H:%M:%S)" "$_c_off" "$*"; }
ok()   { printf '%s[ ok ]%s %s\n' "$_c_ok" "$_c_off" "$*"; }
warn() { printf '%s[warn]%s %s\n' "$_c_warn" "$_c_off" "$*" >&2; }
die()  { printf '%s[fail]%s %s\n' "$_c_err" "$_c_off" "$*" >&2; exit 1; }

# Azure Pipelines renders these as collapsible sections; locally they are plain headings.
section() {
  if [[ -n "${TF_BUILD:-}" ]]; then echo "##[section]$*"; else printf '\n%s==> %s%s\n' "$_c_info" "$*" "$_c_off"; fi
}

has() { command -v "$1" >/dev/null 2>&1; }
require() { for c in "$@"; do has "$c" || die "'$c' is required but not installed (see README prerequisites, or scripts/install-tools.sh)"; done; }

# Python interpreter: repo venv if present, else system python.
python_bin() {
  if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then echo "$REPO_ROOT/.venv/bin/python"
  elif [[ -x "$REPO_ROOT/.venv/Scripts/python.exe" ]]; then echo "$REPO_ROOT/.venv/Scripts/python.exe"
  elif has python3; then echo python3
  else echo python; fi
}

# The AI tooling CLI (ai/aiops). All AI decisions are audited under $ARTIFACTS_DIR/ai.
aiops() {
  # Single PYTHONPATH entry: the list separator differs between Windows (;) and POSIX (:).
  # MSYS_NO_PATHCONV: stop Git Bash rewriting "/deploy-preview ..." into a Windows path.
  MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*" PYTHONPATH="$REPO_ROOT/ai" "$(python_bin)" -m aiops "$@"
}

# terraform / helm: native binary if installed, else the official container image.
# The container fallback is only suitable for cluster-less commands (fmt, validate, lint, template).
terraform_cmd() {
  if has terraform; then terraform "$@"
  else
    has docker || die "terraform not installed and docker unavailable"
    MSYS_NO_PATHCONV=1 docker run --rm -e TF_DATA_DIR -e TF_IN_AUTOMATION=1 \
      -v "$REPO_ROOT:/w" -w "/w/${TF_WORKDIR:-}" "$TERRAFORM_IMAGE" "$@"
  fi
}

helm_cmd() {
  if has helm; then helm "$@"
  else
    has docker || die "helm not installed and docker unavailable"
    MSYS_NO_PATHCONV=1 docker run --rm -v "$REPO_ROOT:/w" -w /w "$HELM_IMAGE" "$@"
  fi
}

git_sha() { git -C "$REPO_ROOT" rev-parse --short=12 HEAD 2>/dev/null || echo "nogit"; }

# Immutable image tag: commit SHA (+ "-dirty" for uncommitted local builds).
image_tag() {
  if [[ -n "${IMAGE_TAG:-}" ]]; then echo "$IMAGE_TAG"; return; fi
  local sha; sha="$(git_sha)"
  if [[ -n "$(git -C "$REPO_ROOT" status --porcelain 2>/dev/null)" ]]; then echo "${sha}-dirty"; else echo "$sha"; fi
}

kubectl_ctx() { kubectl --context "$KUBE_CONTEXT" "$@"; }
helm_ctx() { helm --kube-context "$KUBE_CONTEXT" "$@"; }

app_host() {
  case "$1" in
    production) echo "ideaboard.localhost" ;;
    *) echo "$1.ideaboard.localhost" ;;
  esac
}
