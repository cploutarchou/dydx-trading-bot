---
description: "Run the canonical validation gates for the whole monorepo (or an optional scope: bot, backend, frontend, docs, infra)"
argument-hint: "[scope]"
skills: monorepo-architecture
---

Run the repository's canonical validation for the requested scope, or for
all scopes when no argument is given: $ARGUMENTS

Use the validation matrix in the monorepo-map reference (loaded via the
monorepo-architecture skill). For each scope in scope:

- bot: pytest gate with coverage floor, isort/Black/flake8, mypy
- backend: go build/vet, go test -race
- frontend: lint, typecheck, contract tests, build
- docs: make docs-governance
- infra: compose config validation + k8s secret scan

Rules: run the real commands and quote their exact results; never report a
pass you did not observe; if a gate cannot run locally, say why and the
residual risk. Finish with a per-scope table (command, result) and the
overall verdict.
