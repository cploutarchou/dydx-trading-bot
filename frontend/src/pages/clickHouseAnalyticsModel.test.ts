import { describe, expect, it } from 'vitest';
import {
  AnalyticsEnvelope,
  APIRequestSummaryRow,
  PairBreakdown,
  TradeSummary,
  WorkerMetric,
  extractAPIRequestSummary,
  extractError,
  extractPairBreakdown,
  extractPositionSnapshots,
  extractTradeSummary,
  extractWorkerMetrics,
} from './clickHouseAnalyticsModel';

const ok = <T>(data: T): AnalyticsEnvelope => ({ success: true, enabled: true, source: 'clickhouse', data });

describe('extractPositionSnapshots', () => {
  it('reads data.snapshots (not data.positions)', () => {
    const env = ok({ snapshots: [{ position_id: 'p1', snapshot_time: '2024-01-01T00:00:00Z' }], count: 1 });
    expect(extractPositionSnapshots(env)).toHaveLength(1);
    expect(extractPositionSnapshots(env)[0]!.position_id).toBe('p1');
  });

  it('returns [] when disabled envelope has empty snapshots', () => {
    const env: AnalyticsEnvelope = { success: true, enabled: false, source: 'disabled', data: { snapshots: [], count: 0 } };
    expect(extractPositionSnapshots(env)).toEqual([]);
  });

  it('returns [] when data shape is unexpected', () => {
    expect(extractPositionSnapshots(ok({ positions: [{}] }))).toEqual([]);
    expect(extractPositionSnapshots({ success: true })).toEqual([]);
  });
});

describe('extractTradeSummary', () => {
  it('reads nested data.totals (not flat data.summary)', () => {
    const env = ok({
      instance_id: 'inst-1',
      hours: 24,
      totals: { trade_events: 10, trades_opened: 6, trades_closed: 4, total_realized_pnl: 1.5, total_realized_pnl_pct: 2.5, winning_trades: 3, losing_trades: 1 },
      daily: [],
      orders_by_status: [],
      order_events: 8,
    });
    const summary: TradeSummary | null = extractTradeSummary(env);
    expect(summary).not.toBeNull();
    expect(summary?.totals.trades_closed).toBe(4);
    expect(summary?.totals.total_realized_pnl).toBe(1.5);
    expect(summary?.order_events).toBe(8);
  });

  it('returns null when totals absent', () => {
    expect(extractTradeSummary(ok({ foo: 'bar' }))).toBeNull();
    expect(extractTradeSummary({ success: true })).toBeNull();
  });
});

describe('extractPairBreakdown', () => {
  it('reads data.pairs (not data.breakdown)', () => {
    const env = ok({ instance_id: 'i', hours: 24, pairs: [{ pair1: 'BTC', pair2: 'USD', trades_closed: 2 }] });
    const pairs: PairBreakdown[] = extractPairBreakdown(env);
    expect(pairs).toHaveLength(1);
    expect(pairs[0]!.pair2).toBe('USD');
  });

  it('returns [] when pairs absent', () => {
    expect(extractPairBreakdown(ok({ breakdown: [{}] }))).toEqual([]);
  });
});

describe('extractWorkerMetrics', () => {
  it('reads data.metrics', () => {
    const env = ok({ metrics: [{ worker_id: 'w1', metric_name: 'tasks_completed', metric_value: 5 }], count: 1 });
    const metrics: WorkerMetric[] = extractWorkerMetrics(env);
    expect(metrics[0]!.metric_name).toBe('tasks_completed');
  });

  it('returns [] for the summary envelope (which has throughput, not metrics)', () => {
    const summaryEnv = ok({ throughput: {}, failures: {}, total_metrics: 0 });
    expect(extractWorkerMetrics(summaryEnv)).toEqual([]);
  });
});

describe('extractAPIRequestSummary', () => {
  it('reads data.summary as an array of per-route rows', () => {
    const env = ok({
      service: 'backend',
      hours: 24,
      summary: [{ service: 'backend', route: '/api/v1/backtests', method: 'GET', request_count: 100, avg_latency_ms: 12.5, error_count: 2, rate_limited: 0 }],
      count: 1,
    });
    const rows: APIRequestSummaryRow[] = extractAPIRequestSummary(env);
    expect(rows).toHaveLength(1);
    expect(rows[0]!.request_count).toBe(100);
    expect(rows[0]!.error_count).toBe(2);
  });

  it('returns [] when summary is not an array', () => {
    expect(extractAPIRequestSummary(ok({ summary: { total_requests: 1 } }))).toEqual([]);
  });
});

describe('extractError', () => {
  it('returns null for a successful envelope', () => {
    expect(extractError(ok({}))).toBeNull();
  });

  it('returns the message for a failed envelope', () => {
    expect(extractError({ success: false, enabled: true, message: 'ClickHouse query failed' })).toBe('ClickHouse query failed');
  });

  it('falls back to error field when message absent', () => {
    expect(extractError({ success: false, enabled: true, error: 'boom' })).toBe('boom');
  });

  it('handles undefined envelope', () => {
    expect(extractError(undefined)).toBe('No response from analytics endpoint');
  });
});
