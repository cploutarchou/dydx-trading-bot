import { useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import {
    Activity,
    ArrowRight,
    Award,
    BarChart3,
    ChevronRight,
    Layers3,
    ListChecks,
    PlusCircle,
    ShieldCheck,
    Sparkles,
    Target,
    TrendingUp,
} from 'lucide-react';
import React, { useMemo, useRef } from 'react';
import { Link } from 'react-router-dom';
import api from '../api';
import { enhancedApiClient } from '../api/enhancedClient';
import { BacktestList } from '../components/BacktestList';
import { BacktestRunner } from '../components/BacktestRunner';
import { CodexAssetIntelStrip } from '../components/CodexAssetIntelStrip';
import { PageContainer } from '../components/PageContainer';
import { TerminalDataGrid, type TerminalColumn } from '../components/TerminalDataGrid';
import {
    buildIntelligence,
    extractBacktestRuns,
    formatCurrency,
    formatDateTime,
    formatPercent,
    isActiveBacktestRun,
    normalizePercent,
    safeNumber,
    type BacktestRun,
    type StrategyAggregate,
    type StrategyRef,
} from '../features/backtests/intelligence';
import { buildBacktestIntelRequest } from '../features/codex/marketIntel';

export type BacktestsView = 'dashboard' | 'new' | 'runs';

interface BacktestsPageProps {
  view?: BacktestsView;
}

const StatCard: React.FC<{
  label: string;
  value: string;
  hint: string;
  icon: React.ReactNode;
}> = ({ label, value, hint, icon }) => (
  <div className="operator-stat-card p-5">
    <div className="mb-3 flex items-start justify-between">
      <div className="rounded-xl bg-blue-500/10 p-2 text-blue-400">{icon}</div>
      <span className="text-[10px] uppercase tracking-[0.18em] text-slate-500">{label}</span>
    </div>
    <p className="text-2xl font-bold text-white">{value}</p>
    <p className="mt-1 text-xs text-slate-400">{hint}</p>
  </div>
);

const InsightCard: React.FC<{
  title: string;
  icon: React.ReactNode;
  aggregate: StrategyAggregate | null;
  accent: string;
  secondary: string;
}> = ({ title, icon, aggregate, accent, secondary }) => (
  <div className="operator-section-card p-5">
    <div className="mb-4 flex items-center gap-3">
      <div className={`rounded-xl p-2 ${accent}`}>{icon}</div>
      <div>
        <p className="text-sm font-semibold text-white">{title}</p>
        <p className="text-xs text-slate-500">Based on completed backtests only</p>
      </div>
    </div>
    {aggregate ? (
      <>
        <p className="text-lg font-semibold text-white">{aggregate.label}</p>
        <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
          <div>
            <p className="text-slate-500">Runs</p>
            <p className="font-semibold text-slate-200">{aggregate.completedRuns}</p>
          </div>
          <div>
            <p className="text-slate-500">Total P&amp;L</p>
            <p className={`font-semibold ${secondary}`}>{formatCurrency(aggregate.totalPnl)}</p>
          </div>
          <div>
            <p className="text-slate-500">Avg Sharpe</p>
            <p className="font-semibold text-slate-200">{aggregate.avgSharpe.toFixed(2)}</p>
          </div>
          <div>
            <p className="text-slate-500">Avg Drawdown</p>
            <p className="font-semibold text-slate-200">
              {formatPercent(aggregate.avgDrawdownPct)}
            </p>
          </div>
        </div>
      </>
    ) : (
      <p className="text-sm text-slate-400">
        No completed backtests yet. Run a backtest to unlock this ranking.
      </p>
    )}
  </div>
);

const BacktestWorkflowCards = () => (
  <section className="grid gap-3 md:grid-cols-3">
    <Link to="/strategies" className="operator-action-card p-4">
      <p className="text-sm font-semibold text-white">1. Choose strategy</p>
      <p className="mt-1 text-xs leading-5 text-slate-500">
        Start from a saved strategy or build a new setup first.
      </p>
    </Link>
    <Link to="/backtests/new" className="operator-action-card p-4">
      <p className="text-sm font-semibold text-white">2. Run validation</p>
      <p className="mt-1 text-xs leading-5 text-slate-500">
        Configure dates, pairs, sizing, and historical assumptions.
      </p>
    </Link>
    <Link to="/bots" className="operator-action-card p-4">
      <p className="text-sm font-semibold text-white">3. Deploy only when ready</p>
      <p className="mt-1 text-xs leading-5 text-slate-500">
        Promote validated strategies into live or paper runtime management.
      </p>
    </Link>
  </section>
);

const parseTimestampMs = (value: unknown): number | undefined => {
  if (typeof value !== 'string') {
    return undefined;
  }
  const parsed = new Date(value).getTime();
  return Number.isFinite(parsed) ? parsed : undefined;
};

const getFreshnessElapsedSeconds = (updatedAtMs?: number): number | null => {
  if (!updatedAtMs || !Number.isFinite(updatedAtMs)) {
    return null;
  }
  return Math.max(0, Math.floor((Date.now() - updatedAtMs) / 1000));
};

const formatFreshnessAge = (updatedAtMs?: number): string | null => {
  const elapsedSeconds = getFreshnessElapsedSeconds(updatedAtMs);
  if (elapsedSeconds === null) {
    return null;
  }

  if (elapsedSeconds < 5) {
    return 'updated just now';
  }
  if (elapsedSeconds < 60) {
    return `updated ${elapsedSeconds}s ago`;
  }

  const elapsedMinutes = Math.floor(elapsedSeconds / 60);
  if (elapsedMinutes < 60) {
    return `updated ${elapsedMinutes}m ago`;
  }

  const elapsedHours = Math.floor(elapsedMinutes / 60);
  return `updated ${elapsedHours}h ago`;
};

const getFreshnessToneClasses = (
  updatedAtMs?: number
): { text: string; dot: string; pulse: boolean } => {
  const elapsedSeconds = getFreshnessElapsedSeconds(updatedAtMs);
  if (elapsedSeconds === null) {
    return {
      text: 'text-slate-500',
      dot: 'bg-slate-500/70',
      pulse: false,
    };
  }

  if (elapsedSeconds < 10) {
    return {
      text: 'text-emerald-300',
      dot: 'bg-emerald-400',
      pulse: true,
    };
  }

  if (elapsedSeconds < 25) {
    return {
      text: 'text-amber-300',
      dot: 'bg-amber-400',
      pulse: false,
    };
  }

  return {
    text: 'text-rose-300',
    dot: 'bg-rose-400',
    pulse: false,
  };
};

const getFreshnessCardBorderClasses = (updatedAtMs?: number): string => {
  const elapsedSeconds = getFreshnessElapsedSeconds(updatedAtMs);

  if (elapsedSeconds === null || elapsedSeconds < 45) {
    return 'border-slate-700/60 hover:border-emerald-500/35';
  }

  if (elapsedSeconds < 90) {
    return 'border-amber-500/40 hover:border-amber-400/60';
  }

  return 'border-rose-500/45 hover:border-rose-400/70';
};

const toObject = (value: unknown): Record<string, unknown> =>
  typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : {};

const toFiniteNumber = (value: unknown, fallback = 0): number => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const toOptionalNumber = (value: unknown): number | null => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const toOptionalString = (value: unknown): string | null =>
  typeof value === 'string' && value.trim().length > 0 ? value.trim() : null;

type CapacityRiskModel = {
  label: string;
  detail: string;
  textClass: string;
  dotClass: string;
  chipClass: string;
};

const resolveCapacityRiskModel = (
  queueUtilizationPct: number | null,
  activeJobs: number,
  maxInProcessJobs: number | null,
  hasStatusError: boolean
): CapacityRiskModel => {
  if (hasStatusError) {
    return {
      label: 'unknown',
      detail: 'status unavailable',
      textClass: 'text-slate-300',
      dotClass: 'bg-slate-400',
      chipClass: 'border-slate-600/70 bg-slate-700/40',
    };
  }

  const inProcessUtilization =
    maxInProcessJobs && maxInProcessJobs > 0 ? (activeJobs / maxInProcessJobs) * 100 : null;
  const highestPressure = Math.max(queueUtilizationPct ?? 0, inProcessUtilization ?? 0);

  if (highestPressure >= 85) {
    return {
      label: 'critical',
      detail: 'capacity near max',
      textClass: 'text-rose-300',
      dotClass: 'bg-rose-400',
      chipClass: 'border-rose-500/45 bg-rose-500/10',
    };
  }

  if (highestPressure >= 60) {
    return {
      label: 'elevated',
      detail: 'watch queue pressure',
      textClass: 'text-amber-300',
      dotClass: 'bg-amber-400',
      chipClass: 'border-amber-500/45 bg-amber-500/10',
    };
  }

  return {
    label: 'healthy',
    detail: 'headroom available',
    textClass: 'text-emerald-300',
    dotClass: 'bg-emerald-400',
    chipClass: 'border-emerald-500/40 bg-emerald-500/10',
  };
};

export const BacktestsPage: React.FC<BacktestsPageProps> = ({ view = 'dashboard' }) => {
  const getEnvelopeField = (payload: Record<string, unknown>, key: string): unknown => {
    const nested = payload.data;
    if (nested && typeof nested === 'object' && nested !== null) {
      const nestedRecord = nested as Record<string, unknown>;
      if (key in nestedRecord) {
        return nestedRecord[key];
      }
    }
    return payload[key];
  };

  const queryClient = useQueryClient();
  const strategiesQuery = useQuery({
    queryKey: ['strategies', 'lookup'],
    queryFn: async (): Promise<StrategyRef[]> => {
      const response = await api.listStrategies(0, 500);
      return Array.isArray(response.data?.strategies)
        ? (response.data?.strategies as StrategyRef[])
        : [];
    },
    staleTime: 60_000,
  });

  const backtestsQuery = useQuery({
    queryKey: ['backtests', 'intelligence'],
    queryFn: async (): Promise<BacktestRun[]> => {
      const response = await api.listBacktests(0, 50);
      return extractBacktestRuns(response);
    },
    staleTime: 10_000,
    refetchInterval: (query) =>
      (query.state.data ?? []).some((run) => isActiveBacktestRun(run as BacktestRun))
        ? 8_000
        : false,
    refetchIntervalInBackground: false,
  });
  const activeRunCountForPolling = useMemo(
    () => (backtestsQuery.data ?? []).filter((run) => isActiveBacktestRun(run)).length,
    [backtestsQuery.data]
  );
  const systemStatusQuery = useQuery({
    queryKey: ['system-status', 'backtest-capacity'],
    queryFn: async () => {
      const status = await enhancedApiClient.getSystemStatus();
      return toObject(status);
    },
    staleTime: 10_000,
    refetchInterval: activeRunCountForPolling > 0 ? 10_000 : 30_000,
    refetchIntervalInBackground: false,
  });
  const backtestCapacity = useMemo(() => {
    const payload = toObject(systemStatusQuery.data);
    const runtime = toObject(payload.backtest_runtime);
    const limits = toObject(payload.backtest_limits);
    const botDBSync = toObject(payload.bot_db_sync);

    const queueDepth = toFiniteNumber(runtime.queue_depth, 0);
    const activeJobs = toFiniteNumber(runtime.active_jobs, 0);
    const totalRuns = toFiniteNumber(runtime.total_runs, 0);
    const maxQueueDepth = toOptionalNumber(limits.max_queue_depth);
    const maxActiveGlobal = toOptionalNumber(limits.max_active_runs_global);
    const maxInProcessJobs = toOptionalNumber(limits.max_in_process_jobs);
    const maxPerUser = toOptionalNumber(limits.max_active_runs_per_user);
    const retryAfterSeconds = toOptionalNumber(limits.retry_after_seconds);
    const staleHeartbeatSeconds = toOptionalNumber(limits.stale_heartbeat_seconds);
    const botDBSyncActive = Boolean(botDBSync.active);
    const botDBSyncRemainingSeconds = toOptionalNumber(botDBSync.remaining_seconds);
    const botDBSyncState = toOptionalString(botDBSync.state);

    const queueUtilizationPct =
      maxQueueDepth && maxQueueDepth > 0
        ? Math.max(0, Math.min(100, (queueDepth / maxQueueDepth) * 100))
        : null;

    return {
      queueDepth,
      activeJobs,
      totalRuns,
      maxQueueDepth,
      maxActiveGlobal,
      maxInProcessJobs,
      maxPerUser,
      retryAfterSeconds,
      staleHeartbeatSeconds,
      queueUtilizationPct,
      botDBSyncActive,
      botDBSyncRemainingSeconds,
      botDBSyncState,
    };
  }, [systemStatusQuery.data]);

  const strategiesById = useMemo(
    () =>
      new Map(
        (strategiesQuery.data ?? [])
          .filter((strategy) => Number.isInteger(strategy.id) && strategy.id > 0)
          .map((strategy) => [strategy.id, strategy.name])
      ),
    [strategiesQuery.data]
  );

  const intelligence = useMemo(
    () => buildIntelligence(backtestsQuery.data ?? [], strategiesById),
    [backtestsQuery.data, strategiesById]
  );
  const activeRunsQuickAccess = useMemo(
    () =>
      (backtestsQuery.data ?? [])
        .filter((run) => isActiveBacktestRun(run))
        .sort(
          (left, right) =>
            new Date(right.created_at || 0).getTime() - new Date(left.created_at || 0).getTime()
        )
        .slice(0, 6),
    [backtestsQuery.data]
  );
  const activeRunLiveStatusQueries = useQueries({
    queries: activeRunsQuickAccess.map((run) => ({
      queryKey: ['backtests', 'status', run.run_id, 'quick-access'],
      queryFn: async () => {
        const response = await api.getBacktestStatus(run.run_id);
        const payload = response as unknown as Record<string, unknown>;
        const progressCandidate = getEnvelopeField(payload, 'progress_pct');
        const fallbackProgressCandidate = getEnvelopeField(payload, 'progress_percent');
        const legacyProgressCandidate = getEnvelopeField(payload, 'progress');
        const updatedAtMs =
          parseTimestampMs(getEnvelopeField(payload, 'updated_at')) ??
          parseTimestampMs(payload.timestamp) ??
          Date.now();

        return {
          status: String(getEnvelopeField(payload, 'status') || run.status || 'pending'),
          progressPct: safeNumber(
            progressCandidate ?? fallbackProgressCandidate ?? legacyProgressCandidate,
            Number.NaN
          ),
          updatedAtMs,
        };
      },
      staleTime: 6_000,
      refetchInterval: 7_000,
      refetchIntervalInBackground: false,
      retry: 1,
      enabled: Boolean(run.run_id),
    })),
  });
  const activeRunSummaryQueries = useQueries({
    queries: activeRunsQuickAccess.map((run) => ({
      queryKey: ['backtests', 'analytics-summary', run.run_id, 'quick-access'],
      queryFn: async () => {
        const response = await api.getBacktestAnalyticsSummary(run.run_id);
        const payload = response as unknown as Record<string, unknown>;
        const totalPnlCandidate = getEnvelopeField(payload, 'total_pnl_usd');
        const totalTradesCandidate = getEnvelopeField(payload, 'total_trades');
        const winRateCandidate = getEnvelopeField(payload, 'win_rate');
        return {
          totalPnlUsd: safeNumber(totalPnlCandidate, Number.NaN),
          totalTrades: safeNumber(totalTradesCandidate, Number.NaN),
          winRate: safeNumber(winRateCandidate, Number.NaN),
        };
      },
      staleTime: 12_000,
      refetchInterval: 12_000,
      refetchIntervalInBackground: false,
      retry: 1,
      enabled: Boolean(run.run_id),
    })),
  });
  const activeRunLiveById = useMemo(() => {
    const lookup = new Map<
      string,
      {
        status?: string;
        progressPct?: number;
        updatedAtMs?: number;
        isFetching: boolean;
        totalPnlUsd?: number;
        totalTrades?: number;
        winRate?: number;
      }
    >();

    activeRunsQuickAccess.forEach((run, index) => {
      const query = activeRunLiveStatusQueries[index];
      const summaryQuery = activeRunSummaryQueries[index];
      const progressValue = query?.data?.progressPct;
      const normalizedProgress =
        typeof progressValue === 'number' && Number.isFinite(progressValue)
          ? Math.max(0, Math.min(100, progressValue))
          : undefined;

      lookup.set(run.run_id, {
        status: query?.data?.status,
        progressPct: normalizedProgress,
        updatedAtMs: query?.data?.updatedAtMs,
        isFetching: Boolean(query?.isFetching),
        totalPnlUsd:
          typeof summaryQuery?.data?.totalPnlUsd === 'number' &&
          Number.isFinite(summaryQuery.data.totalPnlUsd)
            ? summaryQuery.data.totalPnlUsd
            : undefined,
        totalTrades:
          typeof summaryQuery?.data?.totalTrades === 'number' &&
          Number.isFinite(summaryQuery.data.totalTrades)
            ? summaryQuery.data.totalTrades
            : undefined,
        winRate:
          typeof summaryQuery?.data?.winRate === 'number' &&
          Number.isFinite(summaryQuery.data.winRate)
            ? summaryQuery.data.winRate
            : undefined,
      });
    });

    return lookup;
  }, [activeRunsQuickAccess, activeRunLiveStatusQueries, activeRunSummaryQueries]);
  const capacityPanelRef = useRef<HTMLDivElement>(null);
  const scrollToCapacityPanel = () =>
    capacityPanelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });

  const capacityRisk = useMemo(
    () =>
      resolveCapacityRiskModel(
        backtestCapacity.queueUtilizationPct,
        backtestCapacity.activeJobs,
        backtestCapacity.maxInProcessJobs,
        systemStatusQuery.isError
      ),
    [
      backtestCapacity.queueUtilizationPct,
      backtestCapacity.activeJobs,
      backtestCapacity.maxInProcessJobs,
      systemStatusQuery.isError,
    ]
  );
  const backtestIntelRequest = useMemo(
    () => buildBacktestIntelRequest(intelligence.topRuns, 1),
    [intelligence.topRuns]
  );
  const strategyColumns = useMemo<TerminalColumn<StrategyAggregate>[]>(
    () => [
      {
        key: 'strategy',
        label: 'Strategy / Setup',
        sortable: true,
        sortValue: (row) => row.label,
        render: (row) => (
          <div>
            <p className="font-medium text-white">{row.label}</p>
            <p className="mt-1 text-xs text-slate-500">
              {row.completedRuns} completed
              {row.activeRuns > 0 ? ` · ${row.activeRuns} active` : ''}
              {row.lastRunAt ? ` · last run ${formatDateTime(row.lastRunAt)}` : ''}
            </p>
          </div>
        ),
      },
      {
        key: 'runs',
        label: 'Runs',
        align: 'right',
        sortable: true,
        sortValue: (row) => row.totalRuns,
        render: (row) => (
          <div>
            <p className="font-semibold text-slate-100">{row.totalRuns}</p>
            <p className="mt-1 text-xs text-slate-500">total observed</p>
          </div>
        ),
      },
      {
        key: 'pnl',
        label: 'Total P&L',
        align: 'right',
        sortable: true,
        sortValue: (row) => row.totalPnl,
        render: (row) => (
          <div>
            <p
              className={`font-semibold ${row.totalPnl >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}
            >
              {formatCurrency(row.totalPnl)}
            </p>
            <p className="mt-1 text-xs text-slate-500">avg {formatCurrency(row.avgPnl)}</p>
          </div>
        ),
      },
      {
        key: 'sharpe',
        label: 'Sharpe',
        align: 'right',
        sortable: true,
        sortValue: (row) => row.avgSharpe,
        render: (row) => (
          <div>
            <p className="font-semibold text-slate-100">{row.avgSharpe.toFixed(2)}</p>
            <p className="mt-1 text-xs text-slate-500">
              drawdown {formatPercent(row.avgDrawdownPct)}
            </p>
          </div>
        ),
      },
      {
        key: 'winrate',
        label: 'Win Rate',
        align: 'right',
        sortable: true,
        sortValue: (row) => row.avgWinRatePct,
        render: (row) => (
          <div>
            <p className="font-semibold text-slate-100">{formatPercent(row.avgWinRatePct)}</p>
            <p className="mt-1 text-xs text-slate-500">
              profitable {formatPercent(row.profitabilityRatePct)}
            </p>
          </div>
        ),
      },
    ],
    []
  );

  if (view === 'new') {
    return (
      <PageContainer size="wide" className="space-y-6">
        <section className="operator-hero px-6 py-6 sm:px-8 sm:py-8">
          <div className="relative grid gap-6 xl:grid-cols-[1.15fr,0.85fr]">
            <div>
              <div className="surface-label">
                <PlusCircle className="h-3.5 w-3.5" />
                New Backtest
              </div>
              <h1 className="mt-5 max-w-3xl text-3xl font-bold tracking-tight text-white sm:text-4xl">
                Create a focused validation run before a strategy reaches Bots.
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">
                Keep setup and launch separate from analytics. Pick a strategy/configuration, define
                the historical window, and start the run from one purpose-built page.
              </p>
            </div>
            <div className="operator-mini-grid">
              <div className="operator-hero-panel px-4 py-4">
                <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Step</p>
                <p className="mt-2 text-xl font-semibold text-white">Validate</p>
                <p className="mt-1 text-xs text-slate-500">Before deployment</p>
              </div>
              <div className="operator-hero-panel px-4 py-4">
                <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                  Active runs
                </p>
                <p className="mt-2 text-xl font-semibold text-white">
                  {backtestsQuery.isLoading ? '—' : intelligence.activeRuns}
                </p>
                <p className="mt-1 text-xs text-slate-500">Soft-refreshed from backend</p>
              </div>
            </div>
          </div>
        </section>

        <BacktestWorkflowCards />

        <section className="operator-section-card overflow-hidden">
          <div className="flex flex-col gap-3 border-b border-slate-800/80 px-5 py-5 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-xl font-semibold text-white">Backtest setup</h2>
              <p className="mt-1 text-sm leading-6 text-slate-400">
                Launch a historical run here. Results and ranking stay on the dashboard and archive
                pages so this form stays easy to scan.
              </p>
            </div>
            <Link
              to="/backtests/runs"
              className="premium-button premium-button-secondary px-4 py-2 text-sm"
            >
              View runs
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
          <BacktestRunner
            onBacktestComplete={() => {
              void queryClient.invalidateQueries({ queryKey: ['backtests'] });
            }}
          />
        </section>
      </PageContainer>
    );
  }

  if (backtestsQuery.isLoading) {
    return (
      <PageContainer size="wide" className="space-y-6">
        <section className="operator-hero px-6 py-6 sm:px-8 sm:py-8" aria-busy="true">
          <div className="relative grid gap-6 xl:grid-cols-[1.15fr,0.85fr]">
            <div>
              <div className="skeleton h-5 w-40 rounded-full" />
              <div className="skeleton mt-5 h-9 max-w-2xl rounded" />
              <div className="skeleton mt-3 h-4 max-w-xl rounded" />
              <div className="skeleton mt-2 h-4 max-w-lg rounded" />
              <div className="mt-5 flex flex-wrap gap-3">
                <div className="skeleton h-8 w-32 rounded-full" />
                <div className="skeleton h-8 w-48 rounded-full" />
                <div className="skeleton h-8 w-56 rounded-full" />
              </div>
            </div>
            <div className="operator-mini-grid">
              {Array.from({ length: 4 }).map((_, index) => (
                <div key={index} className="operator-hero-panel px-4 py-4">
                  <div className="skeleton h-3 w-20 rounded" />
                  <div className="skeleton mt-3 h-7 w-16 rounded" />
                  <div className="skeleton mt-2 h-3 w-24 rounded" />
                </div>
              ))}
            </div>
          </div>
        </section>
        <section
          className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4"
          aria-hidden="true"
        >
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="operator-stat-card p-5">
              <div className="skeleton h-8 w-8 rounded-xl" />
              <div className="skeleton mt-4 h-8 w-28 rounded" />
              <div className="skeleton mt-2 h-3 w-36 rounded" />
            </div>
          ))}
        </section>
      </PageContainer>
    );
  }

  if (backtestsQuery.isError) {
    const message =
      backtestsQuery.error instanceof Error
        ? backtestsQuery.error.message
        : 'Failed to load backtest intelligence.';

    return (
      <PageContainer size="wide" className="space-y-6">
        <div className="rounded-2xl border border-red-700/60 bg-red-950/30 p-6">
          <h1 className="text-xl font-semibold text-white">Backtest Intelligence Unavailable</h1>
          <p className="mt-2 text-sm text-red-200">{message}</p>
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => void backtestsQuery.refetch()}
              className="inline-flex items-center gap-2 rounded-lg border border-red-600/50 bg-red-900/30 px-4 py-2 text-sm font-medium text-red-100 transition hover:bg-red-900/50"
            >
              Retry backtest load
            </button>
            <Link
              to="/backtests/new"
              className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900/60 px-4 py-2 text-sm font-medium text-slate-100 transition hover:border-slate-500"
            >
              New backtest
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              to="/dashboard"
              className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900/60 px-4 py-2 text-sm font-medium text-slate-100 transition hover:border-slate-500"
            >
              Return to dashboard
            </Link>
          </div>
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer size="wide" className="space-y-6">
      <section className="operator-hero px-6 py-6 sm:px-8 sm:py-8">
        <div className="relative grid gap-6 xl:grid-cols-[1.15fr,0.85fr]">
          <div>
            <div className="surface-label">
              {view === 'runs' ? (
                <ListChecks className="h-3.5 w-3.5" />
              ) : (
                <Sparkles className="h-3.5 w-3.5" />
              )}
              {view === 'runs' ? 'Backtest Runs' : 'Backtest Dashboard'}
            </div>
            <h1 className="mt-5 max-w-3xl text-3xl font-bold tracking-tight text-white sm:text-4xl">
              {view === 'runs'
                ? 'Review every historical run without crowding the analytics dashboard.'
                : 'See validation quality, then decide which strategy deserves trust.'}
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">
              {view === 'runs'
                ? 'This archive is for run-by-run inspection, progress, and report entry points. Use the dashboard for high-level decision stats.'
                : 'This dashboard is tuned for validation decisions: live activity, weighted quality metrics, strategy ranking, and promotion guidance.'}
            </p>
            <div className="mt-5 flex flex-wrap gap-3">
              <div className="operator-status-pill" data-tone="accent">
                <Activity className="h-3.5 w-3.5" />
                {intelligence.activeRuns > 0
                  ? `${intelligence.activeRuns} active run${intelligence.activeRuns === 1 ? '' : 's'}`
                  : 'No active runs'}
              </div>
              <div className="operator-status-pill" data-tone="positive">
                <Award className="h-3.5 w-3.5" />
                {formatPercent(intelligence.profitableRatePct)} profitable completed runs
              </div>
              <div className="operator-status-pill" data-tone="warning">
                <ShieldCheck className="h-3.5 w-3.5" />
                Drawdown discipline stays weighted in rankings
              </div>
            </div>
          </div>

          <div className="operator-mini-grid">
            <div className="operator-hero-panel px-4 py-4">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Runs</p>
              <p className="mt-2 text-xl font-semibold text-white">{intelligence.totalRuns}</p>
              <p className="mt-1 text-xs text-slate-500">All loaded backtests</p>
            </div>
            <div className="operator-hero-panel px-4 py-4">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Completed</p>
              <p className="mt-2 text-xl font-semibold text-white">{intelligence.completedRuns}</p>
              <p className="mt-1 text-xs text-slate-500">Eligible for ranking</p>
            </div>
            <div className="operator-hero-panel px-4 py-4">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                Tracked setups
              </p>
              <p className="mt-2 text-xl font-semibold text-white">
                {intelligence.strategies.length}
              </p>
              <p className="mt-1 text-xs text-slate-500">Named strategy groups</p>
            </div>
            <div className="operator-hero-panel px-4 py-4">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                Average Sharpe
              </p>
              <p className="mt-2 text-xl font-semibold text-white">
                {intelligence.avgSharpe.toFixed(2)}
              </p>
              <p className="mt-1 text-xs text-slate-500">Completed runs only</p>
            </div>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Cumulative P&L"
          value={formatCurrency(intelligence.totalPnl)}
          hint="Across completed runs"
          icon={<TrendingUp className="h-5 w-5" />}
        />
        <StatCard
          label="Profitable Runs"
          value={formatPercent(intelligence.profitableRatePct)}
          hint={`${intelligence.profitableRuns} of ${intelligence.completedRuns || 0} completed runs finished positive`}
          icon={<Target className="h-5 w-5" />}
        />
        <StatCard
          label="Average Sharpe"
          value={intelligence.avgSharpe.toFixed(2)}
          hint="Higher means better risk-adjusted return"
          icon={<BarChart3 className="h-5 w-5" />}
        />
        <StatCard
          label="Average Drawdown"
          value={formatPercent(intelligence.avgDrawdownPct)}
          hint="Lower is safer"
          icon={<ShieldCheck className="h-5 w-5" />}
        />
      </section>

      {view === 'dashboard' && <BacktestWorkflowCards />}

      {view === 'dashboard' && (
        <>
          <section className="grid grid-cols-1 gap-4 xl:grid-cols-3">
            <InsightCard
              title="Best Performing Strategy"
              icon={<Award className="h-5 w-5 text-amber-300" />}
              aggregate={intelligence.bestStrategy}
              accent="bg-amber-500/10"
              secondary={
                intelligence.bestStrategy && intelligence.bestStrategy.totalPnl >= 0
                  ? 'text-green-400'
                  : 'text-red-400'
              }
            />
            <InsightCard
              title="Safest Strategy"
              icon={<ShieldCheck className="h-5 w-5 text-emerald-300" />}
              aggregate={intelligence.safestStrategy}
              accent="bg-emerald-500/10"
              secondary={
                intelligence.safestStrategy && intelligence.safestStrategy.totalPnl >= 0
                  ? 'text-green-400'
                  : 'text-red-400'
              }
            />
            <InsightCard
              title="Most Consistent Strategy"
              icon={<Layers3 className="h-5 w-5 text-cyan-300" />}
              aggregate={intelligence.mostConsistentStrategy}
              accent="bg-cyan-500/10"
              secondary={
                intelligence.mostConsistentStrategy &&
                intelligence.mostConsistentStrategy.totalPnl >= 0
                  ? 'text-green-400'
                  : 'text-red-400'
              }
            />
          </section>

          <CodexAssetIntelStrip
            title="Assets Behind Your Top Runs"
            request={backtestIntelRequest}
          />
        </>
      )}

      {view === 'dashboard' && (
        <section className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,.9fr)]">
          <TerminalDataGrid
            title="Strategy leaderboard"
            subtitle="Sortable ranking weighted for profitability, Sharpe, consistency, and drawdown discipline."
            rows={intelligence.strategies}
            columns={strategyColumns}
            rowKey={(row) => row.key}
            searchPlaceholder="Search strategy names or setups"
            getSearchText={(row) =>
              [row.label, String(row.strategyId ?? ''), String(row.totalRuns)].join(' ')
            }
            metrics={[
              {
                label: 'Ranked',
                value: intelligence.strategies.length,
                detail: 'strategy groups',
              },
              {
                label: 'Best P&L',
                value: intelligence.bestStrategy
                  ? formatCurrency(intelligence.bestStrategy.totalPnl)
                  : '—',
                detail: intelligence.bestStrategy?.label || 'awaiting completed runs',
                tone:
                  intelligence.bestStrategy && intelligence.bestStrategy.totalPnl >= 0
                    ? 'positive'
                    : 'default',
              },
              {
                label: 'Safest Drawdown',
                value: intelligence.safestStrategy
                  ? formatPercent(intelligence.safestStrategy.avgDrawdownPct)
                  : '—',
                detail: intelligence.safestStrategy?.label || 'awaiting drawdown data',
                tone: 'accent',
              },
              {
                label: 'Avg Sharpe',
                value: intelligence.avgSharpe.toFixed(2),
                detail: 'completed runs only',
              },
            ]}
            liveBadge={
              <span
                className="operator-status-pill"
                data-tone={intelligence.activeRuns > 0 ? 'accent' : 'positive'}
              >
                {intelligence.activeRuns > 0 ? `${intelligence.activeRuns} live` : 'Stable'}
              </span>
            }
            defaultSortKey="pnl"
            emptyState={
              <div className="rounded-2xl border border-slate-800 bg-slate-950/45 p-6 text-sm text-slate-400">
                No completed backtests yet. Launch your first run from this Backtests desk and the
                leaderboard will populate here.
              </div>
            }
          />

          <div className="space-y-6">
            <div ref={capacityPanelRef} className="operator-section-card p-5">
              <div className="mb-4 flex items-center gap-3">
                <div className="rounded-xl bg-violet-500/10 p-2 text-violet-300">
                  <Layers3 className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-white">Backtest Capacity</h2>
                  <p className="text-sm text-slate-400">
                    Live queue pressure and admission thresholds.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-slate-500">Queue depth</p>
                  <p className="font-semibold text-slate-100">
                    {backtestCapacity.queueDepth}
                    {backtestCapacity.maxQueueDepth && backtestCapacity.maxQueueDepth > 0
                      ? ` / ${backtestCapacity.maxQueueDepth}`
                      : ''}
                  </p>
                </div>
                <div>
                  <p className="text-slate-500">Active jobs</p>
                  <p className="font-semibold text-slate-100">
                    {backtestCapacity.activeJobs}
                    {backtestCapacity.maxInProcessJobs && backtestCapacity.maxInProcessJobs > 0
                      ? ` / ${backtestCapacity.maxInProcessJobs}`
                      : ''}
                  </p>
                </div>
                <div>
                  <p className="text-slate-500">Global active cap</p>
                  <p className="font-semibold text-slate-100">
                    {backtestCapacity.maxActiveGlobal && backtestCapacity.maxActiveGlobal > 0
                      ? backtestCapacity.maxActiveGlobal
                      : 'unbounded'}
                  </p>
                </div>
                <div>
                  <p className="text-slate-500">Per-user active cap</p>
                  <p className="font-semibold text-slate-100">
                    {backtestCapacity.maxPerUser && backtestCapacity.maxPerUser > 0
                      ? backtestCapacity.maxPerUser
                      : 'backend managed'}
                  </p>
                </div>
              </div>

              {backtestCapacity.queueUtilizationPct !== null && (
                <div className="mt-4">
                  <div className="mb-1 flex items-center justify-between text-xs text-slate-400">
                    <span>Queue utilization</span>
                    <span>{backtestCapacity.queueUtilizationPct.toFixed(0)}%</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-slate-700/80">
                    <div
                      className={`h-1.5 rounded-full transition-all duration-500 ${
                        backtestCapacity.queueUtilizationPct >= 85
                          ? 'bg-rose-400'
                          : backtestCapacity.queueUtilizationPct >= 60
                            ? 'bg-amber-400'
                            : 'bg-emerald-400'
                      }`}
                      style={{ width: `${backtestCapacity.queueUtilizationPct}%` }}
                    />
                  </div>
                </div>
              )}

              <div className="mt-4 space-y-1 text-xs text-slate-500">
                <p>
                  Retry-after:{' '}
                  <span className="text-slate-300">
                    {backtestCapacity.retryAfterSeconds && backtestCapacity.retryAfterSeconds > 0
                      ? `${backtestCapacity.retryAfterSeconds}s`
                      : 'server default'}
                  </span>
                </p>
                <p>
                  Stale heartbeat threshold:{' '}
                  <span className="text-slate-300">
                    {backtestCapacity.staleHeartbeatSeconds &&
                    backtestCapacity.staleHeartbeatSeconds > 0
                      ? `${backtestCapacity.staleHeartbeatSeconds}s`
                      : 'default'}
                  </span>
                </p>
                <p>
                  Runtime snapshot freshness:{' '}
                  <span className="text-slate-300">
                    {systemStatusQuery.isFetching ? 'updating…' : 'live poll'}
                  </span>
                </p>
              </div>
            </div>

            <div className="operator-section-card p-5">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="rounded-xl bg-emerald-500/10 p-2 text-emerald-300">
                    <Activity className="h-5 w-5" />
                  </div>
                  <div>
                    <h2 className="text-lg font-semibold text-white">Active Runs Quick Access</h2>
                    <p className="text-sm text-slate-400">
                      Open live backtests instantly without leaving the dashboard.
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={scrollToCapacityPanel}
                    className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] transition hover:brightness-110 ${capacityRisk.textClass} ${capacityRisk.chipClass}`}
                    title={`Capacity risk: ${capacityRisk.label} — click to view panel`}
                  >
                    <span className={`h-1.5 w-1.5 rounded-full ${capacityRisk.dotClass}`} />
                    Capacity {capacityRisk.label}
                  </button>
                  <button
                    type="button"
                    onClick={scrollToCapacityPanel}
                    className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${
                      backtestCapacity.botDBSyncActive
                        ? 'border-amber-500/45 bg-amber-500/10 text-amber-300'
                        : 'border-emerald-500/35 bg-emerald-500/10 text-emerald-300'
                    } transition hover:brightness-110`}
                    title={
                      backtestCapacity.botDBSyncActive
                        ? `DB sync cooldown active (${Math.ceil(backtestCapacity.botDBSyncRemainingSeconds ?? 0)}s remaining) · state ${backtestCapacity.botDBSyncState || 'unknown'} — click to view capacity panel`
                        : `DB sync ${backtestCapacity.botDBSyncState || 'ok'} — click to view capacity panel`
                    }
                    aria-label="Scroll to backtest capacity panel"
                  >
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${
                        backtestCapacity.botDBSyncActive ? 'bg-amber-400' : 'bg-emerald-400'
                      }`}
                    />
                    {backtestCapacity.botDBSyncActive
                      ? `DB sync cooldown · ${Math.ceil(backtestCapacity.botDBSyncRemainingSeconds ?? 0)}s`
                      : 'DB sync stable'}
                  </button>
                  <Link
                    to="/backtests/runs"
                    className="text-xs font-semibold uppercase tracking-[0.14em] text-cyan-300 hover:text-cyan-200"
                  >
                    View all runs
                  </Link>
                </div>
              </div>

              {activeRunsQuickAccess.length === 0 ? (
                <p className="text-sm text-slate-400">
                  No active runs right now. Start a new backtest and it will appear here.
                </p>
              ) : (
                <div className="space-y-3">
                  {activeRunsQuickAccess.map((run) => {
                    const live = activeRunLiveById.get(run.run_id);
                    const normalizedStatus = String(live?.status || run.status || 'pending')
                      .trim()
                      .toUpperCase();
                    const listProgress = safeNumber(
                      (
                        run as {
                          progress_pct?: number;
                          progress_percent?: number;
                          progress?: number;
                        }
                      ).progress_pct ??
                        (run as { progress_percent?: number }).progress_percent ??
                        (run as { progress?: number }).progress,
                      Number.NaN
                    );
                    const resolvedProgress =
                      typeof live?.progressPct === 'number' && Number.isFinite(live.progressPct)
                        ? live.progressPct
                        : Number.isFinite(listProgress)
                          ? Math.max(0, Math.min(100, listProgress))
                          : null;
                    const progressBarWidth = resolvedProgress !== null ? resolvedProgress : 2;
                    const progressLabel =
                      resolvedProgress !== null
                        ? `${resolvedProgress.toFixed(0)}%`
                        : live?.isFetching
                          ? '...'
                          : '—';
                    const freshnessLabel = formatFreshnessAge(live?.updatedAtMs);
                    const freshnessTone = getFreshnessToneClasses(live?.updatedAtMs);
                    const freshnessCardBorder = getFreshnessCardBorderClasses(live?.updatedAtMs);
                    const pnlClass =
                      typeof live?.totalPnlUsd === 'number'
                        ? live.totalPnlUsd >= 0
                          ? 'text-emerald-300'
                          : 'text-rose-300'
                        : 'text-slate-400';

                    return (
                      <Link
                        key={run.run_id}
                        to={`/backtest/${run.run_id}`}
                        className={`block rounded-xl border bg-slate-900/50 p-4 transition hover:bg-slate-900/80 ${freshnessCardBorder}`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-white">
                              {run.name || run.run_id}
                            </p>
                            <p className="mt-1 text-xs text-slate-500">
                              started {formatDateTime(run.created_at)}
                            </p>
                            {freshnessLabel ? (
                              <p
                                className={`mt-1 inline-flex items-center gap-1.5 text-[11px] ${freshnessTone.text}`}
                              >
                                <span
                                  className={`h-1.5 w-1.5 rounded-full ${freshnessTone.dot} ${freshnessTone.pulse ? 'animate-pulse' : ''}`}
                                />
                                {freshnessLabel}
                              </p>
                            ) : null}
                          </div>
                          <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-cyan-200">
                            {normalizedStatus}
                          </span>
                        </div>

                        <div className="mt-3 flex items-center gap-2">
                          <div
                            className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-700/80"
                            role="progressbar"
                            aria-label={`Backtest ${run.name || run.run_id} progress`}
                            aria-valuemin={0}
                            aria-valuemax={100}
                            aria-valuenow={
                              resolvedProgress !== null ? Math.round(resolvedProgress) : undefined
                            }
                          >
                            <div
                              className="h-1.5 rounded-full bg-emerald-400 transition-all duration-500"
                              style={{ width: `${progressBarWidth}%` }}
                            />
                          </div>
                          <span className="w-12 text-right text-xs text-slate-300">
                            {progressLabel}
                          </span>
                        </div>

                        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-400">
                          <span className={pnlClass}>
                            P&amp;L:{' '}
                            {typeof live?.totalPnlUsd === 'number'
                              ? formatCurrency(live.totalPnlUsd)
                              : '—'}
                          </span>
                          <span>
                            Trades:{' '}
                            {typeof live?.totalTrades === 'number'
                              ? Math.max(0, Math.round(live.totalTrades))
                              : '—'}
                          </span>
                          <span>
                            Win Rate:{' '}
                            {typeof live?.winRate === 'number'
                              ? formatPercent(normalizePercent(live.winRate))
                              : '—'}
                          </span>
                        </div>
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="operator-section-card p-5">
              <div className="mb-4 flex items-center gap-3">
                <div className="rounded-xl bg-blue-500/10 p-2 text-blue-400">
                  <TrendingUp className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-white">Top Runs</h2>
                  <p className="text-sm text-slate-400">Best single-run outcomes so far.</p>
                </div>
              </div>

              {intelligence.topRuns.length === 0 ? (
                <p className="text-sm text-slate-400">
                  Top runs will appear after your first completed backtest.
                </p>
              ) : (
                <div className="space-y-3">
                  {intelligence.topRuns.map((run, index) => (
                    <Link
                      key={run.run_id}
                      to={`/backtest/${run.run_id}`}
                      className="block rounded-xl border border-slate-700/60 bg-slate-900/50 p-4 transition hover:border-blue-500/40 hover:bg-slate-900/80"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                              #{index + 1}
                            </span>
                            <span className="text-sm font-semibold text-white">
                              {run.name || run.run_id}
                            </span>
                          </div>
                          <p className="mt-1 text-xs text-slate-500">
                            {formatDateTime(run.created_at)}
                          </p>
                        </div>
                        <ChevronRight className="h-4 w-4 shrink-0 text-slate-500" />
                      </div>
                      <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
                        <div>
                          <p className="text-slate-500">P&amp;L</p>
                          <p
                            className={`font-semibold ${safeNumber(run.total_pnl) >= 0 ? 'text-green-400' : 'text-red-400'}`}
                          >
                            {formatCurrency(safeNumber(run.total_pnl))}
                          </p>
                        </div>
                        <div>
                          <p className="text-slate-500">Sharpe</p>
                          <p className="font-semibold text-slate-200">
                            {safeNumber(run.sharpe_ratio).toFixed(2)}
                          </p>
                        </div>
                        <div>
                          <p className="text-slate-500">Win Rate</p>
                          <p className="font-semibold text-slate-200">
                            {formatPercent(normalizePercent(run.win_rate))}
                          </p>
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>

            <div className="operator-section-card p-5">
              <div className="mb-4 flex items-center gap-3">
                <div className="rounded-xl bg-cyan-500/10 p-2 text-cyan-400">
                  <Activity className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-white">Operator Notes</h2>
                  <p className="text-sm text-slate-400">How to read these rankings safely.</p>
                </div>
              </div>
              <ul className="space-y-2 text-sm text-slate-300">
                <li>Only completed runs contribute to quality rankings.</li>
                <li>
                  Drawdown is treated as a risk penalty, so high-return but unstable setups won’t
                  dominate unfairly.
                </li>
                <li>
                  Strategies with more completed runs receive a confidence boost over single lucky
                  outliers.
                </li>
                <li>
                  Click any run below to inspect the full detailed report before promoting a setup
                  to live runtime.
                </li>
              </ul>
            </div>
          </div>
        </section>
      )}

      {view === 'runs' && (
        <section className="operator-section-card p-5 space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold text-white">All Backtests</h2>
              <p className="text-sm text-slate-400">
                Every run, with soft refresh behavior for active jobs and detail views one click
                away.
              </p>
            </div>
            <Link
              to="/backtests/compare"
              className="premium-button premium-button-secondary rounded-2xl px-4 py-2 text-sm"
            >
              Compare runs
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
          <BacktestList />
        </section>
      )}
    </PageContainer>
  );
};
