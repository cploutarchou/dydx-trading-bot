---
agent: agent
name: codex-frontend-ux-polish
description: "Audit and improve full frontend UX/UI quality for this monorepo with concrete, production-safe implementation steps or patches (usability, accessibility, responsiveness, and operator clarity)."
argument-hint: "Paste target pages/components, user pain points, and desired UX outcomes (speed, clarity, conversion, fewer errors, etc.)."
---

Use this command when you want focused, AI-assisted UX/UI improvements in the frontend.

## Mission

Given the scope, identify the highest-impact UX/UI improvements and provide concrete implementation guidance (or code edits if requested) that improve:

- clarity and information hierarchy,
- workflow efficiency and reduced friction,
- accessibility and inclusive interaction,
- responsive behavior across screen sizes,
- confidence and safety for operator decisions.

## Inputs to collect

- Scope: pages/components/routes affected (prefer exact file paths)
- User personas: operator, analyst, admin, or mixed
- Pain points: confusing labels, too many clicks, weak loading/error states, noisy dashboards, poor mobile behavior
- Constraints: design system boundaries, time budget, risk tolerance, release urgency
- Success signals: task completion time, error rate, support tickets, interaction drop-off, user confidence feedback

If inputs are missing, infer from code and state assumptions explicitly.

## UX/UI checklist (required)

### 1) User journey and task flow

- Map the top user goals for the scoped surfaces.
- Identify friction points, dead ends, or context switching overhead.
- Reduce clicks/steps for frequent tasks without hiding critical controls.

### 2) Information hierarchy and content clarity

- Improve visual priority for key status, risk, and action elements.
- Simplify wording: labels, help text, and CTA copy.
- Remove noisy or redundant UI elements that distract from operator intent.

### 3) States and feedback quality

- Ensure excellent empty/loading/error/success states.
- Add actionable recovery guidance for failures.
- Confirm progress indicators and timestamps are trustworthy and understandable.

### 4) Accessibility and interaction quality

- Verify keyboard navigation and focus visibility/order.
- Check color contrast and semantic structure for assistive technologies.
- Improve ARIA usage where relevant and avoid interaction traps.

### 5) Responsive and layout robustness

- Validate behavior on desktop + narrower viewports.
- Preserve action discoverability in compact layouts.
- Prevent overflow, truncation ambiguity, and critical control collapse.

### 6) Trading/operator safety constraints

- Do not reduce visibility of risk, position health, or runtime warnings.
- Keep high-impact actions explicit and reversible when possible.
- Avoid deceptive default states around execution-critical operations.

## Implementation style

- Prefer small, testable improvements over broad rewrites.
- Reuse existing frontend patterns/components before introducing new primitives.
- Keep API contracts stable unless explicitly included in scope.

## Output format (strict)

Return in this exact structure:

1. **Current UX Findings**
   - 4-10 bullets with concrete evidence (file/component/interaction).
2. **Top UX/UI Improvements (Ranked)**
   - 3-7 items; each includes impact, effort, and implementation risk.
3. **Implementation Diffs**
   - Minimal patch plan (or exact edits if requested), grouped by file.
4. **Validation Plan**
   - Functional checks + accessibility checks + responsive checks.
5. **Acceptance Criteria**
   - Before/after measurable outcomes for each major change.
6. **Rollout and Safety Notes**
   - Safe rollout strategy, fallback path, and what to monitor post-release.

## Guardrails

- Do not propose UI changes that hide operational risk data.
- Keep recommendations measurable and production-aware.
- Avoid purely cosmetic suggestions unless they clearly improve usability.
- Respect architecture boundary: `frontend -> backend -> bot`.
