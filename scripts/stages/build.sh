#!/usr/bin/env bash
# Stage: build immutable, SHA-tagged images and make them available to the cluster.
source "$(dirname "$0")/../lib.sh"
require docker
cd "$REPO_ROOT"

tag="$(image_tag)"
echo "$tag" > "$ARTIFACTS_DIR/image-tag"

# Cloud: BUILD_PLATFORM=linux/amd64 builds for the node architecture (developer machines may be ARM64)
# and pushes straight to $REGISTRY with buildx.
if [[ -n "${BUILD_PLATFORM:-}" ]]; then
  [[ -n "${REGISTRY:-}" ]] || die "BUILD_PLATFORM requires REGISTRY (cross-platform images are pushed, not loaded)"
  section "Build and push $BUILD_PLATFORM images to $REGISTRY (tag $tag)"
  for img in backend frontend; do
    docker buildx build --platform "$BUILD_PLATFORM" -t "$REGISTRY/idea-board-$img:$tag" --push "$img"
  done
  ok "pushed $REGISTRY/idea-board-{backend,frontend}:$tag"
  exit 0
fi

section "Build images (tag $tag)"
docker build --pull=false -t "idea-board-backend:$tag" backend
docker build --pull=false -t "idea-board-frontend:$tag" frontend

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
