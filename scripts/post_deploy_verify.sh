#!/usr/bin/env bash
set -euo pipefail

# One-command post-deploy verification for StackForge app rollout.
# Usage:
#   scripts/post_deploy_verify.sh
#   scripts/post_deploy_verify.sh --host 159.195.82.201 --cluster stackforge-cluster

HOST="159.195.82.201"
CLUSTER="stackforge-cluster"
API_PORT="8889"
FRONTEND_PORT="5173"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST="$2"
      shift 2
      ;;
    --cluster)
      CLUSTER="$2"
      shift 2
      ;;
    --api-port)
      API_PORT="$2"
      shift 2
      ;;
    --frontend-port)
      FRONTEND_PORT="$2"
      shift 2
      ;;
    -h|--help)
      sed -n '1,20p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

echo "=== StackForge Post-Deploy Verify ==="
echo "Host: ${HOST}"
echo "Cluster: ${CLUSTER}"
echo

echo "[1/4] API health check"
API_HEALTH_JSON="$(curl -fsS "http://${HOST}:${API_PORT}/health")"
echo "API healthy response received"

echo "[2/4] Frontend HTTP check"
FRONTEND_HEADERS="$(curl -fsSI "http://${HOST}:${FRONTEND_PORT}" | head -n 5)"
echo "Frontend headers:\n${FRONTEND_HEADERS}"

echo "[3/4] StackForge cluster status"
STATUS_JSON="$(stackforge status --cluster "${CLUSTER}" --output json)"
if command -v jq >/dev/null 2>&1; then
  echo "Cluster: $(jq -r '.cluster // "unknown"' <<<"${STATUS_JSON}")"
  echo "Install status: $(jq -r '.install_status // "unknown"' <<<"${STATUS_JSON}")"
  echo "Health: $(jq -r '.health // "unknown"' <<<"${STATUS_JSON}")"
else
  echo "jq not found; raw status (first 20 lines):"
  echo "${STATUS_JSON}" | head -n 20
fi

echo "[4/4] Result"
echo "PASS: API and frontend endpoints are reachable and StackForge status command succeeded."

echo
echo "--- API /health snippet ---"
echo "${API_HEALTH_JSON}" | head -c 400; echo
