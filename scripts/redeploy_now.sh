#!/usr/bin/env bash
set -euo pipefail

# One-command production redeploy with immutable tags.
# Defaults:
#   - build + push fresh images
#   - also push :latest tags
#   - wait for service readiness checks
#
# Examples:
#   scripts/redeploy_now.sh
#   scripts/redeploy_now.sh --dry-run
#   scripts/redeploy_now.sh --tag 20260602220000

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER="${REPO_ROOT}/scripts/redeploy_with_immutable_tag.sh"

if [[ ! -x "${HELPER}" ]]; then
  echo "Missing executable helper: ${HELPER}" >&2
  exit 1
fi

args=("$@")
is_dry_run=false
for arg in "${args[@]}"; do
  if [[ "${arg}" == "--dry-run" ]]; then
    is_dry_run=true
    break
  fi
done

if [[ "${is_dry_run}" == "true" ]]; then
  exec "${HELPER}" "${args[@]}"
else
  exec "${HELPER}" --build-push --also-latest --wait "${args[@]}"
fi
