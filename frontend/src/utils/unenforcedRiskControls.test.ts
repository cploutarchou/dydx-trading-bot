import { describe, expect, it } from 'vitest';
import {
  excludeRiskControlBlockers,
  formatRiskControlValue,
  isResolvableRiskControl,
  normalizeUnenforcedRiskControls,
  riskControlLabel,
  splitUnenforcedRiskControls,
} from './unenforcedRiskControls';

describe('unenforced risk controls helpers', () => {
  it('only treats max drawdown and trailing stop as resolvable', () => {
    expect(isResolvableRiskControl('max_drawdown_pct')).toBe(true);
    expect(isResolvableRiskControl('trailing_stop_pct')).toBe(true);
    expect(isResolvableRiskControl('stop_loss_pct')).toBe(false);
    // Inherited object keys must never count as a known field.
    expect(isResolvableRiskControl('constructor')).toBe(false);
    expect(isResolvableRiskControl('toString')).toBe(false);
  });

  it('labels known fields and falls back to the raw field', () => {
    expect(riskControlLabel('max_drawdown_pct')).toBe('Max drawdown');
    expect(riskControlLabel('trailing_stop_pct')).toBe('Trailing stop');
    expect(riskControlLabel('max_daily_loss_pct')).toBe('max_daily_loss_pct');
  });

  it('formats the configured value as a percentage without padded decimals', () => {
    expect(formatRiskControlValue(15)).toBe('15%');
    expect(formatRiskControlValue(1)).toBe('1%');
    expect(formatRiskControlValue(2.25)).toBe('2.25%');
    expect(formatRiskControlValue(Number.NaN)).toBe('—');
  });

  it('returns no controls when the backend omits the field', () => {
    expect(normalizeUnenforcedRiskControls(undefined)).toEqual([]);
    expect(normalizeUnenforcedRiskControls(null)).toEqual([]);
    expect(normalizeUnenforcedRiskControls('max_drawdown_pct')).toEqual([]);
  });

  it('drops malformed rows and keeps one row per field', () => {
    const controls = normalizeUnenforcedRiskControls([
      { field: 'max_drawdown_pct', value: 15, message: 'max_drawdown_pct=15 is not enforced' },
      { field: 'max_drawdown_pct', value: 20, message: 'duplicate' },
      {
        field: 'trailing_stop_pct',
        value: '1.5',
        message: 'trailing_stop_pct=1.5 is not enforced',
      },
      { value: 3, message: 'no field' },
      null,
      'trailing_stop_pct',
    ]);

    expect(controls).toEqual([
      { field: 'max_drawdown_pct', value: 15, message: 'max_drawdown_pct=15 is not enforced' },
      { field: 'trailing_stop_pct', value: 1.5, message: 'trailing_stop_pct=1.5 is not enforced' },
    ]);
  });

  it('splits resolvable controls from the ones that stay plain blockers', () => {
    const { resolvable, unresolvable } = splitUnenforcedRiskControls([
      { field: 'max_drawdown_pct', value: 15, message: 'a' },
      { field: 'max_daily_loss_pct', value: 4, message: 'b' },
      { field: 'trailing_stop_pct', value: 1, message: 'c' },
    ]);

    expect(resolvable.map((control) => control.field)).toEqual([
      'max_drawdown_pct',
      'trailing_stop_pct',
    ]);
    expect(unresolvable.map((control) => control.field)).toEqual(['max_daily_loss_pct']);
  });

  it('removes only the blockers that repeat a control message exactly', () => {
    const controls = [
      { field: 'max_drawdown_pct', value: 15, message: 'Max drawdown is not enforced live.' },
    ];

    expect(
      excludeRiskControlBlockers(
        [
          'Max drawdown is not enforced live.',
          'No dYdX key found for mainnet.',
          'Max drawdown is not enforced live. Extra detail.',
          '   ',
          42,
        ],
        controls
      )
    ).toEqual([
      'No dYdX key found for mainnet.',
      'Max drawdown is not enforced live. Extra detail.',
    ]);
    expect(excludeRiskControlBlockers(undefined, controls)).toEqual([]);
    expect(excludeRiskControlBlockers(['Low collateral'], [])).toEqual(['Low collateral']);
  });
});
