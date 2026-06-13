#!/usr/bin/env bash
set -euo pipefail

# Build (and optionally push) all deployable service images for this repository.
# Usage:
#   bash scripts/build_all_service_images.sh
#   IMAGE_TAG=$(git rev-parse --short HEAD) PUSH=true bash scripts/build_all_service_images.sh
#   IMAGE_REGISTRY=ghcr.io/<owner>/dydx-trading-bot IMAGE_TAG=latest PUSH=true bash scripts/build_all_service_images.sh

IMAGE_REGISTRY="${IMAGE_REGISTRY:-ghcr.io/cploutarchou/dydx-trading-bot}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
PUSH="${PUSH:-false}"
ALSO_LATEST="${ALSO_LATEST:-false}"

SERVICES=(api worker backend frontend)
DOCKERFILES=(
  "docker/Dockerfile.api"
  "docker/Dockerfile.worker"
  "docker/Dockerfile.backend"
  "docker/Dockerfile.frontend"
)

for i in "${!SERVICES[@]}"; do
  service="${SERVICES[$i]}"
  dockerfile="${DOCKERFILES[$i]}"

  image="${IMAGE_REGISTRY}/${service}:${IMAGE_TAG}"
  echo "==> Building ${image} from ${dockerfile}"

  docker build \
    -f "${dockerfile}" \
    -t "${image}" \
    .

  if [[ "${ALSO_LATEST}" == "true" ]]; then
    latest_image="${IMAGE_REGISTRY}/${service}:latest"
    echo "==> Tagging ${latest_image}"
    docker tag "${image}" "${latest_image}"
  fi

  if [[ "${PUSH}" == "true" ]]; then
    echo "==> Pushing ${image}"
    docker push "${image}"

    if [[ "${ALSO_LATEST}" == "true" ]]; then
      latest_image="${IMAGE_REGISTRY}/${service}:latest"
      echo "==> Pushing ${latest_image}"
      docker push "${latest_image}"
    fi
  fi

done

echo
echo "Build complete for: ${SERVICES[*]}"
echo "IMAGE_REGISTRY=${IMAGE_REGISTRY}"
echo "IMAGE_TAG=${IMAGE_TAG}"
if [[ "${PUSH}" == "true" ]]; then
  echo "Images pushed to registry."
else
  echo "Images built locally only (set PUSH=true to push)."
fi
