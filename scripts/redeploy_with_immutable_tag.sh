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
STACKFORGE_CONFIG="${REPO_ROOT}/stackforge.yaml"
BUILD_SCRIPT="${REPO_ROOT}/scripts/build_all_service_images.sh"

IMAGE_REGISTRY="${IMAGE_REGISTRY:-ghcr.io/cploutarchou/dydx-trading-bot}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d%H%M%S)}"
BUILD_PUSH=false
ALSO_LATEST=false
WAIT=false
DRY_RUN=false

NOMAD_SERVICE_HOST_STRATEGY="${NOMAD_SERVICE_HOST_STRATEGY:-}"
NOMAD_SERVICE_HOST="${NOMAD_SERVICE_HOST:-}"
NOMAD_PREFLIGHT_PROBE_MODE="${NOMAD_PREFLIGHT_PROBE_MODE:-}"

get_stackforge_config_value() {
  local field="$1"
  python3 - <<'PY' "${STACKFORGE_CONFIG}" "${field}"
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text()
field = sys.argv[2]
patterns = {
    "cluster_name": r"(?m)^\s*name:\s*([^\s#]+)\s*$",
    "ssh_user": r"(?ms)^ssh:\n.*?^\s*user:\s*([^\s#]+)\s*$",
    "public_address": r"(?m)^\s*public_address:\s*([^\s#]+)\s*$",
}
match = re.search(patterns[field], text)
print(match.group(1) if match else "")
PY
}

