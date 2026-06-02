#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env.stackforge"
STACKFORGE_CONFIG="${REPO_ROOT}/stackforge.yaml"
JOB_NAME="${JOB_NAME:-dydx-trading-bot}"
SSH_OPTIONS=(-o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)

get_stackforge_env_value() {
  local key="$1"
  python3 - <<'PY' "${ENV_FILE}" "${key}"
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text()
key = sys.argv[2]
match = re.search(rf"(?m)^{re.escape(key)}=(.*)$", text)
print(match.group(1).strip() if match else "")
PY
}

get_stackforge_config_value() {
  local field="$1"
  python3 - <<'PY' "${STACKFORGE_CONFIG}" "${field}"
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text()
field = sys.argv[2]
patterns = {
    "ssh_user": r"(?ms)^ssh:\n.*?^\s*user:\s*([^\s#]+)\s*$",
    "public_address": r"(?m)^\s*public_address:\s*([^\s#]+)\s*$",
}
match = re.search(patterns[field], text)
print(match.group(1) if match else "")
PY
}

check_prereq_file() {
  local path="$1"
  if [[ ! -f "${path}" ]]; then
    echo "Missing required file: ${path}" >&2
    exit 1
  fi
}

check_url() {
  local label="$1"
  local url="$2"
  local code

  if code="$(curl -sS -L -o /dev/null -w '%{http_code}' "${url}")"; then
    printf '  %-18s %s (%s)\n' "${label}" "${code}" "${url}"
  else
    printf '  %-18s %s (%s)\n' "${label}" "curl-failed" "${url}"
  fi
}

check_auth_route() {
  local api_base="$1"
  local code

    if code="$(curl -sS -o /dev/null -w '%{http_code}' -X POST "${api_base}/api/v1/auth/refresh")"; then
      printf '  %-18s %s (%s)\n' "auth route" "${code}" "${api_base}/api/v1/auth/refresh"
  else
      printf '  %-18s %s (%s)\n' "auth route" "curl-failed" "${api_base}/api/v1/auth/refresh"
  fi
}

run_remote_status() {
  local ssh_target="$1"
  ssh "${SSH_OPTIONS[@]}" "${ssh_target}" 'bash -s' <<'EOF'
set -euo pipefail

if [[ -f /root/.nomad-secure-env ]]; then
  # shellcheck disable=SC1091
  source /root/.nomad-secure-env
fi

echo "## Remote job summary"
nomad job status dydx-trading-bot || true

echo
echo "## Running images"
docker ps --format "{{.Image}} {{.Names}}" | grep "dydx-trading-bot" || true
EOF
}

run_auth_smoke() {
  local api_base="$1"
  local email="${AUTH_SMOKE_EMAIL:-}"
  local password="${AUTH_SMOKE_PASSWORD:-}"
  local cookie_jar login_code me_code refresh_code

  if [[ -z "${email}" || -z "${password}" ]]; then
    echo "  auth smoke         skipped (set AUTH_SMOKE_EMAIL and AUTH_SMOKE_PASSWORD to enable)"
    return 0
  fi

  cookie_jar="$(mktemp)"
  trap 'rm -f "${cookie_jar}"' RETURN

    login_code="$(curl -sS -o /dev/null -w '%{http_code}' -c "${cookie_jar}" -H 'Content-Type: application/json' -d "{\"email\":\"${email}\",\"password\":\"${password}\"}" "${api_base}/api/v1/auth/login")"
    me_code="$(curl -sS -o /dev/null -w '%{http_code}' -b "${cookie_jar}" "${api_base}/api/v1/users/me")"
    refresh_code="$(curl -sS -o /dev/null -w '%{http_code}' -b "${cookie_jar}" -X POST "${api_base}/api/v1/auth/refresh")"

  printf '  %-18s login=%s me=%s refresh=%s\n' "auth smoke" "${login_code}" "${me_code}" "${refresh_code}"
}

check_prereq_file "${ENV_FILE}"
check_prereq_file "${STACKFORGE_CONFIG}"

APP_DOMAIN="${APP_DOMAIN:-$(get_stackforge_env_value APP_DOMAIN)}"
API_DOMAIN="${API_DOMAIN:-$(get_stackforge_env_value API_DOMAIN)}"
SSH_USER="${STACKFORGE_SSH_USER:-$(get_stackforge_config_value ssh_user)}"
PUBLIC_HOST="${STACKFORGE_PUBLIC_HOST:-$(get_stackforge_config_value public_address)}"
SSH_TARGET="${STACKFORGE_REMOTE_HOST:-${SSH_USER}@${PUBLIC_HOST}}"

if [[ -z "${APP_DOMAIN}" || -z "${API_DOMAIN}" ]]; then
  echo "Missing APP_DOMAIN or API_DOMAIN in ${ENV_FILE}" >&2
  exit 1
fi

if [[ -z "${PUBLIC_HOST}" ]]; then
  echo "Missing public_address in ${STACKFORGE_CONFIG}" >&2
  exit 1
fi

if [[ -z "${SSH_USER}" ]]; then
  SSH_USER="root"
  SSH_TARGET="${STACKFORGE_REMOTE_HOST:-${SSH_USER}@${PUBLIC_HOST}}"
fi

echo "Deploy status for ${JOB_NAME}"
echo "Remote host: ${SSH_TARGET}"
echo

run_remote_status "${SSH_TARGET}"

echo
echo "## Public endpoints"
check_url "frontend" "https://${APP_DOMAIN}/"
check_url "api ready" "https://${API_DOMAIN}/ready"
check_auth_route "https://${API_DOMAIN}"
run_auth_smoke "https://${API_DOMAIN}"
