import { describe, expect, it } from 'vitest';
import {
  resolveHeartbeatTone,
  summarizeRuntimeHealth,
  toStrategyStatus,
  type StrategyStatus,
} from './runtimeStatus';

const NOW = Date.parse('2026-09-26T15:00:00Z');

const runtime = (overrides: Record<string, unknown> = {}): Record<string, unknown> => ({
  strategy_id: 2,
  status: 'running',
  bot_status: 'running',
  is_running: true,
  open_positions: 2,
  uptime_seconds: 120,
  runtime_updated_at: '2026-09-26T14:59:50Z',
  last_synced_at: '2026-09-26T14:59:59Z',
  runtime_confirmed: true,
  exposure_unconfirmed: false,
  ...overrides,
});

describe('toStrategyStatus', () => {
  it('keeps the bot error when positions are still recorded, and flags the exposure', () => {
    const status = toStrategyStatus(
      2,
      runtime({
        status: 'error',
        bot_status: 'error',
        is_running: false,
        open_positions: 16,
        last_error: 'Runtime process for strategy-85-2 is no longer running',
        exposure_unconfirmed: true,
        uptime_seconds: undefined,
        started_at: '2026-09-21T04:30:00Z',
      }),
      NOW
    );

    expect(status.status).toBe('error');
    expect(status.lastError).toContain('no longer running');
    expect(status.openPositions).toBe(16);
    expect(status.exposureUnconfirmed).toBe(true);
    // No uptime is invented for a runtime that is not operational.
    expect(status.uptimeSeconds).toBeUndefined();
  });

  it('derives the exposure flag itself when an older backend omits it', () => {
    const status = toStrategyStatus(
      2,
      runtime({
        status: 'stopped',
        is_running: false,
        open_positions: 3,
        exposure_unconfirmed: undefined,
      }),
      NOW
    );
    expect(status.exposureUnconfirmed).toBe(true);

    const live = toStrategyStatus(2, runtime({ exposure_unconfirmed: undefined }), NOW);
    expect(live.exposureUnconfirmed).toBe(false);
  });

  it('never uses the poll time as the runtime heartbeat', () => {
    const status = toStrategyStatus(2, runtime({ runtime_updated_at: undefined }), NOW);
    expect(status.runtimeUpdatedAt).toBeUndefined();
    expect(status.updatedAt).toBe('2026-09-26T14:59:59Z');
  });

  it('marks an unreachable bot as unconfirmed and keeps the last confirmation time', () => {
    const status = toStrategyStatus(
      2,
      runtime({
        status: 'error',
        bot_status: 'unavailable',
        is_running: false,
        runtime_confirmed: false,
        last_confirmed_at: '2026-09-26T14:30:00Z',
      }),
      NOW
    );
    expect(status.runtimeConfirmed).toBe(false);
    expect(status.lastConfirmedAt).toBe('2026-09-26T14:30:00Z');
  });

  it('falls back to stopped for an unknown status and normalises the win rate', () => {
    const status = toStrategyStatus(2, runtime({ status: 'weird', win_rate: 0.62 }), NOW);
    expect(status.status).toBe('stopped');
    expect(status.winRate).toBeCloseTo(62);
  });
});

describe('resolveHeartbeatTone', () => {
  it('is unknown without a runtime update time, whatever the socket state', () => {
    expect(resolveHeartbeatTone(undefined, true, NOW).tone).toBe('unknown');
    expect(resolveHeartbeatTone(undefined, false, NOW).tone).toBe('unknown');
  });

  it('grades a runtime update by its age', () => {
    expect(resolveHeartbeatTone('2026-09-26T14:59:50Z', true, NOW).tone).toBe('live');
    expect(resolveHeartbeatTone('2026-09-26T14:59:50Z', false, NOW).tone).toBe('delayed');
    expect(resolveHeartbeatTone('2026-09-26T14:58:30Z', true, NOW).tone).toBe('delayed');
    expect(resolveHeartbeatTone('2026-09-26T14:50:00Z', true, NOW).tone).toBe('stale');
  });
});

describe('summarizeRuntimeHealth', () => {
  const dead: StrategyStatus = {
    strategyId: 2,
    status: 'error',
    updatedAt: '2026-09-26T14:59:59Z',
    openPositions: 16,
    uptimeSeconds: undefined,
    runtimeConfirmed: true,
    exposureUnconfirmed: true,
  };
  const alive: StrategyStatus = {
    strategyId: 3,
    status: 'running',
    updatedAt: '2026-09-26T14:59:59Z',
    runtimeUpdatedAt: '2026-09-26T14:59:50Z',
    openPositions: 2,
    uptimeSeconds: 600,
    pnl: 1.5,
    runtimeConfirmed: true,
    exposureUnconfirmed: false,
  };

  it('sums positions and uptime over active runtimes only', () => {
    const summary = summarizeRuntimeHealth([dead, alive], NOW);
    expect(summary.scopedCount).toBe(1);
    expect(summary.totalOpenPositions).toBe(2);
    expect(summary.longestUptimeSeconds).toBe(600);
    expect(summary.totalPnl).toBe(1.5);
    expect(summary.unconfirmedExposureCount).toBe(1);
    expect(summary.unconfirmedExposurePositions).toBe(16);
    expect(summary.staleRuntimeCount).toBe(0);
  });

  it('reports nothing live when no runtime is active, instead of the dead one', () => {
    const summary = summarizeRuntimeHealth([dead], NOW);
    expect(summary.scopedCount).toBe(0);
    expect(summary.totalOpenPositions).toBeUndefined();
    expect(summary.longestUptimeSeconds).toBeUndefined();
    expect(summary.unconfirmedExposurePositions).toBe(16);
  });

  it('counts an active runtime without a heartbeat as stale and an unreachable bot as unconfirmed', () => {
    const summary = summarizeRuntimeHealth(
      [{ ...alive, runtimeUpdatedAt: undefined, runtimeConfirmed: false }],
      NOW
    );
    expect(summary.staleRuntimeCount).toBe(1);
    expect(summary.unconfirmedRuntimeCount).toBe(1);
  });
});
