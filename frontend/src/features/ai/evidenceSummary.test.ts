import { describe, expect, it } from 'vitest';
import { formatAIParamValue, formatEvidenceSummaryChips } from './evidenceSummary';

const summary = {
  completed_runs: 5,
  trades_analysed: 312,
  pairs_analysed: 12,
  live_closed_trades: 9,
  live_open_positions: 2,
  live_available: true,
  cointegrated_pairs: 4,
  data_notes: [],
};

describe('formatEvidenceSummaryChips', () => {
  it('lists every part with data', () => {
    expect(formatEvidenceSummaryChips(summary)).toEqual([
      '5 completed runs',
      '312 trades',
      '12 pairs',
      '4 cointegrated pairs',
      'live: 9 closed, 2 open',
    ]);
  });

  it('leaves out zero parts and the live chip when live data was unavailable', () => {
    expect(
      formatEvidenceSummaryChips({
        ...summary,
        pairs_analysed: 0,
        cointegrated_pairs: 0,
        live_available: false,
        live_closed_trades: 9,
      })
    ).toEqual(['5 completed runs', '312 trades']);
  });

  it('uses singular labels and renders nothing for an empty summary', () => {
    expect(
      formatEvidenceSummaryChips({
        ...summary,
        completed_runs: 1,
        trades_analysed: 1,
        pairs_analysed: 1,
        cointegrated_pairs: 1,
        live_closed_trades: 0,
        live_open_positions: 0,
      })
    ).toEqual([
      '1 completed run',
      '1 trade',
      '1 pair',
      '1 cointegrated pair',
      'live: 0 closed, 0 open',
    ]);
    expect(
      formatEvidenceSummaryChips({
        completed_runs: 0,
        trades_analysed: 0,
        pairs_analysed: 0,
        live_closed_trades: 0,
        live_open_positions: 0,
        live_available: false,
        cointegrated_pairs: 0,
        data_notes: [],
      })
    ).toEqual([]);
  });
});

describe('formatAIParamValue', () => {
  it('formats units, booleans and missing values', () => {
    expect(formatAIParamValue(50, 'USD')).toBe('50 USD');
    expect(formatAIParamValue(15, '%')).toBe('15%');
    expect(formatAIParamValue(1.5, '')).toBe('1.5');
    expect(formatAIParamValue(true, '')).toBe('On');
    expect(formatAIParamValue('1HOUR', '')).toBe('1HOUR');
    expect(formatAIParamValue(null, 'USD')).toBe('—');
  });
});
