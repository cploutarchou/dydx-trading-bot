import { describe, expect, it } from 'vitest';
import { meaningfulTimestamp } from './timestamps';

describe('meaningfulTimestamp', () => {
  it('keeps real timestamps', () => {
    expect(meaningfulTimestamp('2026-09-26T11:22:16Z')).toBe('2026-09-26T11:22:16Z');
  });

  it('drops Go zero time, blanks, junk and non-strings', () => {
    expect(meaningfulTimestamp('0001-01-01T00:00:00Z')).toBeUndefined();
    expect(meaningfulTimestamp('0001-01-01 00:00:00.000 UTC')).toBeUndefined();
    expect(meaningfulTimestamp('   ')).toBeUndefined();
    expect(meaningfulTimestamp('not a date')).toBeUndefined();
    expect(meaningfulTimestamp(null)).toBeUndefined();
    expect(meaningfulTimestamp(0)).toBeUndefined();
  });
});
