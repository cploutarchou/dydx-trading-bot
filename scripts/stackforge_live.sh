#!/usr/bin/env bash
set -euo pipefail

# Wrapper to force all StackForge commands to the live production cluster context for this repo.
# Usage examples:
#   scripts/stackforge_live.sh status --output json
#   scripts/stackforge_live.sh deploy history --output json
#   scripts/stackforge_live.sh deploy --mode nomad --file stackforge-deployment.yaml --env-file .env.stackforge --confirm-production --yes

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIVE_CLUSTER="${STACKFORGE_CLUSTER:-stackforge-cluster}"
CONFIG_FILE="${REPO_ROOT}/stackforge.yaml"

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 <stackforge args...>" >&2
  exit 2
fi

tcp_open() {
  local host="$1"
  timeout 4 bash -lc "cat < /dev/null > /dev/tcp/${host}/22" >/dev/null 2>&1
}

ssh_probe() {
  local host="$1"
  ssh \
    -o BatchMode=yes \
    -o ConnectTimeout=6 \
    -o StrictHostKeyChecking=accept-new \
    "${host}" true >/dev/null 2>&1
}

ssh_reachable() {
  local host="$1"
  if tcp_open "${host}"; then
    return 0
  fi
  ssh_probe "${host}"
}

get_inventory_ip() {
  local key="$1"
  local inventory="${HOME}/.stackforge/${LIVE_CLUSTER}/inventory.yaml"
  if [[ ! -f "${inventory}" ]]; then
    return 0
  fi

  awk -F': ' -v k="${key}" '$1 ~ "^[[:space:]]*"k"$" {print $2; exit}' "${inventory}" \
    | tr -d '"' \
    | tr -d '\r'
}

print_connectivity_diagnostics() {
  local private_ip public_ip
  private_ip="$(get_inventory_ip "private_ip")"
  public_ip="$(get_inventory_ip "public_ip")"

  echo "StackForge cluster: ${LIVE_CLUSTER}" >&2
  echo "Config file: ${CONFIG_FILE}" >&2

  if [[ -n "${private_ip}" ]]; then
    if ssh_reachable "${private_ip}"; then
      if tcp_open "${private_ip}"; then
        echo "SSH private (${private_ip}:22): reachable (direct)" >&2
      else
        echo "SSH private (${private_ip}:22): reachable (via SSH routing/proxy)" >&2
      fi
    else
      echo "SSH private (${private_ip}:22): unreachable" >&2
    fi
  else
    echo "SSH private: unknown (no private_ip in inventory)" >&2
  fi

  if [[ -n "${public_ip}" ]]; then
    if ssh_reachable "${public_ip}"; then
      echo "SSH public (${public_ip}:22): reachable" >&2
    else
      echo "SSH public (${public_ip}:22): unreachable" >&2
    fi
  else
    echo "SSH public: unknown (no public_ip in inventory)" >&2
  fi
}

get_config_value() {
  local field="$1"
  python3 - <<'PY' "${CONFIG_FILE}" "${field}"
import re, sys
from pathlib import Path
text = Path(sys.argv[1]).read_text()
field = sys.argv[2]
patterns = {
    "address":        r"(?m)^\s*address:\s*([^\s#]+)\s*$",
    "public_address": r"(?m)^\s*public_address:\s*([^\s#]+)\s*$",
}
m = re.search(patterns[field], text)
print(m.group(1) if m else "")
PY
}

ensure_private_ssh_for_live_ops() {
  local private_ip public_ip
  private_ip="$(get_inventory_ip "private_ip")"
  public_ip="$(get_inventory_ip "public_ip")"

  # Fall back to stackforge.yaml node addresses when inventory is absent
  if [[ -z "${private_ip}" ]] && [[ -f "${CONFIG_FILE}" ]]; then
    private_ip="$(get_config_value address)"
    public_ip="$(get_config_value public_address)"
  fi

  if [[ -z "${private_ip}" ]]; then
    return 0
  fi

  # StackForge live operations currently require direct TCP reachability
  # to the node address in config (ProxyJump-only reachability is not enough).
  if tcp_open "${private_ip}"; then
    return 0
  fi

  echo "[ERROR] Private node SSH is unreachable via direct TCP (${private_ip}:22)." >&2
  if ssh_probe "${private_ip}"; then
    echo "[INFO] SSH via ProxyJump appears reachable, but StackForge live validate/deploy still requires direct TCP to the configured node address." >&2
  fi
  if [[ -n "${public_ip}" ]] && ssh_reachable "${public_ip}"; then
    echo "[INFO] Public SSH is reachable (${public_ip}:22), but this cluster is configured for private-node operations." >&2
  fi
  echo "[HINT] Run 'scripts/stackforge_live.sh doctor' and connect via the required VPN/private route before deploy/install." >&2
  exit 3
}

if [[ "$1" == "doctor" ]]; then
  print_connectivity_diagnostics
  exit 0
fi

requires_private_ssh=false
case "$1" in
  deploy|install)
    requires_private_ssh=true
    ;;
  validate)
    for arg in "$@"; do
      if [[ "${arg}" == "--live" ]]; then
        requires_private_ssh=true
        break
      fi
    done
    ;;
esac

if [[ "${requires_private_ssh}" == true ]]; then
  ensure_private_ssh_for_live_ops
fi

exec stackforge --cluster "${LIVE_CLUSTER}" --config "${CONFIG_FILE}" "$@"
