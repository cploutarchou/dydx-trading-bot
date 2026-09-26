/**
 * Timestamps from the backend can carry Go's zero time (`0001-01-01T00:00:00Z`)
 * when a field was never set. It parses as a valid date, so rendering it gives
 * "0001-01-01" or an age of millions of hours. Treat it as missing instead.
 */

/** Returns the value when it is a parseable timestamp after year 1, else undefined. */
export const meaningfulTimestamp = (value: unknown): string | undefined => {
  if (typeof value !== 'string') return undefined;
  const trimmed = value.trim();
  // Checked textually too: V8 reads "0001-01-01 00:00:00 UTC" as the year 2001.
  if (!trimmed || trimmed.startsWith('0001-01-01')) return undefined;
  const parsed = new Date(trimmed);
  if (Number.isNaN(parsed.getTime()) || parsed.getUTCFullYear() <= 1) return undefined;
  return trimmed;
};
