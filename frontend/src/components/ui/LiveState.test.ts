import { describe, expect, it } from 'vitest';
import { getFreshnessTone } from './LiveState';

describe('live-state freshness tone', () => {
  const now = new Date('2026-05-07T10:00:00.000Z').getTime();

  it('maps fresh timestamps to live tone', () => {
    expect(getFreshnessTone('2026-05-07T09:59:50.000Z', now)).toBe('live');
  });

  it('escalates delayed and stale timestamps', () => {
    expect(getFreshnessTone('2026-05-07T09:59:20.000Z', now)).toBe('delayed');
    expect(getFreshnessTone('2026-05-07T09:58:00.000Z', now)).toBe('stale');
  });

  it('uses offline tone for missing or invalid timestamps', () => {
    expect(getFreshnessTone(null, now)).toBe('offline');
    expect(getFreshnessTone('not-a-date', now)).toBe('offline');
  });
});