remote_stackforge_deploy() {
  local stackforge_cluster ssh_user public_address ssh_target remote_prefix remote_manifest remote_env remote_config
  stackforge_cluster="${STACKFORGE_CLUSTER:-$(get_stackforge_config_value cluster_name)}"
  ssh_user="${STACKFORGE_SSH_USER:-$(get_stackforge_config_value ssh_user)}"
  public_address="${STACKFORGE_PUBLIC_HOST:-$(get_stackforge_config_value public_address)}"

  if [[ -z "${NOMAD_SERVICE_HOST_STRATEGY}" ]]; then
    NOMAD_SERVICE_HOST_STRATEGY="node-address"
    echo "[INFO] No NOMAD_SERVICE_HOST_STRATEGY set; defaulting to node-address for remote fallback" >&2
  fi

  if [[ -z "${NOMAD_PREFLIGHT_PROBE_MODE}" ]]; then
    NOMAD_PREFLIGHT_PROBE_MODE="host-network"
    echo "[INFO] No NOMAD_PREFLIGHT_PROBE_MODE set; defaulting to host-network for remote fallback" >&2
  fi

  if [[ -z "${public_address}" ]]; then
    echo "Remote StackForge fallback failed: could not determine public host from ${STACKFORGE_CONFIG}" >&2
    return 1
  fi

  if [[ -z "${ssh_user}" ]]; then
    ssh_user="root"
  fi

  ssh_target="${STACKFORGE_REMOTE_HOST:-${ssh_user}@${public_address}}"
  remote_prefix="/tmp/dydx-stackforge-${IMAGE_TAG}-$$"
  remote_manifest="${remote_prefix}.manifest.yaml"
  remote_env="${remote_prefix}.env"
  remote_config="${remote_prefix}.stackforge.yaml"

  echo "==> Falling back to host-side StackForge deploy via ${ssh_target}"

  ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "${ssh_target}" "umask 077 && cat > '${remote_manifest}'" < "${TMP_MANIFEST}"
  ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "${ssh_target}" "umask 077 && cat > '${remote_env}'" < "${ENV_FILE}"
  ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "${ssh_target}" "umask 077 && cat > '${remote_config}'" < "${STACKFORGE_CONFIG}"

  if [[ "${DRY_RUN}" == "true" ]]; then
    ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "${ssh_target}" \
      "REMOTE_MANIFEST='${remote_manifest}' REMOTE_ENV='${remote_env}' REMOTE_CONFIG='${remote_config}' STACKFORGE_CLUSTER='${stackforge_cluster}' WAIT='${WAIT}' DRY_RUN='${DRY_RUN}' NOMAD_SERVICE_HOST_STRATEGY='${NOMAD_SERVICE_HOST_STRATEGY}' NOMAD_SERVICE_HOST='${NOMAD_SERVICE_HOST}' NOMAD_PREFLIGHT_PROBE_MODE='${NOMAD_PREFLIGHT_PROBE_MODE}' bash -s" <<'EOF' \
      | sed -E 's/ghp_[A-Za-z0-9_]+/***redacted***/g; s/("password"\s*:\s*")[^"]+(")/\1***redacted***\2/g'
set -euo pipefail
trap 'rm -f "${REMOTE_MANIFEST}" "${REMOTE_ENV}" "${REMOTE_CONFIG}"' EXIT

if [[ -f /root/.nomad-secure-env ]]; then
  # shellcheck disable=SC1091
  source /root/.nomad-secure-env
fi

deploy_args=(
  deploy
  --confirm-production
  --yes
  --mode compose
  --no-build
  --file "${REMOTE_MANIFEST}"
  --env-file "${REMOTE_ENV}"
)

if [[ "${WAIT}" == "true" ]]; then
  deploy_args+=(--wait)
fi

if [[ "${DRY_RUN}" == "true" ]]; then
  deploy_args+=(--dry-run)
fi

if [[ -n "${NOMAD_SERVICE_HOST_STRATEGY:-}" ]]; then
  deploy_args+=(--nomad-service-host-strategy "${NOMAD_SERVICE_HOST_STRATEGY}")
fi

if [[ "${NOMAD_SERVICE_HOST_STRATEGY:-}" == "custom" && -n "${NOMAD_SERVICE_HOST:-}" ]]; then
  deploy_args+=(--nomad-service-host "${NOMAD_SERVICE_HOST}")
fi

if [[ -n "${NOMAD_PREFLIGHT_PROBE_MODE:-}" ]]; then
  deploy_args+=(--nomad-preflight-probe-mode "${NOMAD_PREFLIGHT_PROBE_MODE}")
fi

set +e
deploy_output="$(stackforge --cluster "${STACKFORGE_CLUSTER}" --config "${REMOTE_CONFIG}" "${deploy_args[@]}" 2>&1)"
deploy_status=$?
set -e

printf '%s\n' "${deploy_output}"

if [[ ${deploy_status} -ne 0 ]]; then
  if [[ "${WAIT}" == "true" ]] && grep -q "nomad deploy wait timed out" <<<"${deploy_output}"; then
    echo "[WARN] StackForge wait timed out; validating Nomad job health before failing..." >&2
    python3 - <<'PY'
import json
import subprocess
import sys

try:
    raw = subprocess.check_output(["nomad", "job", "status", "-json", "dydx-trading-bot"], text=True)
except Exception as exc:
    print(f"nomad health check failed: {exc}", file=sys.stderr)
    raise SystemExit(1)

data = json.loads(raw)
if isinstance(data, list):
  data = data[0] if data else {}
if not isinstance(data, dict):
  print(f"unexpected nomad JSON shape: {type(data).__name__}", file=sys.stderr)
  raise SystemExit(1)

status = str(data.get("Status", "")).lower()

deployment = data.get("LatestDeploymentSummary")
dep_status = ""
if isinstance(deployment, dict):
  dep_status = str(deployment.get("Status", "")).lower()
elif isinstance(deployment, list) and deployment:
  first = deployment[0]
  if isinstance(first, dict):
    dep_status = str(first.get("Status", "")).lower()

task_groups = data.get("TaskGroups") or []
healthy = True
if isinstance(task_groups, dict):
  iterable = task_groups.values()
elif isinstance(task_groups, list):
  iterable = task_groups
else:
  iterable = []

for tg in iterable:
  if not isinstance(tg, dict):
    continue
  desired = int(tg.get("Desired", 0) or 0)
  running = int(tg.get("Running", 0) or 0)
  if desired > 0 and running < desired:
    healthy = False
    break

if status == "running" and dep_status in {"successful", "running"} and healthy:
    print("Nomad job is healthy despite wait timeout; treating deploy as success.")
    raise SystemExit(0)

print("Nomad job is not healthy after wait timeout.", file=sys.stderr)
raise SystemExit(1)
PY
    exit $?
  fi
  exit ${deploy_status}
fi
EOF
  else
    ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "${ssh_target}" \
      "REMOTE_MANIFEST='${remote_manifest}' REMOTE_ENV='${remote_env}' REMOTE_CONFIG='${remote_config}' STACKFORGE_CLUSTER='${stackforge_cluster}' WAIT='${WAIT}' DRY_RUN='${DRY_RUN}' NOMAD_SERVICE_HOST_STRATEGY='${NOMAD_SERVICE_HOST_STRATEGY}' NOMAD_SERVICE_HOST='${NOMAD_SERVICE_HOST}' NOMAD_PREFLIGHT_PROBE_MODE='${NOMAD_PREFLIGHT_PROBE_MODE}' bash -s" <<'EOF'
set -euo pipefail
trap 'rm -f "${REMOTE_MANIFEST}" "${REMOTE_ENV}" "${REMOTE_CONFIG}"' EXIT

if [[ -f /root/.nomad-secure-env ]]; then
  # shellcheck disable=SC1091
  source /root/.nomad-secure-env
fi

deploy_args=(
  deploy
  --confirm-production
  --yes
  --mode compose
  --no-build
  --file "${REMOTE_MANIFEST}"
  --env-file "${REMOTE_ENV}"
)

if [[ "${WAIT}" == "true" ]]; then
  deploy_args+=(--wait)
fi

if [[ "${DRY_RUN}" == "true" ]]; then
  deploy_args+=(--dry-run)
fi

if [[ -n "${NOMAD_SERVICE_HOST_STRATEGY:-}" ]]; then
  deploy_args+=(--nomad-service-host-strategy "${NOMAD_SERVICE_HOST_STRATEGY}")
fi

if [[ "${NOMAD_SERVICE_HOST_STRATEGY:-}" == "custom" && -n "${NOMAD_SERVICE_HOST:-}" ]]; then
  deploy_args+=(--nomad-service-host "${NOMAD_SERVICE_HOST}")
fi

if [[ -n "${NOMAD_PREFLIGHT_PROBE_MODE:-}" ]]; then
  deploy_args+=(--nomad-preflight-probe-mode "${NOMAD_PREFLIGHT_PROBE_MODE}")
fi

set +e
deploy_output="$(stackforge --cluster "${STACKFORGE_CLUSTER}" --config "${REMOTE_CONFIG}" "${deploy_args[@]}" 2>&1)"
deploy_status=$?
set -e

printf '%s\n' "${deploy_output}"

if [[ ${deploy_status} -ne 0 ]]; then
  if [[ "${WAIT}" == "true" ]] && grep -q "nomad deploy wait timed out" <<<"${deploy_output}"; then
    echo "[WARN] StackForge wait timed out; validating Nomad job health before failing..." >&2
    python3 - <<'PY'
import json
import subprocess
import sys

try:
    raw = subprocess.check_output(["nomad", "job", "status", "-json", "dydx-trading-bot"], text=True)
except Exception as exc:
    print(f"nomad health check failed: {exc}", file=sys.stderr)
    raise SystemExit(1)

data = json.loads(raw)
if isinstance(data, list):
  data = data[0] if data else {}
if not isinstance(data, dict):
  print(f"unexpected nomad JSON shape: {type(data).__name__}", file=sys.stderr)
  raise SystemExit(1)

status = str(data.get("Status", "")).lower()

deployment = data.get("LatestDeploymentSummary")
dep_status = ""
if isinstance(deployment, dict):
  dep_status = str(deployment.get("Status", "")).lower()
elif isinstance(deployment, list) and deployment:
  first = deployment[0]
  if isinstance(first, dict):
    dep_status = str(first.get("Status", "")).lower()

task_groups = data.get("TaskGroups") or []
healthy = True
if isinstance(task_groups, dict):
  iterable = task_groups.values()
elif isinstance(task_groups, list):
  iterable = task_groups
else:
  iterable = []

for tg in iterable:
  if not isinstance(tg, dict):
    continue
  desired = int(tg.get("Desired", 0) or 0)
  running = int(tg.get("Running", 0) or 0)
  if desired > 0 and running < desired:
    healthy = False
    break

if status == "running" and dep_status in {"successful", "running"} and healthy:
    print("Nomad job is healthy despite wait timeout; treating deploy as success.")
    raise SystemExit(0)

print("Nomad job is not healthy after wait timeout.", file=sys.stderr)
raise SystemExit(1)
PY
    exit $?
  fi
  exit ${deploy_status}
fi
EOF
  fi
}

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

