#!/usr/bin/env bash
# Create (idempotently) the local kind cluster that hosts staging + production.
source "$(dirname "$0")/lib.sh"
require kind kubectl docker

INGRESS_HTTPS_PORT="${INGRESS_HTTPS_PORT:-8443}"

if kind get clusters 2>/dev/null | grep -qx "$KIND_CLUSTER_NAME"; then
  ok "kind cluster '$KIND_CLUSTER_NAME' already exists"
else
  config="$ARTIFACTS_DIR/kind-cluster.yaml"
  sed -e "s/\${INGRESS_HTTP_PORT}/$INGRESS_HTTP_PORT/" -e "s/\${INGRESS_HTTPS_PORT}/$INGRESS_HTTPS_PORT/" \
    "$REPO_ROOT/deploy/kind/cluster.yaml" > "$config"
  image_args=()
  [[ -n "${KIND_NODE_IMAGE:-}" ]] && image_args=(--image "$KIND_NODE_IMAGE")
  log "creating kind cluster '$KIND_CLUSTER_NAME' (ingress on 127.0.0.1:$INGRESS_HTTP_PORT)"
  kind create cluster --name "$KIND_CLUSTER_NAME" --config "$config" "${image_args[@]}" --wait 120s
fi

kubectl config use-context "$KUBE_CONTEXT" >/dev/null
kubectl_ctx wait --for=condition=Ready nodes --all --timeout=180s
ok "cluster ready: context $KUBE_CONTEXT"
