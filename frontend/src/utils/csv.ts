/**
 * CSV export safety helpers (audit FE-028).
 *
 * Cells that come from API data can start with `=`, `+`, `-`, `@`, tab, or CR
 * and would be interpreted as formulas by Excel/Sheets on open (CSV formula
 * injection). Prefixing risky cells with `'` neutralizes execution while
 * keeping the text visible. Fully-numeric strings (including negative
 * numbers) are safe and left untouched so financial exports stay usable.
 */

const FORMULA_PREFIX = /^[=+\-@\t\r]/;

export const sanitizeCsvCell = (value: string): string => {
  if (!FORMULA_PREFIX.test(value)) return value;
  if (value.trim() !== '' && !Number.isNaN(Number(value))) return value;
  return `'${value}`;
};

/** Coerce any cell value to a sanitized, quoted-and-escaped CSV cell. */
export const toCsvCell = (value: string | number | boolean | null | undefined): string => {
  const raw = value === null || value === undefined ? '' : String(value);
  const sanitized = sanitizeCsvCell(raw);
  if (sanitized.includes(',') || sanitized.includes('"') || sanitized.includes('\n')) {
    return `"${sanitized.replace(/"/g, '""')}"`;
  }
  return sanitized;
};
