---
agent: 'Senior DeFi Monorepo Platform'
name: codex-deepseek-usage-optimizer
description: "Audit and improve how this monorepo uses DeepSeek models (quality, reliability, and cost) and where needed upgrade full UX/UI user experience using AI-driven recommendations, then produce concrete, repo-specific implementation steps or patches."
argument-hint: "Paste target scope (files/services), current pain points, and any latency/cost/quality goals."
---

Use this command when you want production-grade improvements to DeepSeek usage in this repo.

## Mission

Given the target scope, identify the highest-impact DeepSeek integration improvements and return concrete implementation guidance (or code edits if requested) for:

- response quality,
- latency/reliability,
- token/cost efficiency,
- operational safety,
- full UX/UI user experience quality where needed (clarity, usability, accessibility, responsiveness, and workflow friction reduction).

## Inputs to collect

- Scope: `bot`, `backend`, `frontend`, or cross-service
- Current integration style: OpenAI-format vs Anthropic-format calls
- Key pain points: low answer quality, high latency, high token spend, flaky tool calls, JSON parse failures, 429s, etc.
- UX/UI pain points: confusing flows, noisy dashboards, poor hierarchy, weak states/loading/errors, accessibility issues, mobile/responsive gaps
- Constraints: production safety, deadline, acceptable risk, max complexity

If inputs are missing, infer conservatively from code and call this out.

## DeepSeek-focused checklist (required)

### 1) Model & mode selection

- Use `deepseek-v4-pro` for hardest reasoning and critical orchestration logic.
- Use `deepseek-v4-flash` for faster/cheaper paths where quality remains acceptable.
- Prefer `deepseek-v4-*` names over deprecated aliases (`deepseek-chat`, `deepseek-reasoner`).
- For thinking mode, set `thinking.type` and `reasoning_effort` intentionally (`high` vs `max`).

### 2) Tool-calling correctness

- Validate `tools` schema and argument parsing paths.
- If thinking mode + tool calls are used, ensure `reasoning_content` is preserved and passed back on subsequent turns; otherwise note potential 400 risk.
- For strict tool contracts, consider Beta strict mode requirements (`/beta`, `strict: true`, valid JSON Schema subset).

### 3) Structured output robustness

- For machine parsing, enforce JSON output (`response_format: {"type":"json_object"}`) and include explicit JSON instructions/examples in prompts.
- Add graceful fallback when empty JSON content is returned.
- Ensure truncation safety with sensible `max_tokens`.

### 4) Cost & cache efficiency

- Improve prompt prefix reuse to increase context-cache hits.
- Track `usage.prompt_cache_hit_tokens` and `usage.prompt_cache_miss_tokens` where available.
- Recommend model-routing and prompt-shaping changes that reduce cost without harming task quality.

### 5) Reliability & rate limits

- Handle HTTP 429 with exponential backoff + jitter and bounded retries.
- Ensure streaming/non-streaming keep-alive handling does not break parsers.
- Add timeout/cancellation strategy and clear error classification.

### 6) Repo fit (dYdX monorepo)

- Respect architecture boundary: `frontend -> backend -> bot`.
- Keep trading safety first: no changes that weaken atomic paired execution safeguards.
- Prefer small, testable changes with verification steps.

### 7) UX/UI improvement pass (required when frontend or user-facing flow is in scope)

- Audit end-to-end user journeys and prioritize high-friction steps.
- Improve information hierarchy, labels, empty/loading/error states, and action affordances.
- Recommend UI updates that are measurable (task completion speed, fewer clicks, lower confusion).
- Include accessibility checks (keyboard navigation, contrast, focus order, semantic structure, screen-reader clarity).
- Ensure responsive behavior across desktop and smaller viewports.
- Prefer incremental, production-safe UX wins over broad rewrites unless explicitly requested.

## Output format (strict)

Return in this exact structure:

1. **Current Findings**
   - 3-8 bullets, each with concrete evidence (file/function/path).
2. **Top Improvements (Ranked)**
   - 3-6 items with: impact, effort, risk.
   - Include at least one UX/UI improvement whenever a user-facing surface is touched.
3. **Implementation Diffs**
   - Minimal patch plan (or exact edits if requested), grouped by file.
4. **Validation Plan**
   - Tests/checks to run, expected signals, rollback trigger.
5. **Observability Additions**
   - Metrics/logs to add (quality, latency, cache-hit rate, 429 rate, token usage).
6. **UX/UI Validation Signals**
   - Usability checks, accessibility checks, and before/after acceptance criteria for impacted screens.

## Guardrails

- Do not invent API capabilities.
- Prefer official DeepSeek-supported fields and modes.
- Do not propose architecture-breaking shortcuts.
- Do not propose UX/UI changes that reduce risk visibility for operators in trading workflows.
- Keep recommendations specific, measurable, and production-aware.
