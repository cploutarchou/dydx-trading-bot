#!/usr/bin/env bash
set -euo pipefail

# Wrapper to force all StackForge commands to the live production cluster context for this repo.
# Usage examples:
#   scripts/stackforge_live.sh status --output json
#   scripts/stackforge_live.sh deploy history --output json
#   scripts/stackforge_live.sh deploy --mode nomad --file stackforge-deployment.yaml --env-file .env.stackforge --confirm-production --yes

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIVE_CLUSTER="stackforge-cluster"
CONFIG_FILE="${REPO_ROOT}/stackforge.yaml"

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 <stackforge args...>" >&2
  exit 2
fi

exec stackforge --cluster "${LIVE_CLUSTER}" --config "${CONFIG_FILE}" "$@"
