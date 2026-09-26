import { describe, expect, it } from 'vitest';
import {
  formatCount,
  formatDrawdownPct,
  formatPct,
  formatSignedUsd,
  formatSignedUsdCompact,
  formatUsd,
  formatUsdBalance,
  formatUsdFixed,
} from './format';

describe('shared formatters', () => {
  it('formatUsd renders grouped absolute amounts', () => {
    expect(formatUsd(1234.5)).toBe('$1,234.5');
    expect(formatUsd(0)).toBe('$0');
    expect(formatUsd(-42)).toBe('$42');
  });

  it('formatUsdFixed keeps exactly two decimals for ledger surfaces', () => {
    expect(formatUsdFixed(100)).toBe('$100.00');
    expect(formatUsdFixed(1234.5)).toBe('$1,234.50');
    expect(formatUsdFixed(Number.NaN)).toBe('$0.00');
    expect(formatUsdFixed(undefined)).toBe('$0.00');
    expect(formatUsdFixed(null)).toBe('$0.00');
  });

  it('formatUsdBalance keeps the sign and never turns a missing balance into zero', () => {
    expect(formatUsdBalance(1234.5)).toBe('$1,234.50');
    expect(formatUsdBalance(0)).toBe('$0.00');
    expect(formatUsdBalance(-12.5)).toBe('-$12.50');
    expect(formatUsdBalance(undefined)).toBe('—');
    expect(formatUsdBalance(null)).toBe('—');
    expect(formatUsdBalance(Number.NaN)).toBe('—');
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

  it('formatDrawdownPct reads percent as percent and flags equity below zero', () => {
    expect(formatDrawdownPct(0.5)).toBe('0.5%');
    expect(formatDrawdownPct(9)).toBe('9.0%');
    expect(formatDrawdownPct(270.7)).toBe('270.7% (equity below zero)');
    expect(formatDrawdownPct(null)).toBe('N/A');
    expect(formatDrawdownPct(Number.NaN)).toBe('N/A');
  });
});
