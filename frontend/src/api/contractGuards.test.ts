import { describe, expect, it } from 'vitest';
import {
  guardBacktestStatusContract,
  guardListBacktestsContract,
  guardRunBacktestContract,
  guardSyncHealthContract,
} from './contractGuards';

describe('contract guards', () => {
  it('accepts run backtest payload with run_id', () => {
    expect(() => guardRunBacktestContract({ data: { run_id: 'run-1' } })).not.toThrow();
  });

  it('rejects run backtest payload when run_id is missing', () => {
    expect(() => guardRunBacktestContract({ data: {} })).toThrow(/run_id/i);
  });

  it('accepts list backtests payload with backtests key', () => {
    expect(() => guardListBacktestsContract({ data: { backtests: [] } })).not.toThrow();
  });

  it('rejects list backtests payload when backtests key is missing', () => {
    expect(() => guardListBacktestsContract({ data: { runs: [] } })).toThrow(/backtests/i);
  });

  it('accepts backtest status payload with required keys', () => {
    expect(() =>
      guardBacktestStatusContract({ data: { run_id: 'run-1', status: 'RUNNING', progress_pct: 12.5 } })
    ).not.toThrow();
  });

  it('rejects backtest status payload when progress_pct is missing', () => {
    expect(() =>
      guardBacktestStatusContract({ data: { run_id: 'run-1', status: 'RUNNING' } })
    ).toThrow(/progress_pct/i);
  });

  it('accepts sync health payload with runs key', () => {
    expect(() => guardSyncHealthContract({ data: { runs: [] } })).not.toThrow();
  });

  it('rejects sync health payload when runs key is missing', () => {
    expect(() => guardSyncHealthContract({ data: { items: [] } })).toThrow(/runs/i);
  });
});

