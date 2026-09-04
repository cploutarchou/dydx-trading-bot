import { describe, expect, it } from 'vitest';
import { formatCount, formatPct, formatSignedUsd, formatSignedUsdCompact, formatUsd } from './format';

describe('shared formatters', () => {
  it('formatUsd renders grouped absolute amounts', () => {
    expect(formatUsd(1234.5)).toBe('$1,234.5');
    expect(formatUsd(0)).toBe('$0');
    expect(formatUsd(-42)).toBe('$42');
  });

  it('formatSignedUsd adds direction arrows and keeps zero neutral', () => {
    expect(formatSignedUsd(12.5)).toBe('▲ +$12.5');
    expect(formatSignedUsd(-4)).toBe('▼ -$4');
    expect(formatSignedUsd(0)).toBe('$0');
    expect(formatSignedUsd(Number.NaN)).toBe('$0');
  });

  it('formatPct fixes fraction digits', () => {
    expect(formatPct(12.34)).toBe('12.3%');
    expect(formatPct(12.34, 2)).toBe('12.34%');
    expect(formatPct(Number.NaN)).toBe('0.0%');
  });

  it('formatCount rounds and groups', () => {
    expect(formatCount(1234.6)).toBe('1,235');
    expect(formatCount(Number.NaN)).toBe('0');
  });

  it('formatSignedUsdCompact keeps sign and compacts magnitude', () => {
    expect(formatSignedUsdCompact(1500)).toBe('▲ +$1.5K');
    expect(formatSignedUsdCompact(-2500000)).toBe('▼ -$2.5M');
    expect(formatSignedUsdCompact(0)).toBe('$0');
  });
});
