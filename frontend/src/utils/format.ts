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
