---
name: light-mode-theme-fintech
description: 'Apply consistent premium light-theme fintech design in React/Tailwind/CSS surfaces. Use when fixing contrast, surface depth, control legibility, or color semantics for operator-grade pages in day/light mode.'
argument-hint: 'Describe the page, component, or surface that needs light-mode styling work.'
user-invocable: true
disable-model-invocation: false
---

# Light Mode Theme Fintech

Use this skill to ensure light-mode UI is as polished and premium as the dark theme.
Light mode is a first-class design target — it must have visual depth, contrast hierarchy, and legible controls.

---

## 1. Design Philosophy

Light mode must feel **intentional, layered, and confident** — not bleached or flat.  
Key reference: Apple's light mode, Linear app, Vercel dashboard, Stripe dashboard.

Target aesthetic for this codebase:

- Cool-white page base with subtle blue-gray tint
- Glass-effect cards with layered gradients + inset highlights
- Clear typographic hierarchy: `#020617` heading → `#0f172a` body → `#334155` secondary → `#64748b` muted
- Crisp borders at `rgba(100, 116, 139, 0.32–0.44)` depending on surface elevation
- Soft but present shadows: `0 12px 30px rgba(15,23,42,0.10–0.16)` with `inset 0 1px 0 rgba(255,255,255,0.95)`

---

## 2. CSS Token Reference

### Page & Shell

```css
/* Page background */
background: linear-gradient(135deg, #ffffff, #f6f8fb 54%, #eef2f7);

/* Sidebar */
background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(241, 245, 249, 0.98));
```

### Surface Elevation Tiers

```css
/* Tier 1 — Base card (e.g., metric-tile, signal-card) */
background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.92));
border: 1px solid rgba(100, 116, 139, 0.34);
box-shadow:
  inset 0 1px 0 rgba(255, 255, 255, 0.96),
  0 12px 28px rgba(15, 23, 42, 0.1);

/* Tier 2 — Panel (e.g., operator-section-card, platform-panel) */
background: linear-gradient(180deg, rgba(255, 255, 255, 0.97), rgba(241, 245, 249, 0.9));
border: 1px solid rgba(100, 116, 139, 0.36);
box-shadow:
  inset 0 1px 0 rgba(255, 255, 255, 0.96),
  0 20px 44px rgba(15, 23, 42, 0.11);

/* Tier 3 — Modal / overlay */
background: rgba(255, 255, 255, 0.98);
border: 1px solid rgba(100, 116, 139, 0.38);
box-shadow:
  inset 0 1px 0 rgba(255, 255, 255, 0.98),
  0 28px 60px rgba(15, 23, 42, 0.14);
```

### Typography Scale

```css
h1, h2, h3, strong (primary):   color: #020617
body, p (body):                  color: #0f172a
secondary text:                  color: #334155
muted / labels:                  color: #475569
placeholder / faint:             color: #94a3b8
```

### Financial Color Semantics (Light)

```css
/* Profit / positive */
text: #047857;     border: rgba(5,150,105,0.30);    bg: rgba(236,253,245,0.90)

/* Loss / danger */
text: #be123c;     border: rgba(225,29,72,0.30);     bg: rgba(255,241,242,0.90)

/* Info / accent (cyan) */
text: #0369a1;     border: rgba(14,116,144,0.30);    bg: rgba(240,249,255,0.90)

/* Warning / amber */
text: #b45309;     border: rgba(217,119,6,0.30);     bg: rgba(255,251,235,0.90)

/* Violet */
text: #4c1d95;     border: rgba(109,40,217,0.28);    bg: rgba(245,243,255,0.90)
```

### Controls

```css
/* Input */
background: rgba(255, 255, 255, 0.95);
border: rgba(100, 116, 139, 0.38);
color: #0f172a;
box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72);

/* Primary button */
background: linear-gradient(135deg, #075985, #0284c7 58%, #6d28d9);
color: #ffffff;

/* Secondary button */
background: rgba(255, 255, 255, 0.92);
border: rgba(100, 116, 139, 0.38);
color: #1e293b;
box-shadow:
  inset 0 1px 0 rgba(255, 255, 255, 0.72),
  0 8px 18px rgba(15, 23, 42, 0.08);
```

---

## 3. Contrast Acceptance Criteria

Before signing off on any surface:

| Layer        | Minimum WCAG ratio | Target hex |
| ------------ | ------------------ | ---------- |
| Heading      | 10:1+              | `#020617`  |
| Body copy    | 7:1+               | `#0f172a`  |
| Secondary    | 5:1+               | `#334155`  |
| Muted labels | 4.5:1+             | `#475569`  |
| Placeholder  | 3:1+               | `#94a3b8`  |

Test by forcing `data-theme="light"` in the browser and sampling computed `color` with DevTools.

---

## 4. Common Failures to Fix

| Symptom                  | Root Cause                           | Fix                                       |
| ------------------------ | ------------------------------------ | ----------------------------------------- |
| White text on white card | Tailwind `text-white` not overridden | Scope under `[data-theme='light'] .class` |
| Flat/washed card         | No gradient or shadow                | Add tier-appropriate gradient + shadow    |
| Cyan text unreadable     | `text-cyan-200` on white bg          | Override to `#0369a1`                     |
| Green text invisible     | `text-emerald-200/70` on light       | Override to `#047857`                     |
| No card depth            | All cards same white                 | Use elevation tier distinction            |

---

## 5. Required Validation Checklist

After any light-mode change:

- [ ] Verified with `document.documentElement.setAttribute('data-theme','light')` in browser
- [ ] Sampled `color`, `backgroundImage`, `borderColor`, `boxShadow` via `getComputedStyle`
- [ ] Heading/body/muted contrast is visually distinguishable
- [ ] No Tailwind utility overrides bleeding into dark theme
- [ ] `npm run lint` passes with zero new errors
- [ ] Dark mode renders correctly (untouched)
