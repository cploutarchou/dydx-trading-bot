/**
 * Pure mapping layer between the backend ClickHouse analytics envelopes
 * (backend/internal/app/analytics_routes.go) and the typed view models the
 * ClickHouseAnalytics page renders.
 *
 * Every backend analytics endpoint returns:
 *   { success, enabled, source, data: {...}, message?, error?, trace_id }
 * with the per-endpoint payload nested under `data`. These helpers centralize
 * that contract so the page never hand-reads envelope internals and the mapping
 * is unit-tested independently of React.
 */

export interface AnalyticsEnvelope {
  success: boolean;
  enabled?: boolean;
  source?: string;
  message?: string;
  error?: string;
  data?: unknown;
  trace_id?: string;
}

// Mirrors backend LivePositionSnapshot JSON tags.
export interface PositionSnapshot {
  snapshot_time: string;
  position_id: string;
  instance_id: string;
  bot_id: string;
  pair1: string;
  pair2: string;
  side1: string;
  side2: string;
  status: string;
  event_kind: string;
  entry_price1: number;
  entry_price2: number;
  current_price1?: number;
  current_price2?: number;
  entry_size1: number;
  entry_size2: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  realized_pnl: number;
  realized_pnl_pct: number;
  z_score_current?: number;
}

// Mirrors backend LiveTradeTotals / LiveTradeSummary JSON tags.
export interface TradeTotals {
  trade_events: number;
  trades_opened: number;
  trades_closed: number;
  total_realized_pnl: number;
  total_realized_pnl_pct: number;
  winning_trades: number;
  losing_trades: number;
}

export interface TradeSummary {
  instance_id: string;
  hours: number;
  totals: TradeTotals;
  order_events: number;
}

// Mirrors backend LivePairBreakdown JSON tags.
export interface PairBreakdown {
  pair1: string;
  pair2: string;
  trades_closed: number;
  total_realized_pnl: number;
  avg_realized_pnl_pct: number;
  winning_trades: number;
  losing_trades: number;
  best_realized_pnl: number;
  worst_realized_pnl: number;
}

// Mirrors backend WorkerMetric JSON tags (raw worker-metrics endpoint).
export interface WorkerMetric {
  metric_time: string;
  worker_id: string;
  worker_type: string;
  queue_name: string;
  metric_name: string;
  metric_value: number;
}

// Mirrors backend APIRequestSummary JSON tags (per route/method row).
export interface APIRequestSummaryRow {
  service: string;
  route: string;
  method: string;
  request_count: number;
  avg_latency_ms: number;
  error_count: number;
  rate_limited: number;
}

function asObject(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : undefined;
}

function envelopeMessage(env: AnalyticsEnvelope): string {
  return env.message || env.error || 'Failed to fetch analytics';
}

// extractError returns a user-facing error message for a failed/disabled envelope.
export function extractError(env: AnalyticsEnvelope | undefined): string | null {
  if (!env) {
    return 'No response from analytics endpoint';
  }
  if (env.success) {
    return null;
  }
  return envelopeMessage(env);
}

// GET /api/v1/analytics/position-history -> data.snapshots
export function extractPositionSnapshots(env: AnalyticsEnvelope): PositionSnapshot[] {
  const data = asObject(env.data);
  const snapshots = data?.snapshots;
  return Array.isArray(snapshots) ? (snapshots as PositionSnapshot[]) : [];
}

// GET /api/v1/analytics/trade-summary -> data (summary with nested totals)
export function extractTradeSummary(env: AnalyticsEnvelope): TradeSummary | null {
  const data = asObject(env.data);
  if (!data || !asObject(data.totals)) {
    return null;
  }
  const totals = data.totals as TradeTotals;
  return {
    instance_id: (data.instance_id as string) ?? '',
    hours: (data.hours as number) ?? 0,
    totals,
    order_events: (data.order_events as number) ?? 0,
  };
}

// GET /api/v1/analytics/pair-breakdown -> data.pairs
export function extractPairBreakdown(env: AnalyticsEnvelope): PairBreakdown[] {
  const data = asObject(env.data);
  const pairs = data?.pairs;
  return Array.isArray(pairs) ? (pairs as PairBreakdown[]) : [];
}

// GET /api/v1/analytics/worker-metrics -> data.metrics (raw metrics list)
export function extractWorkerMetrics(env: AnalyticsEnvelope): WorkerMetric[] {
  const data = asObject(env.data);
  const metrics = data?.metrics;
  return Array.isArray(metrics) ? (metrics as WorkerMetric[]) : [];
}

// GET /api/v1/analytics/api-requests/summary -> data.summary (per-route array)
export function extractAPIRequestSummary(env: AnalyticsEnvelope): APIRequestSummaryRow[] {
  const data = asObject(env.data);
  const summary = data?.summary;
  return Array.isArray(summary) ? (summary as APIRequestSummaryRow[]) : [];
}
