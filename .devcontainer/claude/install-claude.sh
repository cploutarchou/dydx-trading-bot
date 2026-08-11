#!/usr/bin/env bash
# Install official Claude Code (Anthropic) inside the dev container.
# Pure Claude only — no third-party providers. Auth via `claude` login or ANTHROPIC_API_KEY.
set -euo pipefail

export NVM_DIR="${NVM_DIR:-/usr/local/share/nvm}"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  # shellcheck disable=SC1090
  . "$NVM_DIR/nvm.sh"
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "install-claude: npm not found; ensure the Node devcontainer feature is enabled" >&2
  exit 1
fi

# Install / refresh official Claude Code CLI
npm install -g @anthropic-ai/claude-code

USER_HOME="${_REMOTE_USER_HOME:-${HOME:-/home/vscode}}"
mkdir -p "$USER_HOME/.claude" "$USER_HOME/.local/bin"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Pure Anthropic settings only (no custom base URL / third-party provider).
if [ -f "$SCRIPT_DIR/settings.json" ]; then
  cp "$SCRIPT_DIR/settings.json" "$USER_HOME/.claude/settings.json"
fi

# Drop obsolete third-party provider helpers if present.
rm -f "$USER_HOME/.claude/load-local-env.sh"
rm -f "$SCRIPT_DIR/load-local-env.sh"

# Thin wrapper so `claude` resolves via nvm/npm global install.
cat > "$USER_HOME/.local/bin/claude" <<'WRAP'
#!/usr/bin/env bash
set -euo pipefail
export NVM_DIR="${NVM_DIR:-/usr/local/share/nvm}"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

REAL=""
if command -v nvm >/dev/null 2>&1; then
  ver="$(nvm version default 2>/dev/null || nvm version current 2>/dev/null || true)"
  if [ -n "$ver" ] && [ -x "$NVM_DIR/versions/node/$ver/bin/claude" ]; then
    REAL="$NVM_DIR/versions/node/$ver/bin/claude"
  fi
fi
if [ -z "$REAL" ]; then
  REAL="$(find "$NVM_DIR/versions/node" -path '*/bin/claude' 2>/dev/null | sort -V | tail -1 || true)"
fi
if [ -z "$REAL" ] && command -v npm >/dev/null 2>&1; then
  prefix="$(npm prefix -g 2>/dev/null || true)"
  if [ -n "$prefix" ] && [ -x "$prefix/bin/claude" ]; then
    REAL="$prefix/bin/claude"
  fi
fi
if [ -z "$REAL" ] && [ -x /usr/local/bin/claude ]; then
  REAL=/usr/local/bin/claude
fi
if [ -z "$REAL" ]; then
  echo "claude: not installed. Run: npm install -g @anthropic-ai/claude-code" >&2
  exit 127
fi
exec "$REAL" "$@"
WRAP
chmod +x "$USER_HOME/.local/bin/claude"

BASHRC="$USER_HOME/.bashrc"
if [ -f "$BASHRC" ]; then
  # Remove obsolete third-party provider / custom loader lines if present.
  if grep -qE 'load-local-env\.sh|ANTHROPIC_BASE_URL' "$BASHRC" 2>/dev/null; then
    tmp="$(mktemp)"
    grep -vE 'load-local-env\.sh|ANTHROPIC_BASE_URL' "$BASHRC" >"$tmp" || true
    mv "$tmp" "$BASHRC"
  fi
  if ! grep -q 'NVM_DIR=.*nvm' "$BASHRC" 2>/dev/null; then
    cat >>"$BASHRC" <<'RC'

# nvm (Node) — used by Claude Code
export NVM_DIR="/usr/local/share/nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && . "$NVM_DIR/bash_completion"
RC
  fi
  if ! grep -q '\.local/bin' "$BASHRC" 2>/dev/null; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >>"$BASHRC"
  fi
fi

# Reset settings if a custom Anthropic base URL was previously configured.
if [ -f "$USER_HOME/.claude/settings.json" ] && grep -qE 'ANTHROPIC_BASE_URL' "$USER_HOME/.claude/settings.json" 2>/dev/null; then
  cp "$SCRIPT_DIR/settings.json" "$USER_HOME/.claude/settings.json"
fi

echo "install-claude: Claude Code ready (official Anthropic / pure Claude)"
export PATH="$USER_HOME/.local/bin:${PATH:-}"
if command -v claude >/dev/null 2>&1; then
  claude --version || true
else
  echo "install-claude: claude binary not on PATH yet; open a new shell after Node feature install"
fi

if [ -n "${ANTHROPIC_API_KEY:-}${ANTHROPIC_AUTH_TOKEN:-}" ]; then
  echo "install-claude: Anthropic API credentials detected in environment"
else
  echo "install-claude: no ANTHROPIC_API_KEY in env — run \`claude\` and sign in, or set ANTHROPIC_API_KEY on the host"
fi