if [[ ! -f "${STACKFORGE_CONFIG}" ]]; then
  echo "Missing StackForge config: ${STACKFORGE_CONFIG}" >&2
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

if [[ -n "${NOMAD_SERVICE_HOST_STRATEGY}" ]]; then
  deploy_args+=(--nomad-service-host-strategy "${NOMAD_SERVICE_HOST_STRATEGY}")
fi

if [[ "${NOMAD_SERVICE_HOST_STRATEGY}" == "custom" && -n "${NOMAD_SERVICE_HOST}" ]]; then
  deploy_args+=(--nomad-service-host "${NOMAD_SERVICE_HOST}")
fi

if [[ -n "${NOMAD_PREFLIGHT_PROBE_MODE}" ]]; then
  deploy_args+=(--nomad-preflight-probe-mode "${NOMAD_PREFLIGHT_PROBE_MODE}")
fi

set +e
if [[ "${DRY_RUN}" == "true" ]]; then
  deploy_output="$("${STACKFORGE_WRAPPER}" "${deploy_args[@]}" 2>&1)"
else
  deploy_output="$("${STACKFORGE_WRAPPER}" "${deploy_args[@]}" 2>&1)"
fi
deploy_status=$?
set -e

if [[ ${deploy_status} -eq 0 ]]; then
  if [[ "${DRY_RUN}" == "true" ]]; then
    printf '%s\n' "${deploy_output}" | sed -E 's/ghp_[A-Za-z0-9_]+/***redacted***/g; s/("password"\s*:\s*")[^"]+(")/\1***redacted***\2/g'
  else
    printf '%s\n' "${deploy_output}"
  fi
elif [[ ${deploy_status} -eq 3 ]]; then
  printf '%s\n' "${deploy_output}" >&2
  remote_stackforge_deploy
else
  if [[ "${DRY_RUN}" == "true" ]]; then
    printf '%s\n' "${deploy_output}" | sed -E 's/ghp_[A-Za-z0-9_]+/***redacted***/g; s/("password"\s*:\s*")[^"]+(")/\1***redacted***\2/g' >&2
  else
    printf '%s\n' "${deploy_output}" >&2
  fi
  exit ${deploy_status}
fi

echo
echo "Done."
echo "IMAGE_REGISTRY=${IMAGE_REGISTRY}"
echo "IMAGE_TAG=${IMAGE_TAG}"
echo "Temporary manifest: ${TMP_MANIFEST} (auto-cleaned on exit)"
