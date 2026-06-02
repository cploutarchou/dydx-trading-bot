#!/usr/bin/env bash
set -euo pipefail

# Redeploy using immutable GHCR tags without permanently editing stackforge-deployment.yaml.
#
# Examples:
#   scripts/redeploy_with_immutable_tag.sh
#   scripts/redeploy_with_immutable_tag.sh --tag 20260602190000
#   scripts/redeploy_with_immutable_tag.sh --build-push --also-latest --wait

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_MANIFEST="${REPO_ROOT}/stackforge-deployment.yaml"
ENV_FILE="${REPO_ROOT}/.env.stackforge"
STACKFORGE_WRAPPER="${REPO_ROOT}/scripts/stackforge_live.sh"
BUILD_SCRIPT="${REPO_ROOT}/scripts/build_all_service_images.sh"

IMAGE_REGISTRY="${IMAGE_REGISTRY:-ghcr.io/cploutarchou/dydx-trading-bot}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d%H%M%S)}"
BUILD_PUSH=false
ALSO_LATEST=false
WAIT=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag)
      IMAGE_TAG="$2"
      shift 2
      ;;
    --build-push)
      BUILD_PUSH=true
      shift
      ;;
    --also-latest)
      ALSO_LATEST=true
      shift
      ;;
    --wait)
      WAIT=true
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ ! -f "${BASE_MANIFEST}" ]]; then
  echo "Missing manifest: ${BASE_MANIFEST}" >&2
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing env file: ${ENV_FILE}" >&2
  exit 1
fi

if [[ ! -x "${STACKFORGE_WRAPPER}" ]]; then
  echo "Missing executable wrapper: ${STACKFORGE_WRAPPER}" >&2
  exit 1
fi

if [[ "${BUILD_PUSH}" == "true" ]]; then
  echo "==> Building and pushing images with IMAGE_TAG=${IMAGE_TAG}"
  IMAGE_REGISTRY="${IMAGE_REGISTRY}" \
  IMAGE_TAG="${IMAGE_TAG}" \
  PUSH=true \
  ALSO_LATEST="${ALSO_LATEST}" \
  bash "${BUILD_SCRIPT}"
fi

TMP_MANIFEST="$(mktemp "${REPO_ROOT}/.stackforge-deployment.XXXXXX.yaml")"
trap 'rm -f "${TMP_MANIFEST}"' EXIT

echo "==> Rendering temporary manifest with immutable tags"
python3 - <<'PY' "${BASE_MANIFEST}" "${TMP_MANIFEST}" "${IMAGE_REGISTRY}" "${IMAGE_TAG}"
import re
import sys
from pathlib import Path

src = Path(sys.argv[1]).read_text()
dst = Path(sys.argv[2])
registry = sys.argv[3]
tag = sys.argv[4]

patterns = {
    "api": re.compile(rf"(image:\s*{re.escape(registry)}/api:)([^\s]+)"),
    "backend": re.compile(rf"(image:\s*{re.escape(registry)}/backend:)([^\s]+)"),
    "frontend": re.compile(rf"(image:\s*{re.escape(registry)}/frontend:)([^\s]+)"),
}

rendered = src
for name, pattern in patterns.items():
    rendered, count = pattern.subn(lambda m: f"{m.group(1)}{tag}", rendered, count=1)
    if count != 1:
        raise SystemExit(f"Could not uniquely update image tag for service: {name}")

dst.write_text(rendered)
PY

echo "==> Deploying tag ${IMAGE_TAG}"
deploy_args=(
  deploy
  --confirm-production
  --yes
  --mode nomad
  --file "${TMP_MANIFEST}"
  --env-file "${ENV_FILE}"
  --nomad-address https://127.0.0.1:4646
  --nomad-cacert /etc/nomad.d/tls/ca.pem
)

if [[ "${WAIT}" == "true" ]]; then
  deploy_args+=(--wait)
fi

if [[ "${DRY_RUN}" == "true" ]]; then
  deploy_args+=(--dry-run)
fi

if [[ "${DRY_RUN}" == "true" ]]; then
  "${STACKFORGE_WRAPPER}" "${deploy_args[@]}" \
    2>&1 | sed -E 's/ghp_[A-Za-z0-9_]+/***redacted***/g; s/("password"\s*:\s*")[^"]+("?)/\1***redacted***\2/g'
else
  "${STACKFORGE_WRAPPER}" "${deploy_args[@]}"
fi

echo
echo "Done."
echo "IMAGE_REGISTRY=${IMAGE_REGISTRY}"
echo "IMAGE_TAG=${IMAGE_TAG}"
echo "Temporary manifest: ${TMP_MANIFEST} (auto-cleaned on exit)"
