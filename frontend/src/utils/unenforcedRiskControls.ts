/**
 * Risk limits the live runtime cannot enforce yet.
 *
 * The runtime refuses to start while one of these is set above zero, so an
 * operator is never shown a protection that is not real. Only the fields named
 * here can be turned off from the UI; anything else the backend reports stays a
 * plain blocker that the operator cannot acknowledge away.
 */

import type { UnenforcedRiskControl } from '../api';

const RESOLVABLE_RISK_CONTROL_LABELS = new Map<string, string>([
  ['max_drawdown_pct', 'Max drawdown'],
  ['trailing_stop_pct', 'Trailing stop'],
]);

export const isResolvableRiskControl = (field: string): boolean =>
  RESOLVABLE_RISK_CONTROL_LABELS.has(field);

/** Friendly label for a known field, otherwise the raw field name. */
export const riskControlLabel = (field: string): string =>
  RESOLVABLE_RISK_CONTROL_LABELS.get(field) ?? field;

/** `15%`, `2.25%` — the configured value without padded decimals. */
export const formatRiskControlValue = (value: number): string =>
  Number.isFinite(value) ? `${Number(value.toFixed(2))}%` : '—';

/**
 * Reads `unenforced_risk_controls` from a readiness payload. Tolerates a missing
 * field (older backend) and malformed rows, and keeps one row per field.
 */
export const normalizeUnenforcedRiskControls = (value: unknown): UnenforcedRiskControl[] => {
  if (!Array.isArray(value)) {
    return [];
  }

  const seen = new Set<string>();
  const controls: UnenforcedRiskControl[] = [];
  value.forEach((entry) => {
    if (typeof entry !== 'object' || entry === null) {
      return;
    }
    const record = entry as Record<string, unknown>;
    const field = typeof record.field === 'string' ? record.field.trim() : '';
    if (!field || seen.has(field)) {
      return;
    }
    seen.add(field);
    controls.push({
      field,
      value: Number(record.value),
      message: typeof record.message === 'string' ? record.message.trim() : '',
    });
  });
  return controls;
};

export const splitUnenforcedRiskControls = (
  controls: UnenforcedRiskControl[]
): { resolvable: UnenforcedRiskControl[]; unresolvable: UnenforcedRiskControl[] } => ({
  resolvable: controls.filter((control) => isResolvableRiskControl(control.field)),
  unresolvable: controls.filter((control) => !isResolvableRiskControl(control.field)),
});

/**
 * Drops blocker lines that only repeat a control's own message, so a screen
 * that renders the controls notice does not list the same sentence twice.
 */
export const excludeRiskControlBlockers = (
  blockers: unknown,
  controls: UnenforcedRiskControl[]
): string[] => {
  if (!Array.isArray(blockers)) {
    return [];
  }
  const controlMessages = new Set(
    controls.map((control) => control.message.trim()).filter((message) => message.length > 0)
  );
  return blockers.filter(
    (blocker): blocker is string =>
      typeof blocker === 'string' &&
      blocker.trim().length > 0 &&
      !controlMessages.has(blocker.trim())
  );
};
