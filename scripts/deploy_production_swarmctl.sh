#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/deploy_production_swarmctl.sh [options]

Options:
  --env <name>                 Target swarmctl environment (default: production)
  --image-tag <tag>            Image tag to deploy (default: sha-<origin_default_branch_short_sha>)
  --dry-run <true|false>       Validate + plan only (default: true)
  --deploy-infra <true|false>  Deploy HA infra stacks (default: false)
  --deploy-apps <true|false>   Deploy app manifests (default: true)
  --with-registry-auth <true|false>
                               Forward local Docker registry credentials to Swarm (default: true)
  --docker-host <value>        Override DOCKER_HOST (default: derived from ~/.swarmctl/config.yaml)
  --api-health-url <url>       Optional API health endpoint to test after deploy
  --frontend-url <url>         Optional frontend URL to test after deploy
  -h, --help                   Show this help

Examples:
  # Safe preflight
  scripts/deploy_production_swarmctl.sh --env production --dry-run true

  # Real production deploy of apps only
  scripts/deploy_production_swarmctl.sh --env production --dry-run false --deploy-infra false --deploy-apps true
EOF
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

tolower() {
  echo "$1" | tr '[:upper:]' '[:lower:]'
}

# Defaults
ENVIRONMENT="production"
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  default_branch="$(git remote show origin 2>/dev/null | sed -n '/HEAD branch/s/.*: //p' | head -n1 || true)"
  if [[ -z "$default_branch" ]]; then
    default_branch="master"
  fi

  remote_sha="$(git ls-remote --heads origin "$default_branch" 2>/dev/null | awk '{print $1}' | head -n1 || true)"
  if [[ -n "$remote_sha" ]]; then
    git_short_sha="${remote_sha:0:7}"
  else
    git_short_sha="$(git rev-parse --short HEAD 2>/dev/null || true)"
  fi
else
  git_short_sha=""
fi
IMAGE_TAG="${git_short_sha:+sha-${git_short_sha}}"
if [[ -z "$IMAGE_TAG" ]]; then
  IMAGE_TAG="latest"
fi
DRY_RUN="true"
DEPLOY_INFRA="false"
DEPLOY_APPS="true"
WITH_REGISTRY_AUTH="true"
DOCKER_HOST_OVERRIDE=""
API_HEALTH_URL=""
FRONTEND_URL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      ENVIRONMENT="$2"; shift 2 ;;
    --image-tag)
      IMAGE_TAG="$2"; shift 2 ;;
    --dry-run)
      DRY_RUN="$(tolower "$2")"; shift 2 ;;
    --deploy-infra)
      DEPLOY_INFRA="$(tolower "$2")"; shift 2 ;;
    --deploy-apps)
      DEPLOY_APPS="$(tolower "$2")"; shift 2 ;;
    --with-registry-auth)
      WITH_REGISTRY_AUTH="$(tolower "$2")"; shift 2 ;;
    --docker-host)
      DOCKER_HOST_OVERRIDE="$2"; shift 2 ;;
    --api-health-url)
      API_HEALTH_URL="$2"; shift 2 ;;
    --frontend-url)
      FRONTEND_URL="$2"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1 ;;
  esac
done

for v in "$DRY_RUN" "$DEPLOY_INFRA" "$DEPLOY_APPS" "$WITH_REGISTRY_AUTH"; do
  if [[ "$v" != "true" && "$v" != "false" ]]; then
    echo "Boolean flags must be true|false" >&2
    exit 1
  fi
done

require_cmd swarmctl
require_cmd docker
require_cmd python3

resolve_docker_host() {
  python3 - "$ENVIRONMENT" <<'PY'
import pathlib
import sys
import yaml

env_name = sys.argv[1]
cfg_path = pathlib.Path.home() / '.swarmctl' / 'config.yaml'
cfg = yaml.safe_load(cfg_path.read_text()) or {}
contexts = cfg.get('contexts') or {}
target = None
for name, ctx in contexts.items():
  if not isinstance(ctx, dict):
    continue
  if ctx.get('environment') == env_name:
    target = ctx
    break
if target is None:
  current = cfg.get('currentContext')
  target = contexts.get(current) if current else None
if not isinstance(target, dict):
  raise SystemExit('Unable to resolve swarmctl context for environment: ' + env_name)
host = str(target.get('managerHost', '')).strip()
user = str(target.get('sshUser', '')).strip() or 'root'
if not host:
  raise SystemExit('Missing managerHost in ~/.swarmctl/config.yaml for environment: ' + env_name)
print(f'ssh://{user}@{host}')
PY
}

