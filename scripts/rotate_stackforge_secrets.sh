#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-.env.stackforge}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Env file not found: ${ENV_FILE}" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required" >&2
  exit 1
fi

timestamp="$(date +%Y%m%d%H%M%S)"
backup="${ENV_FILE}.bak.${timestamp}"
cp "${ENV_FILE}" "${backup}"

python3 - <<'PY' "${ENV_FILE}"
import base64
import secrets
import string
import sys
from pathlib import Path

env_path = Path(sys.argv[1])
lines = env_path.read_text(encoding="utf-8").splitlines()

def rand_urlsafe(nbytes: int = 48) -> str:
	raw = base64.urlsafe_b64encode(secrets.token_bytes(nbytes)).decode("utf-8")
	return raw.rstrip("=")

alphabet = string.ascii_letters + string.digits + "-_"

def rand_password(length: int = 40) -> str:
	return "".join(secrets.choice(alphabet) for _ in range(length))

rotations = {
	"SECRET_KEY": rand_urlsafe(48),
	"JWT_SECRET_KEY": rand_urlsafe(48),
	"ENCRYPTION_KEY": rand_urlsafe(48),
	"APP_DB_PASSWORD": rand_password(40),
	"APP_DB_ROOT_PASSWORD": rand_password(40),
	"BOT_DB_PASSWORD": rand_password(40),
	"BOT_DB_ROOT_PASSWORD": rand_password(40),
}

# Provider-managed tokens/usernames must be replaced manually with real values.
manual_refresh = {
	"GITHUB_API_TOKEN": "REPLACE_ME_GITHUB_TOKEN",
	"GHCR_USERNAME": "REPLACE_ME_GHCR_USERNAME",
	"GHCR_TOKEN": "REPLACE_ME_GHCR_TOKEN",
	"DOCKERHUB_USERNAME": "REPLACE_ME_DOCKERHUB_USERNAME",
	"DOCKERHUB_TOKEN": "REPLACE_ME_DOCKERHUB_TOKEN",
	"DOCKER_REGISTRY": "REPLACE_ME_DOCKER_REGISTRY",
	"DOCKER_REGISTRY_USERNAME": "REPLACE_ME_DOCKER_REGISTRY_USERNAME",
	"DOCKER_REGISTRY_PASSWORD": "REPLACE_ME_DOCKER_REGISTRY_PASSWORD",
	"CLOUDFLARE_API_TOKEN": "REPLACE_ME_CLOUDFLARE_API_TOKEN",
}

idx = {}
for i, line in enumerate(lines):
	stripped = line.strip()
	if not stripped or stripped.startswith("#") or "=" not in line:
		continue
	key = line.split("=", 1)[0].strip()
	idx[key] = i

for key, value in rotations.items():
	if key in idx:
		lines[idx[key]] = f"{key}={value}"
	else:
		lines.append(f"{key}={value}")

for key, value in manual_refresh.items():
	if key in idx:
		lines[idx[key]] = f"{key}={value}"
	else:
		lines.append(f"{key}={value}")

env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def mask(v: str) -> str:
	if len(v) <= 10:
		return "*" * len(v)
	return f"{v[:4]}...{v[-4:]}"

print("Rotated keys:")
for k in [
	"SECRET_KEY",
	"JWT_SECRET_KEY",
	"ENCRYPTION_KEY",
	"APP_DB_PASSWORD",
	"APP_DB_ROOT_PASSWORD",
	"BOT_DB_PASSWORD",
	"BOT_DB_ROOT_PASSWORD",
]:
	print(f"- {k}={mask(rotations[k])}")

print("\nSet manual values before deploy:")
for k in [
	"GITHUB_API_TOKEN",
	"GHCR_USERNAME",
	"GHCR_TOKEN",
	"DOCKERHUB_USERNAME",
	"DOCKERHUB_TOKEN",
	"DOCKER_REGISTRY",
	"DOCKER_REGISTRY_USERNAME",
	"DOCKER_REGISTRY_PASSWORD",
	"CLOUDFLARE_API_TOKEN",
]:
	print(f"- {k}={manual_refresh[k]}")
PY

echo "Backup written to: ${backup}"
echo "Updated: ${ENV_FILE}"
