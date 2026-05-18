#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/bootstrap_production_prereqs.sh [options]

Options:
  --manager <host>            Swarm manager host (default: 156.67.29.10)
  --user <ssh-user>           SSH user (default: root)
  --key <path>                SSH private key path (default: ~/.ssh/id_ed25519)
  --secrets-file <path>       Env file with secret values (required unless --skip-secrets)
  --ghcr-user <user>          GHCR username (optional)
  --ghcr-token-env <VAR>      Env var name that contains GHCR token (default: GHCR_TOKEN)
  --skip-ghcr-login           Skip docker login ghcr.io
  --skip-secrets              Skip secret creation/update
  --skip-networks             Skip network creation checks
  -h, --help                  Show this help

secrets-file format (shell env file):
  DYDX_BOT_DB_PASSWORD=...
  DYDX_DB_PASSWORD=...
  DYDX_POSTGRES_PASSWORD=...
  DYDX_REDIS_PASSWORD=...
  DYDX_JWT_SECRET_KEY=...
  DYDX_SECRET_KEY=...
  DYDX_ENCRYPTION_KEY=...
  DYDX_BOT_API_TOKEN=...

# Optional HA infra overrides (fallbacks are derived automatically):
# PG_SU_PASSWORD (default: DYDX_POSTGRES_PASSWORD)
# PG_APP_PASSWORD (default: DYDX_POSTGRES_PASSWORD)
# PG_REPMGR_PASSWORD (default: DYDX_POSTGRES_PASSWORD)
# PGPOOL_ADMIN_PASSWORD (default: DYDX_POSTGRES_PASSWORD)
# REDIS_PASSWORD (default: DYDX_REDIS_PASSWORD)

Example:
  export GHCR_TOKEN='ghp_...'
  scripts/bootstrap_production_prereqs.sh \
    --manager 156.67.29.10 \
    --user root \
    --key ~/.ssh/id_ed25519 \
    --secrets-file ./production.secrets.env \
    --ghcr-user cploutarchou
EOF
}

MANAGER_HOST="156.67.29.10"
SSH_USER="root"
SSH_KEY_PATH="$HOME/.ssh/id_ed25519"
SECRETS_FILE=""
GHCR_USER=""
GHCR_TOKEN_ENV="GHCR_TOKEN"
SKIP_GHCR_LOGIN="false"
SKIP_SECRETS="false"
SKIP_NETWORKS="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --manager)
      MANAGER_HOST="$2"; shift 2 ;;
    --user)
      SSH_USER="$2"; shift 2 ;;
    --key)
      SSH_KEY_PATH="$2"; shift 2 ;;
    --secrets-file)
      SECRETS_FILE="$2"; shift 2 ;;
    --ghcr-user)
      GHCR_USER="$2"; shift 2 ;;
    --ghcr-token-env)
      GHCR_TOKEN_ENV="$2"; shift 2 ;;
    --skip-ghcr-login)
      SKIP_GHCR_LOGIN="true"; shift ;;
    --skip-secrets)
      SKIP_SECRETS="true"; shift ;;
    --skip-networks)
      SKIP_NETWORKS="true"; shift ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1 ;;
  esac
done

if [[ "$SKIP_SECRETS" != "true" && -z "$SECRETS_FILE" ]]; then
  echo "--secrets-file is required unless --skip-secrets is used" >&2
  exit 1
fi

if [[ "$SKIP_SECRETS" != "true" && ! -f "$SECRETS_FILE" ]]; then
  echo "Secrets file not found: $SECRETS_FILE" >&2
  exit 1
fi

if [[ ! -f "$SSH_KEY_PATH" ]]; then
  echo "SSH key not found: $SSH_KEY_PATH" >&2
  exit 1
fi

SSH_OPTS=(
  -i "$SSH_KEY_PATH"
  -o StrictHostKeyChecking=no
  -o UserKnownHostsFile=/dev/null
  -o ConnectTimeout=15
)

REMOTE="${SSH_USER}@${MANAGER_HOST}"

echo "=== target ==="
echo "manager: ${MANAGER_HOST}"
echo "user   : ${SSH_USER}"

echo "=== connectivity check ==="
ssh "${SSH_OPTS[@]}" "$REMOTE" "hostname && docker node ls >/dev/null"

if [[ "$SKIP_NETWORKS" != "true" ]]; then
  echo "=== ensure overlay networks ==="
  ssh "${SSH_OPTS[@]}" "$REMOTE" "
    set -euo pipefail
    ensure_net() {
      local name=\"\$1\"
      if docker network ls --format '{{.Name}}' | grep -qx \"\$name\"; then
        echo \"network exists: \$name\"
      else
        docker network create --driver overlay --attachable \"\$name\" >/dev/null
        echo \"network created: \$name\"
      fi
    }
    ensure_net internal
    ensure_net public
  "
fi

