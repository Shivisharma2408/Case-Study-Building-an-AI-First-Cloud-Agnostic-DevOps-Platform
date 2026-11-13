#!/usr/bin/env bash
# Stage: provision the local platform - kind cluster + `terraform apply` of the local stack
# (ingress-nginx, metrics-server, namespaces with quotas, PostgreSQL, DB secrets).
source "$(dirname "$0")/../lib.sh"
require kind kubectl terraform helm

section "kind cluster"
"$REPO_ROOT/scripts/kind-up.sh"

section "terraform apply (stack: local)"
AUTO_APPROVE="${AUTO_APPROVE:-1}" "$REPO_ROOT/scripts/tf.sh" local apply
"$REPO_ROOT/scripts/tf.sh" local output app_urls
