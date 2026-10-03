#!/usr/bin/env bash
# Run the CI quality checks locally, for the areas your branch touched.
#
# GitHub Actions bills every job by the minute, so the cheap way to find a
# failure is to find it here first. This mirrors .github/workflows/bot-quality.yml:
# the same area detection (bot / backend / frontend / docs / stack) and the same
# commands, including the lint tool versions CI pins.
#
# Usage:
#   scripts/ci_local.sh            checks for areas changed against origin/master
#   scripts/ci_local.sh --all      every area
#   scripts/ci_local.sh --base REF compare against another ref
#
# Not run here (they need service containers or a network advisory database, so
# they stay on GitHub Actions): the multi-worker broadcast test, the
# external-service integration tests, bandit, pip-audit and the image builds.
set -uo pipefail

cd "$(git rev-parse --show-toplevel)"

base="origin/master"
all=false
while [ $# -gt 0 ]; do
  case "$1" in
    --all) all=true ;;
    --base) shift; base="${1:?--base needs a ref}" ;;
    -h|--help) sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

# Keep in step with the lint job in .github/workflows/bot-quality.yml.
LINT_TOOLS=(--with black==26.5.1 --with isort==6.0.1 --with flake8==7.3.0)

if $all; then
  files=""
else
  merge_base="$(git merge-base HEAD "$base" 2>/dev/null)" || {
    echo "cannot find a merge base with $base; run 'git fetch' or use --all" >&2
    exit 2
  }
  # Committed, staged, unstaged and untracked changes all count.
  files="$( { git diff --name-only "$merge_base"; git ls-files --others --exclude-standard; } | sort -u)"
fi

touched() { $all || grep -Eq "$1" <<<"$files"; }

failed=()
ran=()
step() { # step "<label>" command...
  local label="$1"; shift
  printf '\n\033[1m==> %s\033[0m\n' "$label"
  ran+=("$label")
  if ! "$@"; then failed+=("$label"); fi
}
in_dir() { local dir="$1"; shift; (cd "$dir" && "$@"); }

if touched '^bot/'; then
  py="bot/.venv/bin/python"
  [ -x "$py" ] || { echo "missing $py; create the bot virtualenv first" >&2; exit 2; }
  if command -v uv >/dev/null; then
    step "bot: isort"  in_dir bot uv run --no-project "${LINT_TOOLS[@]}" isort --check-only --diff src tests
    step "bot: black"  in_dir bot uv run --no-project "${LINT_TOOLS[@]}" black --check --diff src tests
    step "bot: flake8" in_dir bot uv run --no-project "${LINT_TOOLS[@]}" flake8 src tests --select=E9,F63,F7,F82 --show-source
  else
    echo "uv not found: linting with the virtualenv's tool versions, which may differ from CI" >&2
    step "bot: isort"  in_dir bot .venv/bin/python -m isort --check-only --diff src tests
    step "bot: black"  in_dir bot .venv/bin/python -m black --check --diff src tests
    step "bot: flake8" in_dir bot .venv/bin/python -m flake8 src tests --select=E9,F63,F7,F82 --show-source
  fi
  step "bot: mypy"   in_dir bot .venv/bin/python -m mypy --no-color src
  step "bot: pytest" in_dir bot .venv/bin/python -m pytest tests/ -q --tb=short \
    --ignore=tests/test_api_database_integration.py --ignore=tests/test_comprehensive.py \
    --cov=src --cov-fail-under=82 -p no:cacheprovider
fi

if touched '^backend/'; then
  step "backend: build" in_dir backend go build ./...
  step "backend: vet"   in_dir backend sh -c 'go vet ./... && go vet -tags integration ./internal/routes/'
  step "backend: test"  in_dir backend go test -race -count=1 ./...
  if command -v golangci-lint >/dev/null; then
    step "backend: golangci-lint" in_dir backend golangci-lint run ./...
  else
    echo "golangci-lint not found; skipping the backend lint" >&2
  fi
fi

if touched '^frontend/'; then
  [ -d frontend/node_modules ] || step "frontend: npm ci" in_dir frontend npm ci
  step "frontend: lint"      in_dir frontend npm run lint
  step "frontend: typecheck" in_dir frontend npm run typecheck
  step "frontend: test"      in_dir frontend npm test
  step "frontend: build"     in_dir frontend npm run build
fi

if touched '^docs/|^README\.md$|^scripts/validate_docs_governance\.py$'; then
  step "docs: governance" python3 scripts/validate_docs_governance.py
fi

if touched '^docker/|^docker-compose\.[^/]*\.yml$|^backend/go\.mod$|^scripts/check_toolchain_drift\.py$|^\.github/workflows/'; then
  step "stack: toolchain drift" python3 scripts/check_toolchain_drift.py
  step "stack: infra compose"   sh -c 'docker compose -f docker-compose.infra.yml config >/dev/null'
  step "stack: stack compose"   sh -c 'docker compose -f docker-compose.stack.yml config >/dev/null'
fi

echo
if [ ${#ran[@]} -eq 0 ]; then
  echo "No checked area changed against $base; nothing to run. Use --all to run everything."
  exit 0
fi
if [ ${#failed[@]} -gt 0 ]; then
  printf '\033[31mFAILED (%d of %d):\033[0m\n' "${#failed[@]}" "${#ran[@]}"
  printf '  - %s\n' "${failed[@]}"
  exit 1
fi
printf '\033[32mAll %d checks passed.\033[0m\n' "${#ran[@]}"