if [[ "$SKIP_GHCR_LOGIN" != "true" ]]; then
  echo "=== ghcr login (optional but recommended for private images) ==="
  if [[ -z "$GHCR_USER" ]]; then
    echo "Skipping GHCR login: --ghcr-user not provided"
  else
    GHCR_TOKEN_VALUE="${!GHCR_TOKEN_ENV:-}"
    if [[ -z "$GHCR_TOKEN_VALUE" ]]; then
      echo "Skipping GHCR login: env var $GHCR_TOKEN_ENV is empty"
    else
      ssh "${SSH_OPTS[@]}" "$REMOTE" "set -euo pipefail; echo '$GHCR_TOKEN_VALUE' | docker login ghcr.io -u '$GHCR_USER' --password-stdin >/dev/null && echo 'ghcr login: ok'"
    fi
  fi
fi

if [[ "$SKIP_SECRETS" != "true" ]]; then
  echo "=== create/update required secrets ==="

  # shellcheck disable=SC1090
  source "$SECRETS_FILE"

  required_vars=(
    DYDX_BOT_DB_PASSWORD
    DYDX_DB_PASSWORD
    DYDX_POSTGRES_PASSWORD
    DYDX_REDIS_PASSWORD
    DYDX_JWT_SECRET_KEY
    DYDX_SECRET_KEY
    DYDX_ENCRYPTION_KEY
    DYDX_BOT_API_TOKEN
  )

  for var in "${required_vars[@]}"; do
    if [[ -z "${!var:-}" ]]; then
      echo "Missing required secret variable in $SECRETS_FILE: $var" >&2
      exit 1
    fi
  done

  # Derive HA infra secret values unless explicit overrides are provided.
  PG_SU_PASSWORD="${PG_SU_PASSWORD:-$DYDX_POSTGRES_PASSWORD}"
  PG_APP_PASSWORD="${PG_APP_PASSWORD:-$DYDX_POSTGRES_PASSWORD}"
  PG_REPMGR_PASSWORD="${PG_REPMGR_PASSWORD:-$DYDX_POSTGRES_PASSWORD}"
  PGPOOL_ADMIN_PASSWORD="${PGPOOL_ADMIN_PASSWORD:-$DYDX_POSTGRES_PASSWORD}"
  REDIS_PASSWORD="${REDIS_PASSWORD:-$DYDX_REDIS_PASSWORD}"

  upsert_secret() {
    local secret_name="$1"
    local secret_value="$2"

    ssh "${SSH_OPTS[@]}" "$REMOTE" "set -euo pipefail; docker secret rm '$secret_name' >/dev/null 2>&1 || true"
    ssh "${SSH_OPTS[@]}" "$REMOTE" "set -euo pipefail; printf '%s' '$secret_value' | docker secret create '$secret_name' - >/dev/null"
    echo "secret upserted: $secret_name"
  }

  upsert_secret "dydx-bot-db-password" "$DYDX_BOT_DB_PASSWORD"
  upsert_secret "dydx-db-password" "$DYDX_DB_PASSWORD"
  upsert_secret "dydx-postgres-password" "$DYDX_POSTGRES_PASSWORD"
  upsert_secret "dydx-redis-password" "$DYDX_REDIS_PASSWORD"
  upsert_secret "dydx-jwt-secret-key" "$DYDX_JWT_SECRET_KEY"
  upsert_secret "dydx-secret-key" "$DYDX_SECRET_KEY"
  upsert_secret "dydx-encryption-key" "$DYDX_ENCRYPTION_KEY"
  upsert_secret "dydx-bot-api-token" "$DYDX_BOT_API_TOKEN"

  # HA infra secrets required by swarm/stack-postgres-ha.yml and swarm/stack-redis-ha.yml
  upsert_secret "pg_su_password" "$PG_SU_PASSWORD"
  upsert_secret "pg_app_password" "$PG_APP_PASSWORD"
  upsert_secret "pg_repmgr_password" "$PG_REPMGR_PASSWORD"
  upsert_secret "pgpool_admin_password" "$PGPOOL_ADMIN_PASSWORD"
  upsert_secret "redis_password" "$REDIS_PASSWORD"
fi

echo "=== quick verification ==="
ssh "${SSH_OPTS[@]}" "$REMOTE" "set -euo pipefail; docker network ls --format '{{.Name}}' | grep -E '^(internal|public)$'"
ssh "${SSH_OPTS[@]}" "$REMOTE" "set -euo pipefail; docker secret ls --format '{{.Name}}' | grep -E '^(dydx-bot-db-password|dydx-db-password|dydx-postgres-password|dydx-redis-password|dydx-jwt-secret-key|dydx-secret-key|dydx-encryption-key|dydx-bot-api-token|pg_su_password|pg_app_password|pg_repmgr_password|pgpool_admin_password|redis_password)$' || true"

echo "Bootstrap complete. You can now rerun:"
echo "  ./scripts/deploy_production_swarmctl.sh --env production --dry-run false --deploy-infra false --deploy-apps true"
