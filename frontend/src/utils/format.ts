/**
 * Shared money/number/percent formatters (audit FE-022). One source of truth
 * so every desk renders identical money strings; replaces the ~65 scattered
 * local helpers. All values are display-layer only — the backend owns decimal
 * precision for trading math.
 */

const usdFormatter = (maximumFractionDigits: number) =>
  Intl.NumberFormat('en-US', { maximumFractionDigits });

/** `$1,234.5` — absolute (unsigned) USD amount. */
export const formatUsd = (value: number, maximumFractionDigits = 2): string =>
  Number.isFinite(value)
    ? `$${usdFormatter(maximumFractionDigits).format(Math.abs(value))}`
    : '$0';

/** `▲ +$12.5` / `▼ -$4` / `$0` — signed P&L with a direction glyph so the
 *  signal survives color-blindness and grayscale (WCAG 1.4.1). Zero is neutral. */
export const formatSignedUsd = (value: number, maximumFractionDigits = 2): string => {
  if (!Number.isFinite(value) || value === 0) return '$0';
  const direction = value > 0 ? '▲ +' : '▼ -';
  return `${direction}$${usdFormatter(maximumFractionDigits).format(Math.abs(value))}`;
};

/** `$1,234.50` — USD with exactly two decimals (ledgers, commissions).
 * Accepts undefined/null so optional API fields render as `$0.00`. */
export const formatUsdFixed = (value: number | undefined | null): string =>
  typeof value === 'number' && Number.isFinite(value)
    ? `$${Math.abs(value).toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`
    : '$0.00';

/** `$1,234.50` / `-$12.50` / `—` — account balances on decision surfaces
 * (go-live dialog). Unlike `formatUsdFixed`, the sign is kept and a missing or
 * non-finite value renders as an em dash: an operator must never read a
 * negative or unknown balance as a positive or zero one. */
export const formatUsdBalance = (value: number | undefined | null): string => {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
  const amount = Math.abs(value).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return value < 0 ? `-$${amount}` : `$${amount}`;
};

/** `12.3%` — percentage with fixed digits. */
export const formatPct = (value: number, fractionDigits = 1): string =>
  `${Number.isFinite(value) ? value.toFixed(fractionDigits) : '0.0'}%`;

/** `1,234` — rounded integer with locale grouping. */
export const formatCount = (value: number): string =>
  Math.round(Number.isFinite(value) ? value : 0).toLocaleString('en-US');

/** `+$1.2K`-style compact signed USD for KPI tiles (no currency symbol drift). */
export const formatSignedUsdCompact = (value: number): string => {
  if (!Number.isFinite(value) || value === 0) return '$0';
  const compact = Intl.NumberFormat('en-US', {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(Math.abs(value));
  return `${value > 0 ? '▲ +' : '▼ -'}$${compact}`;
};

/**
 * The bot always reports drawdown in percent (0-100, never a 0-1 fraction), so
 * no x100 guessing here: 0.5 means half a percent. Above 100% the simulated
 * equity went below zero, which is flagged rather than clamped.
 */
export const formatDrawdownPct = (value: number | undefined | null): string => {
  if (value === undefined || value === null) return 'N/A';
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 'N/A';
  const text = `${Math.abs(numeric).toFixed(1)}%`;
  return Math.abs(numeric) > 100 ? `${text} (equity below zero)` : text;
};
