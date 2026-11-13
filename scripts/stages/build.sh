#!/usr/bin/env bash
# Stage: build immutable, SHA-tagged images and make them available to the cluster.
source "$(dirname "$0")/../lib.sh"
require docker
cd "$REPO_ROOT"

tag="$(image_tag)"
section "Build images (tag $tag)"
docker build --pull=false -t "idea-board-backend:$tag" backend
docker build --pull=false -t "idea-board-frontend:$tag" frontend
echo "$tag" > "$ARTIFACTS_DIR/image-tag"

if [[ -n "${REGISTRY:-}" ]]; then
  section "Push to $REGISTRY"
  for img in idea-board-backend idea-board-frontend; do
    docker tag "$img:$tag" "$REGISTRY/$img:$tag"
    docker push "$REGISTRY/$img:$tag"
  done
fi

if has kind && kind get clusters 2>/dev/null | grep -qx "$KIND_CLUSTER_NAME"; then
  section "Load images into kind cluster '$KIND_CLUSTER_NAME'"
  kind load docker-image "idea-board-backend:$tag" "idea-board-frontend:$tag" --name "$KIND_CLUSTER_NAME"
else
  warn "kind cluster '$KIND_CLUSTER_NAME' not found - images built but not loaded (run scripts/pipeline.sh platform)"
fi
ok "images idea-board-{backend,frontend}:$tag"
