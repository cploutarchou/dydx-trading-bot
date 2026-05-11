import { useQuery } from '@tanstack/react-query';
import { Activity, BarChart3, RefreshCw, ShieldCheck, TrendingUp } from 'lucide-react';
import api, {
    type ArbitrageImprovementMetricsResponse,
    type ArbitragePairPriorityItem,
} from '../api';

const metricValue = (
  metrics: ArbitrageImprovementMetricsResponse | undefined,
  key: string
): number => {
  const value = metrics?.counters?.[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
};

const formatMetric = (value: number): string =>
  value >= 1000
    ? Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(value)
    : String(value);

const formatScore = (value: unknown): string => {
  const parsed = typeof value === 'number' && Number.isFinite(value) ? value : 0;
  return parsed.toFixed(2);
};

const flagLabel = (name: string): string =>
  name
    .replace(/_ENABLED$/, '')
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

const reasonLabel = (name: string): string =>
  name
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

export function ArbitrageImprovementPanel() {
  const metricsQuery = useQuery({
    queryKey: ['arbitrage', 'improvement-metrics'],
    queryFn: async () => {
      const response = await api.getArbitrageImprovementMetrics();
      return response.data;
    },
    refetchInterval: 10_000,
  });

  const priorityQuery = useQuery({
    queryKey: ['arbitrage', 'pair-priority'],
    queryFn: async () => {
      const response = await api.getArbitragePairPriority(10);
      return response.data;
    },
    refetchInterval: 30_000,
  });

  const metrics = metricsQuery.data;
  const pairPriority = priorityQuery.data;
  const flags = metrics?.feature_flags ?? {};
  const topPairs: ArbitragePairPriorityItem[] = Array.isArray(pairPriority?.pairs)
    ? pairPriority.pairs.slice(0, 6)
    : [];
  const cacheHits = metricValue(metrics, 'cache_hits_total');
  const cacheMisses = metricValue(metrics, 'cache_misses_total');
  const cacheTotal = cacheHits + cacheMisses;
  const cacheHitRate = cacheTotal > 0 ? (cacheHits / cacheTotal) * 100 : 0;
  const topRejections = Object.entries(metrics?.rejection_reasons ?? {})
    .filter(([, count]) => typeof count === 'number' && Number.isFinite(count) && count > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);

  const errorText =
    metricsQuery.error instanceof Error
      ? metricsQuery.error.message
      : priorityQuery.error instanceof Error
        ? priorityQuery.error.message
        : '';

  return (
    <section className="operator-section-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="surface-label">
            <TrendingUp className="h-3.5 w-3.5" />
            Arbitrage intelligence
          </div>
          <h2 className="mt-3 text-lg font-semibold text-white">Efficiency & Pair Priority</h2>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">
            Backend-proxied bot metrics for scan efficiency, saved API calls, pair ordering, and
            rejection visibility.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            void metricsQuery.refetch();
            void priorityQuery.refetch();
          }}
          disabled={metricsQuery.isFetching || priorityQuery.isFetching}
          className="premium-button premium-button-secondary rounded-2xl px-4 py-2 text-sm disabled:opacity-60"
        >
          <RefreshCw
            size={16}
            className={metricsQuery.isFetching || priorityQuery.isFetching ? 'animate-spin' : ''}
          />
          Refresh
        </button>
      </div>

      {errorText && (
        <div className="mt-4 rounded-lg border border-amber-600/50 bg-amber-950/25 px-3 py-2 text-sm text-amber-200">
          {errorText}
        </div>
      )}

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          {
            label: 'Scan cycles',
            value: metricValue(metrics, 'arbitrage_scan_cycles_total'),
            icon: Activity,
          },
          {
            label: 'API calls saved',
            value: metricValue(metrics, 'exchange_api_calls_saved_total'),
            icon: ShieldCheck,
          },
          {
            label: 'Duplicates avoided',
            value: metricValue(metrics, 'duplicate_api_calls_avoided_total'),
            icon: BarChart3,
          },
          {
            label: 'Cache hit rate',
            value: cacheHitRate,
            suffix: '%',
            icon: RefreshCw,
          },
        ].map((item) => {
          const Icon = item.icon;
          return (
            <div
              key={item.label}
              className="rounded-lg border border-slate-800 bg-slate-950/55 p-4"
            >
              <div className="flex items-center justify-between gap-2">
                <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                  {item.label}
                </p>
                <Icon className="h-4 w-4 text-cyan-300" />
              </div>
              <p className="mt-2 text-2xl font-semibold text-white">
                {item.suffix === '%' ? item.value.toFixed(1) : formatMetric(item.value)}
                {item.suffix ?? ''}
              </p>
            </div>
          );
        })}
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-[0.9fr,1.1fr]">
        <div className="rounded-lg border border-slate-800 bg-slate-950/45 p-4">
          <h3 className="text-sm font-semibold text-white">Feature Flags</h3>
          <div className="mt-3 grid gap-2">
            {Object.entries(flags).length === 0 ? (
              <p className="text-sm text-slate-500">No flag data returned yet.</p>
            ) : (
              Object.entries(flags).map(([name, enabled]) => (
                <div key={name} className="flex items-center justify-between gap-3 text-sm">
                  <span className="text-slate-300">{flagLabel(name)}</span>
                  <span
                    className="operator-status-pill"
                    data-tone={enabled ? 'positive' : 'warning'}
                  >
                    {enabled ? 'Enabled' : 'Off'}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="rounded-lg border border-slate-800 bg-slate-950/45 p-4">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-white">Pair Priority</h3>
            <span className="text-xs text-slate-500">
              {pairPriority?.enabled ? 'ranking active' : 'diagnostic order'}
            </span>
          </div>
          <div className="mt-3 overflow-hidden rounded-lg border border-slate-800">
            <div className="grid grid-cols-[1.2fr_0.4fr_1.4fr] bg-slate-900/70 px-3 py-2 text-[10px] uppercase tracking-[0.14em] text-slate-500">
              <span>Pair</span>
              <span>Score</span>
              <span>Reason</span>
            </div>
            {topPairs.length === 0 ? (
              <div className="px-3 py-4 text-sm text-slate-500">No pair priority data yet.</div>
            ) : (
              topPairs.map((pair) => (
                <div
                  key={`${pair.base_market}-${pair.quote_market}`}
                  className="grid grid-cols-[1.2fr_0.4fr_1.4fr] gap-3 border-t border-slate-800 px-3 py-2 text-sm"
                >
                  <span className="font-mono text-slate-100">{pair.pair}</span>
                  <span className="text-cyan-200">{formatScore(pair.score)}</span>
                  <span className="truncate text-slate-400">
                    {Array.isArray(pair.explanation) && pair.explanation.length > 0
                      ? pair.explanation.join(', ')
                      : 'internal data'}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-slate-800 bg-slate-950/45 p-4">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-white">Top Rejection Reasons</h3>
          <span className="text-xs text-slate-500">from live opportunity checks</span>
        </div>
        {topRejections.length === 0 ? (
          <p className="mt-3 text-sm text-slate-500">No rejection reason data yet.</p>
        ) : (
          <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {topRejections.map(([reason, count]) => (
              <div
                key={reason}
                className="flex items-center justify-between rounded-md border border-slate-800 bg-slate-900/50 px-3 py-2 text-sm"
              >
                <span className="text-slate-300">{reasonLabel(reason)}</span>
                <span className="font-semibold text-amber-200">{formatMetric(count)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
