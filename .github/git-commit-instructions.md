# Git commit & branch guidelines for this repository

This file explains how to write clear git commits, name branches, and prepare PRs for the dYdX Trading Bot project. Follow this to keep history readable and PRs reviewable.

---

## Why this matters

- Small, well-scoped commits are easier to review and revert.
- A consistent commit format makes changelogs and automated tooling predictable.
- Branch naming and PR hygiene speed up reviews and CI checks.

---

## Commit message format (recommended)

We follow the Conventional Commits-style, with a short header and optional body and footer.

Format:

```
<type>(<scope>): <short summary>

<body - optional, wrap at 72 chars>

<footer - optional: BREAKING CHANGE: explanation or references like Closes #123>
```

- type: feat, fix, docs, style, refactor, perf, test, chore, ci, build, revert
- scope: a module or file group (optional). Example: `app`, `backend`, `config`
- short summary: 50 characters or less, imperative mood ("Add" not "Added")

Examples:

```
feat(app): add strategy_params support to BacktestEngine

Allow backtests to override config values using the new
`strategy_params` dict. This enables quick A/B testing without
editing `app/config.yaml`.

Closes #432
```

```
fix(func_bot_agent): emergency close first side when second fails

Ensure atomicity: if market_2 order fails, place a reduce-only
order to close market_1 immediately and mark the pair as FAILED.
```

```
docs: add python-trading.instructions.md with contributor rules
```

---

## Commit body guidance

- Use the body to explain *why* the change was made and any non-obvious implementation choices.
- Mention any tradeoffs, regressions, or follow-ups required.
- Reference issue numbers using `Closes #123` or `Fixes #123` where appropriate.

---

## Branch naming

Use short, descriptive branch names. Include ticket/issue IDs if available.

Patterns:

- feature/ISSUE-123-add-backtest-params
- fix/ISSUE-456-handle-order-failure
- chore/update-deps
- test/add-backtest-unit-tests

Avoid long or generic branch names like `changes` or `work`.

---

## Before committing (local checklist)

1. Run tests related to your changes (fast smoke tests first):

```bash
make test  # or run targeted pytest for changed modules
```

2. Run formatters & linters:

```bash
make format
make lint
```

3. Run type checks if applicable (mypy). If the project uses them:

```bash
# if configured
mypy .
```

4. Verify you didn't commit secrets or credentials.

5. Ensure you updated `app/constants.py` (or other constants) when you added a config parameter, and include that in the commit.

6. Add tests for new behavior; if you changed behavior, update relevant tests.

---

## Commands and workflows (common tasks)

Stage interactively (recommended for tidy commits):

```bash
git add -p   # stage hunks interactively
git status
```

Create commit (single-line header only):

```bash
git commit -m "fix(app): correct timezone usage in backtest timestamps"
```

Create commit with full editor/body (recommended for descriptive commits):

```bash
git commit
# This opens your editor; write header, blank line, body, and footer.
```

Amend last commit (when you forgot to include something or want to reword):

```bash
git add <missing-files>
git commit --amend --no-edit   # to add files without changing message
# or
git commit --amend             # to edit the message
```

Interactive rebase to squash or reorder commits before pushing a feature branch:

```bash
# Rebase the last N commits (e.g., 5) to squash or edit messages
git rebase -i HEAD~5
# After resolving, force push the branch
git push --force-with-lease origin your-branch
```

Create a new branch and push:

```bash
git checkout -b feature/ISSUE-123-short-desc
git push --set-upstream origin feature/ISSUE-123-short-desc
```

If you need to discard local changes:

```bash
git restore <file>  # restore a file
git restore --staged <file>  # unstage a file
git reset --hard    # WARNING: discards all local changes
```

---

## Pull Request guidance

- Use the commit summary as the PR title or a concise variant.
- In the PR description, include:
  - What the change does
  - Why it's needed
  - Files changed (high level)
  - Tests added/updated
  - Any runtime steps to verify (smoke tests)
- Link related issues (e.g., Closes #123).
- Add reviewers and set labels (feature, bug, docs) as appropriate.

Recommended merge strategy: prefer squash-and-merge for feature branches (keeps history linear and forces a single cohesive commit). If your repo or team prefers preserving commit history, follow that project's merge policy.

---

## Special notes for this project

When your change touches configuration or trading logic, double-check these items are included in the commit/PR:

- If you added a new config parameter:
  - Edit `app/config.yaml` (user-facing option)
  - Add to `app/config.py` dataclass (type-safe field)
  - Export in `app/constants.py` (importable constant)
  - Update any docs (README or instructions file)

- If you modified persistence or state formats (eg. `cointegrated_pairs.json` or `bot_agents.json`):
  - Add a migration or backward-compatible parsing logic
  - Update `app/models/pair_storage.py` if necessary

- If your change affects backtesting logic or results:
  - Add/adjust unit tests in `tests/` covering the logic
  - Run a small backtest to validate changes (optional, but recommended):

```bash
python scripts/run_backtest.py --start 2024-09-01 --end 2024-09-30 --pairs 3
```

- Do not commit secrets, credentials, or private keys. If a secret was accidentally committed, follow the repo incident procedure in `README.md`.

---

## Commit message examples oriented to this repo

- Feature adding strategy params:

```
feat(backtesting): support strategy_params override in BacktestEngine

This allows backtests to be parameterized without editing config.yaml.
Closes #789
```

- Fix atomic execution in BotAgent:

```
fix(func_bot_agent): emergency-close m1 if m2 fails

Ensure we do not leave orphaned positions when the second order fails.
```

- Docs only change:

```
docs: add git commit instructions and contribution checklist
```

---

## Final pre-push checklist

- [ ] Tests relevant to changes pass locally
- [ ] Code formatted and linted
- [ ] Commit message follows format and references issues if applicable
- [ ] No secrets in commits
- [ ] Branch name follows naming convention

---

If you'd like, I can also create a lightweight git commit hook stub (pre-commit) to validate commit messages or enforce formatting; tell me if you prefer a Conventional Commit validator or a commitizen setup and I'll add it.

