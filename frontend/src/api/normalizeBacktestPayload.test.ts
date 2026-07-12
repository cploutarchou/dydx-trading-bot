import { describe, expect, it } from 'vitest';
import { normalizeBacktestPayload } from '../api';

describe('normalizeBacktestPayload', () => {
  it('preserves explicit max_pairs even when pairs are provided', () => {
    const payload = normalizeBacktestPayload({
      start_date: '2026-03-01',
      end_date: '2026-03-31',
      pairs: ['BTC-USD', 'ETH-USD', 'SOL-USD', 'ETH-USD'],
      max_pairs: 7,
      trading_parameters: {
        pair_selection_mode: 'cointegration',
      },
    });

    expect(payload.pairs).toEqual(['BTC-USD', 'ETH-USD', 'SOL-USD']);
    expect(payload.selected_pairs).toEqual([
      'BTC-USD/ETH-USD',
      'BTC-USD/SOL-USD',
      'ETH-USD/SOL-USD',
    ]);
    expect(payload.max_pairs).toBe(7);
    expect(payload.pair_selection_mode).toBe('cointegration');
    expect(payload.trading_parameters?.pair_selection_mode).toBe('cointegration');
    expect(payload.benchmark_symbol).toBeUndefined();
    expect(payload.trading_parameters?.benchmark_symbol).toBeUndefined();
    expect(payload.source).toBe('ui');
  });

  it('preserves an explicit benchmark without synthesizing a default', () => {
    const payload = normalizeBacktestPayload({
      start_date: '2026-03-01',
      end_date: '2026-03-31',
      pairs: ['ETH-USD', 'SOL-USD'],
      benchmark_symbol: 'ETH-USD',
      trading_parameters: {
        benchmark_symbol: 'SOL-USD',
      },
    });

    expect(payload.benchmark_symbol).toBe('ETH-USD');
    expect(payload.trading_parameters?.benchmark_symbol).toBe('SOL-USD');
  });

  it('infers max_pairs from deduped pairs only when explicit value is missing/invalid', () => {
    const noMaxPairs = normalizeBacktestPayload({
      start_date: '2026-03-01',
      end_date: '2026-03-31',
      pairs: ['BTC-USD', 'ETH-USD', 'SOL-USD', 'ETH-USD'],
      trading_parameters: {},
    });

    expect(noMaxPairs.max_pairs).toBe(3);

    const invalidMaxPairs = normalizeBacktestPayload({
      start_date: '2026-03-01',
      end_date: '2026-03-31',
      pairs: ['BTC-USD', 'ETH-USD', 'SOL-USD'],
      max_pairs: 0,
      trading_parameters: {},
    });

    expect(invalidMaxPairs.max_pairs).toBe(3);
  });

  it('does not force pair_selection_mode when omitted', () => {
    const payload = normalizeBacktestPayload({
      start_date: '2026-03-01',
      end_date: '2026-03-31',
      pairs: ['BTC-USD', 'ETH-USD'],
      trading_parameters: {
        resolution: '4H',
      },
    });

    expect(payload.pair_selection_mode).toBeUndefined();
    expect(payload.trading_parameters?.pair_selection_mode).toBeUndefined();
    expect(payload.trading_parameters?.resolution).toBe('4HOURS');
    expect(payload.trading_parameters?.candle_resolution).toBe('4HOURS');
    expect(payload.selected_pairs).toEqual(['BTC-USD/ETH-USD']);
  });

  it('derives market universe from explicit selected_pairs when pairs are omitted', () => {
    const payload = normalizeBacktestPayload({
      start_date: '2026-03-01',
      end_date: '2026-03-31',
      strategy_id: 12,
      selected_pairs: ['BTC-USD/ETH-USD', 'ETH-USD/SOL-USD'],
      source: 'backtest-rerun',
      trading_parameters: {},
    });

    expect(payload.pairs).toEqual(['BTC-USD', 'ETH-USD', 'SOL-USD']);
    expect(payload.selected_pairs).toEqual(['BTC-USD/ETH-USD', 'ETH-USD/SOL-USD']);
    expect(payload.source).toBe('backtest-rerun');
  });

  it('rejects backtest payloads without selected markets or selected_pairs', () => {
    expect(() =>
      normalizeBacktestPayload({
        start_date: '2026-03-01',
        end_date: '2026-03-31',
        strategy_id: 12,
        trading_parameters: {},
      })
    ).toThrow('Backtest payload requires at least two selected markets');
  });
});