python3 - <<'PY'
import importlib.util
import sys
if importlib.util.find_spec('yaml') is None:
    print('Missing Python package: pyyaml (pip install pyyaml)', file=sys.stderr)
    sys.exit(1)
PY

env_lc="$(tolower "$ENVIRONMENT")"
tag_lc="$(tolower "$IMAGE_TAG")"
if [[ "$env_lc" != "staging" ]]; then
  if [[ "$tag_lc" == "latest" ]]; then
    :
  elif [[ "$tag_lc" =~ ^sha-[0-9a-f]{7,64}$ ]]; then
    :
  elif [[ "$tag_lc" =~ ^v?[0-9]+\.[0-9]+\.[0-9]+([-.][a-z0-9.]+)?$ ]]; then
    :
  else
    echo "Blocked: non-staging image_tag '$IMAGE_TAG' is not allowed (env=$ENVIRONMENT)." >&2
    echo "Allowed patterns: latest, sha-<hex>, v<major>.<minor>.<patch>, <major>.<minor>.<patch> (optional -rc.1 style suffix)." >&2
    exit 1
  fi
fi

echo "=== swarmctl deploy config ==="
echo "environment : $ENVIRONMENT"
echo "image_tag   : $IMAGE_TAG"
echo "dry_run     : $DRY_RUN"
echo "deploy_infra: $DEPLOY_INFRA"
echo "deploy_apps : $DEPLOY_APPS"
echo "with_reg_auth: $WITH_REGISTRY_AUTH"

if [[ -n "$DOCKER_HOST_OVERRIDE" ]]; then
  export DOCKER_HOST="$DOCKER_HOST_OVERRIDE"
else
  export DOCKER_HOST="$(resolve_docker_host)"
fi

echo "docker_host : $DOCKER_HOST"

ALLOW_LATEST_ARGS=()
if [[ "$tag_lc" == "latest" ]]; then
  ALLOW_LATEST_ARGS+=(--allow-latest)
fi

if [[ "$WITH_REGISTRY_AUTH" == "true" ]]; then
  if ! docker system info >/dev/null 2>&1; then
    echo "Warning: Docker CLI could not reach DOCKER_HOST=$DOCKER_HOST" >&2
  fi
  if ! docker info >/dev/null 2>&1; then
    echo "Warning: local Docker daemon is not reachable; only remote DOCKER_HOST checks will work." >&2
  fi
  if [[ ! -f "$HOME/.docker/config.json" ]]; then
    echo "Warning: no local Docker login config found at ~/.docker/config.json." >&2
    echo "For private GHCR images, run: docker login ghcr.io" >&2
  fi
fi

echo "=== infra observability ==="
swarmctl infra ips --env "$ENVIRONMENT"
swarmctl infra topology --env "$ENVIRONMENT"

echo "=== validate infra compose files ==="
docker compose -f swarm/stack-postgres-ha.yml config >/dev/null
docker compose -f swarm/stack-redis-ha.yml config >/dev/null

echo "=== validate source manifests ==="
swarmctl validate -f app-api.yml --env "$ENVIRONMENT" "${ALLOW_LATEST_ARGS[@]}"
swarmctl validate -f app-backend.yml --env "$ENVIRONMENT" "${ALLOW_LATEST_ARGS[@]}"
swarmctl validate -f app-worker.yml --env "$ENVIRONMENT" "${ALLOW_LATEST_ARGS[@]}"
swarmctl validate -f app.yml --env "$ENVIRONMENT" "${ALLOW_LATEST_ARGS[@]}"

RENDER_DIR=".rendered/deploy-${ENVIRONMENT}-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RENDER_DIR"
cp app.yml "$RENDER_DIR/app.yml"
cp app-api.yml "$RENDER_DIR/app-api.yml"
cp app-backend.yml "$RENDER_DIR/app-backend.yml"
cp app-worker.yml "$RENDER_DIR/app-worker.yml"

IMAGE_TAG="$IMAGE_TAG" RENDER_DIR="$RENDER_DIR" python3 - <<'PY'
import os
import pathlib
import yaml

