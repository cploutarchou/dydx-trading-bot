import { describe, expect, it } from 'vitest';
import {
    formatBacktestProgressSourceLabel,
    getFreshnessTone,
    resolveBacktestStreamBadge,
    resolveBacktestStreamHealth,
} from './LiveState';

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

describe('backtest stream health helpers', () => {
  it('formats known progress sources with friendly labels', () => {
    expect(formatBacktestProgressSourceLabel('websocket')).toBe('websocket');
    expect(formatBacktestProgressSourceLabel('polling_recovery')).toBe('polling recovery');
  });

  it('falls back to source value/default for unknown or empty labels', () => {
    expect(formatBacktestProgressSourceLabel('custom_source')).toBe('custom_source');
    expect(formatBacktestProgressSourceLabel('')).toBe('default');
    expect(formatBacktestProgressSourceLabel(undefined)).toBe('default');
  });

  it('resolves healthy websocket stream state', () => {
    const result = resolveBacktestStreamHealth('websocket', true);
    expect(result.label).toBe('Live stream healthy');
    expect(result.dotClass).toBe('bg-emerald-400');
  });

  it('resolves fallback and polling stream states', () => {
    expect(resolveBacktestStreamHealth('stale_resync', false).label).toBe('Resyncing via fallback');
    expect(resolveBacktestStreamHealth('polling', false).label).toBe('Recovery polling active');
  });

  it('resolves reusable badge tone + label for healthy and fallback streams', () => {
    expect(resolveBacktestStreamBadge('websocket', true)).toEqual({
      label: 'Live stream healthy',
      tone: 'healthy',
    });
    expect(resolveBacktestStreamBadge('polling_recovery', false)).toEqual({
      label: 'Resyncing via fallback',
      tone: 'delayed',
    });
  });
});
