#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${HOME}/.local/bin"
AGE_CONFIG_DIR="${HOME}/.config/sops/age"
AGE_KEY_FILE="${AGE_CONFIG_DIR}/keys.txt"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOPS_CONFIG_PATH="${REPO_ROOT}/.sops.yaml"
SOPS_TEMPLATE_PATH="${REPO_ROOT}/config/.sops.example.yaml"
mkdir -p "${INSTALL_DIR}"

detect_arch() {
  local arch
  arch="$(uname -m)"
  case "${arch}" in
    x86_64|amd64) echo "amd64" ;;
    aarch64|arm64) echo "arm64" ;;
    armv7l) echo "armv7" ;;
    *)
      echo "Unsupported architecture: ${arch}" >&2
      exit 1
      ;;
  esac
}

install_with_brew() {
  brew install sops age
}

resolve_bin() {
  local name="${1}"
  if [ -x "${INSTALL_DIR}/${name}" ]; then
    echo "${INSTALL_DIR}/${name}"
    return 0
  fi
  command -v "${name}"
}

install_linux_binary() {
  local arch="${1}"
  local sops_version="v3.9.4"
  local age_version="v1.2.1"
  local sops_url="https://github.com/getsops/sops/releases/download/${sops_version}/sops-${sops_version}.linux.${arch}"
  local age_url="https://github.com/FiloSottile/age/releases/download/${age_version}/age-${age_version}-linux-${arch}.tar.gz"
  local tmp_dir
  tmp_dir="$(mktemp -d)"

  echo "Installing sops to ${INSTALL_DIR}"
  curl -fsSL "${sops_url}" -o "${tmp_dir}/sops"
  install -m 0755 "${tmp_dir}/sops" "${INSTALL_DIR}/sops"

  echo "Installing age to ${INSTALL_DIR}"
  curl -fsSL "${age_url}" -o "${tmp_dir}/age.tar.gz"
  tar -xzf "${tmp_dir}/age.tar.gz" -C "${tmp_dir}"
  install -m 0755 "${tmp_dir}"/age/age "${INSTALL_DIR}/age"
  install -m 0755 "${tmp_dir}"/age/age-keygen "${INSTALL_DIR}/age-keygen"

  rm -rf "${tmp_dir}"
}

install_macos_binary() {
  local arch="${1}"
  local sops_version="v3.9.4"
  local age_version="v1.2.1"
  local sops_url="https://github.com/getsops/sops/releases/download/${sops_version}/sops-${sops_version}.darwin.${arch}"
  local age_url="https://github.com/FiloSottile/age/releases/download/${age_version}/age-${age_version}-darwin-${arch}.tar.gz"
  local tmp_dir
  tmp_dir="$(mktemp -d)"

  echo "Installing sops to ${INSTALL_DIR}"
  curl -fsSL "${sops_url}" -o "${tmp_dir}/sops"
  install -m 0755 "${tmp_dir}/sops" "${INSTALL_DIR}/sops"

  echo "Installing age to ${INSTALL_DIR}"
  curl -fsSL "${age_url}" -o "${tmp_dir}/age.tar.gz"
  tar -xzf "${tmp_dir}/age.tar.gz" -C "${tmp_dir}"
  install -m 0755 "${tmp_dir}"/age/age "${INSTALL_DIR}/age"
  install -m 0755 "${tmp_dir}"/age/age-keygen "${INSTALL_DIR}/age-keygen"

  rm -rf "${tmp_dir}"
}

ensure_age_key() {
  local age_keygen_bin
  local public_key

  mkdir -p "${AGE_CONFIG_DIR}"
  age_keygen_bin="$(resolve_bin age-keygen)"

  if [ ! -f "${AGE_KEY_FILE}" ]; then
    echo "Generating age identity at ${AGE_KEY_FILE}"
    public_key="$("${age_keygen_bin}" -o "${AGE_KEY_FILE}" 2>&1 | awk '/Public key:/ {print $3}')"
  else
    public_key="$("${age_keygen_bin}" -y "${AGE_KEY_FILE}" | head -n 1)"
  fi

  chmod 600 "${AGE_KEY_FILE}"

  echo
  echo "Age identity ready: ${AGE_KEY_FILE}"
  echo "Age public recipient: ${public_key}"

  if [ ! -f "${SOPS_CONFIG_PATH}" ] && [ -f "${SOPS_TEMPLATE_PATH}" ] && [ -n "${public_key}" ]; then
    cat > "${SOPS_CONFIG_PATH}" <<EOF
creation_rules:
  - path_regex: config/secrets/.*\\.secrets\\.sops\\.json\$
    age: ${public_key}
EOF
    echo "Created ${SOPS_CONFIG_PATH} from the template."
  elif [ -f "${SOPS_CONFIG_PATH}" ]; then
    echo "${SOPS_CONFIG_PATH} already exists; left unchanged."
  fi
}

case "$(uname -s)" in
  Darwin)
    if command -v brew >/dev/null 2>&1; then
      install_with_brew
    else
      install_macos_binary "$(detect_arch)"
    fi
    ;;
  Linux)
    install_linux_binary "$(detect_arch)"
    ;;
  *)
    echo "Unsupported OS for automated install. Install sops and age manually." >&2
    exit 1
    ;;
esac

ensure_age_key

echo
echo "Installed tools. Ensure ${INSTALL_DIR} is in your PATH."
echo "Recommended next step:"
echo "  make dev-config"