image_tag = os.environ['IMAGE_TAG']
render_dir = pathlib.Path(os.environ['RENDER_DIR'])
for filename in ['app.yml', 'app-api.yml', 'app-backend.yml', 'app-worker.yml']:
    p = render_dir / filename
    data = yaml.safe_load(p.read_text())
    spec = data.setdefault('spec', {})
    image = spec.get('image')
    if not isinstance(image, dict):
        raise RuntimeError(f'Expected spec.image object in {p}')
    image['tag'] = image_tag
    p.write_text(yaml.safe_dump(data, sort_keys=False))
PY

echo "=== validate rendered manifests ==="
swarmctl validate -f "$RENDER_DIR/app-api.yml" --env "$ENVIRONMENT" "${ALLOW_LATEST_ARGS[@]}"
swarmctl validate -f "$RENDER_DIR/app-backend.yml" --env "$ENVIRONMENT" "${ALLOW_LATEST_ARGS[@]}"
swarmctl validate -f "$RENDER_DIR/app-worker.yml" --env "$ENVIRONMENT" "${ALLOW_LATEST_ARGS[@]}"
swarmctl validate -f "$RENDER_DIR/app.yml" --env "$ENVIRONMENT" "${ALLOW_LATEST_ARGS[@]}"

echo "=== plan rendered manifests ==="
swarmctl plan -f "$RENDER_DIR/app-api.yml" --env "$ENVIRONMENT" "${ALLOW_LATEST_ARGS[@]}"
swarmctl plan -f "$RENDER_DIR/app-backend.yml" --env "$ENVIRONMENT" "${ALLOW_LATEST_ARGS[@]}"
swarmctl plan -f "$RENDER_DIR/app-worker.yml" --env "$ENVIRONMENT" "${ALLOW_LATEST_ARGS[@]}"
swarmctl plan -f "$RENDER_DIR/app.yml" --env "$ENVIRONMENT" "${ALLOW_LATEST_ARGS[@]}"

if [[ "$DRY_RUN" == "true" ]]; then
  echo "Dry run complete. Rendered manifests are in: $RENDER_DIR"
  exit 0
fi

if [[ "$DEPLOY_INFRA" == "true" ]]; then
  echo "=== deploy infra stacks ==="
  swarmctl stack deploy dydx-postgres-ha -c swarm/stack-postgres-ha.yml --env "$ENVIRONMENT"
  swarmctl stack deploy dydx-redis-ha -c swarm/stack-redis-ha.yml --env "$ENVIRONMENT"
  swarmctl stack status dydx-postgres-ha --env "$ENVIRONMENT"
  swarmctl stack status dydx-redis-ha --env "$ENVIRONMENT"
fi

if [[ "$DEPLOY_APPS" == "true" ]]; then
  echo "=== deploy app manifests ==="
  APPLY_ARGS=(--env "$ENVIRONMENT" --wait)
  APPLY_ARGS+=("${ALLOW_LATEST_ARGS[@]}")
  if [[ "$WITH_REGISTRY_AUTH" == "true" ]]; then
    APPLY_ARGS+=(--with-registry-auth)
  fi

  swarmctl apply -f "$RENDER_DIR/app-api.yml" "${APPLY_ARGS[@]}" --timeout 5m
  swarmctl apply -f "$RENDER_DIR/app-backend.yml" "${APPLY_ARGS[@]}" --timeout 5m
  swarmctl apply -f "$RENDER_DIR/app-worker.yml" "${APPLY_ARGS[@]}" --timeout 10m
  swarmctl apply -f "$RENDER_DIR/app.yml" "${APPLY_ARGS[@]}" --timeout 5m

  echo "=== rollout status ==="
  swarmctl rollout status dydx-trading-bot-api --env "$ENVIRONMENT"
  swarmctl rollout status dydx-trading-bot-backend --env "$ENVIRONMENT"
  swarmctl rollout status dydx-trading-bot-worker --env "$ENVIRONMENT"
  swarmctl rollout status dydx-trading-bot-frontend --env "$ENVIRONMENT"
fi

if [[ -n "$API_HEALTH_URL" ]]; then
  echo "=== api health check ==="
  curl -fsS "$API_HEALTH_URL"
  echo
fi

if [[ -n "$FRONTEND_URL" ]]; then
  echo "=== frontend check ==="
  curl -I -fsS "$FRONTEND_URL" | head -n 10
fi

echo "Deployment flow complete."
