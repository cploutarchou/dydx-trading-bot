#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KEY_FILE="${REPO_ROOT}/.configkey.bin"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required for the repo-owned config workflow." >&2
  exit 1
fi

if ! python3 - <<'PY' >/dev/null 2>&1
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
print(AESGCM)
PY
then
  echo "python3 'cryptography' is required for encrypted config handling." >&2
  echo "Install it in the environment that runs the monorepo tooling, then retry." >&2
  exit 1
fi

if [ -f "${KEY_FILE}" ]; then
  echo "Config key already exists at ${KEY_FILE}"
  echo "Shareable token:"
  python3 "${REPO_ROOT}/scripts/secure_config.py" show-token
  exit 0
fi

echo "Creating repo config key at ${KEY_FILE}"
python3 "${REPO_ROOT}/scripts/secure_config.py" keygen
echo
echo "Next steps:"
echo "  make dev-config"
echo "  make dev"
