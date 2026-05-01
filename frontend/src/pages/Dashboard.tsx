/**
 * Dashboard – Premium redesign
 * ─ Hero greeting + live clock
 * ─ Animated KPI cards (8)
 * ─ TradingView cumulative PnL chart
 * ─ Active runtime monitor + recent activity
 */

import { useQuery } from '@tanstack/react-query';
import {
    Activity,
    AlertCircle,
    ArrowRight,
    BarChart2,
    Clock,
    Layers3,
    Newspaper,
    Play,
    Rocket,
    ShieldCheck,
    Sparkles,
    Target,
    TrendingDown,
    TrendingUp,
    Zap,
} from 'lucide-react';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import api, { classifyApiError } from '../api';
import { useBotInstances } from '../api/hooks';
import { CodexAssetIntelStrip } from '../components/CodexAssetIntelStrip';
import { CoinDeskNewsPanel } from '../components/CoinDeskNewsPanel';
import { CumulativePnlChart, type PnlPoint } from '../components/CumulativePnlChart';
import { PageContainer } from '../components/PageContainer';
import { SyncHealthPanel } from '../components/SyncHealthPanel';
import { EmptyState, InlineNotice } from '../components/ui/PlatformUI';
import {
    type BacktestRun,
    buildIntelligence,
    formatCurrency as formatIntelligenceCurrency,
    formatPercent as formatIntelligencePercent,
} from '../features/backtests/intelligence';
import {
    buildCodexAssetContextRequest,
    formatPct as formatCodexPct,
    formatUsd as formatCodexUsd,
} from '../features/codex/marketIntel';
import { useAuthStore } from '../store/auth';

// ── Types ─────────────────────────────────────────────────────────────────────

interface BacktestRunSummary extends BacktestRun {
  total_pnl: number;
  win_rate: number;
  total_trades: number;
  progress_pct?: number;
  current_pair?: string;
}

interface DashboardStats {
  total: number;
  completed: number;
  running: number;
  failed: number;
  totalPnl: number;
  bestWinRate: number;
  bestSharpe: number;
  totalTrades: number;
  avgPnlPerRun: number;
  activeRuns: BacktestRunSummary[];
  pnlTimeSeries: PnlPoint[];
}

interface RuntimeBotSummary {
  instance_id: string;
  status?: string;
  instance_name?: string;
  strategy?: string;
  error_message?: string;
  started_at?: string;
}

const DASHBOARD_STATS_TIMEOUT_MS = 30000;

// ── useCountUp ────────────────────────────────────────────────────────────────

function useCountUp(target: number, duration = 900): number {
  const [value, setValue] = useState(0);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    if (!Number.isFinite(target)) return;
    const start = Date.now();

    const tick = () => {
      const elapsed = Date.now() - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(target * eased);
      if (progress < 1) rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [target, duration]);

  return value;
}

// ── LiveClock ─────────────────────────────────────────────────────────────────

const LiveClock: React.FC = () => {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <span className="font-mono tabular-nums text-cyan-300">
      {now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
    </span>
  );
};

// ── KpiCard ───────────────────────────────────────────────────────────────────

interface KpiCardProps {
  label: string;
  value: string;
  subtitle?: string;
  icon: React.ReactNode;
  color: 'teal' | 'green' | 'red' | 'amber' | 'cyan' | 'emerald' | 'rose';
  trend?: 'up' | 'down' | 'neutral';
  animDelay?: number;
}

const colorMap: Record<KpiCardProps['color'], { border: string; bg: string; icon: string }> = {
  teal: { border: 'border-teal-500/30', bg: 'bg-teal-500/10', icon: 'text-teal-300' },
  green: { border: 'border-green-500/30', bg: 'bg-green-500/10', icon: 'text-green-400' },
  red: { border: 'border-red-500/30', bg: 'bg-red-500/10', icon: 'text-red-400' },
  amber: { border: 'border-amber-500/30', bg: 'bg-amber-500/10', icon: 'text-amber-400' },
  cyan: { border: 'border-cyan-500/30', bg: 'bg-cyan-500/10', icon: 'text-cyan-400' },
  emerald: { border: 'border-emerald-500/30', bg: 'bg-emerald-500/10', icon: 'text-emerald-400' },
  rose: { border: 'border-rose-500/30', bg: 'bg-rose-500/10', icon: 'text-rose-400' },
};

const KpiCard: React.FC<KpiCardProps> = ({
  label,
  value,
  subtitle,
  icon,
  color,
  trend,
  animDelay = 0,
}) => {
  const c = colorMap[color];
  return (
    <div
      className={`operator-stat-card border ${c.border} cursor-default p-5 transition-all duration-300 hover:border-cyan-500/20 hover:bg-slate-900/80 animate-fade-slide-up`}
      style={{ animationDelay: `${animDelay}ms` }}
    >
      <div className="mb-3 flex items-start justify-between">
        <div className={`rounded-lg p-2.5 ${c.bg}`}>
          <div className={c.icon}>{icon}</div>
        </div>
        {trend && trend !== 'neutral' && (
          <span
            className={`flex items-center gap-0.5 text-xs font-medium ${trend === 'up' ? 'text-green-400' : 'text-red-400'}`}
          >
            {trend === 'up' ? (
              <TrendingUp className="h-3.5 w-3.5" />
            ) : (
              <TrendingDown className="h-3.5 w-3.5" />
            )}
          </span>
        )}
      </div>
      <p className="text-[10px] uppercase text-slate-500">{label}</p>
      {value === '—' ? (
        <>
          <div className="skeleton mt-2 h-7 w-20 rounded" />
          {subtitle !== undefined && <div className="skeleton mt-2 h-2.5 w-24 rounded" />}
        </>
      ) : (
        <>
          <p className="mt-2 text-2xl font-bold text-white">{value}</p>
          {subtitle && <p className="mt-1 text-[11px] text-slate-500">{subtitle}</p>}
        </>
      )}
    </div>
  );
};

// ── ActiveRunCard ─────────────────────────────────────────────────────────────

const ActiveRunCard: React.FC<{ run: BacktestRunSummary }> = ({ run }) => {
  const pct = Math.min(100, Math.max(0, run.progress_pct ?? 0));
  const isRunning = run.status.toUpperCase() === 'RUNNING';
  return (
    <div className="operator-action-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <span className="relative flex h-2 w-2 shrink-0">
            {isRunning && (
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan-400 opacity-75" />
            )}
            <span
              className={`relative inline-flex h-2 w-2 rounded-full ${isRunning ? 'bg-cyan-400' : 'bg-amber-400'}`}
            />
          </span>
          <span className="truncate font-mono text-xs text-cyan-300">
            {(run.name || run.run_id).substring(0, 22)}
          </span>
        </div>
        <span className="ml-2 shrink-0 text-xs tabular-nums text-slate-400">
          {pct > 0 ? `${pct.toFixed(1)}%` : '…'}
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
        <div
          className="h-1.5 rounded-full bg-cyan-500 transition-all duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>
      {run.current_pair && (
        <p className="text-[11px] text-slate-400">
          Scanning: <span className="font-mono text-slate-200">{run.current_pair}</span>
        </p>
      )}
    </div>
  );
};

const StrategySpotlightCard: React.FC<{
  title: string;
  subtitle: string;
  href: string;
  icon: React.ReactNode;
  accentClass: string;
  titleValue?: string;
  primaryMetric?: string;
  secondaryMetric?: string;
  emptyMessage: string;
}> = ({
  title,
  subtitle,
  href,
  icon,
  accentClass,
  titleValue,
  primaryMetric,
  secondaryMetric,
  emptyMessage,
}) => (
  <div className="operator-section-card p-5">
    <div className="mb-4 flex items-start justify-between gap-3">
      <div className="flex items-center gap-3">
        <div className={`rounded-lg p-2.5 ${accentClass}`}>{icon}</div>
        <div>
          <p className="text-sm font-semibold text-white">{title}</p>
          <p className="text-xs text-slate-500">{subtitle}</p>
        </div>
      </div>
      <Link
        to={href}
        className="inline-flex items-center gap-1 text-xs font-medium text-cyan-300 transition hover:text-cyan-200"
      >
        Open
        <ArrowRight className="h-3.5 w-3.5" />
      </Link>
    </div>

    {titleValue ? (
      <>
        <p className="text-lg font-semibold text-white">{titleValue}</p>
        <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
          <div>
            <p className="text-slate-500">Primary</p>
            <p className="font-semibold text-slate-200">{primaryMetric}</p>
          </div>
          <div>
            <p className="text-slate-500">Secondary</p>
            <p className="font-semibold text-slate-200">{secondaryMetric}</p>
          </div>
        </div>
      </>
    ) : (
      <p className="text-sm text-slate-400">{emptyMessage}</p>
    )}
  </div>
);

// ── Helpers ───────────────────────────────────────────────────────────────────

const toRecord = (v: unknown): Record<string, unknown> =>
  v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {};

const normalizeRuntimeBots = (value: unknown): RuntimeBotSummary[] =>
  Array.isArray(value)
    ? value
        .map((item) => {
          const record = toRecord(item);
          const instanceId = typeof record.instance_id === 'string' ? record.instance_id : '';
          return {
            instance_id: instanceId,
            status: typeof record.status === 'string' ? record.status : undefined,
            instance_name:
              typeof record.instance_name === 'string' ? record.instance_name : undefined,
            strategy: typeof record.strategy === 'string' ? record.strategy : undefined,
            error_message:
              typeof record.error_message === 'string' ? record.error_message : undefined,
            started_at: typeof record.started_at === 'string' ? record.started_at : undefined,
          };
        })
        .filter((bot) => bot.instance_id.length > 0)
    : [];

const safeNum = (v: unknown, fallback = 0): number => {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
};

const normalizePercent = (value: unknown): number => {
  const numeric = safeNum(value, 0);
  return Math.abs(numeric) <= 1 ? numeric * 100 : numeric;
};

const parseTimestamp = (value: unknown): number | null => {
  if (typeof value !== 'string' || value.trim().length === 0) return null;
  const normalized = value.includes(' ') ? value.replace(' ', 'T') : value;
  const ms = Date.parse(normalized);
  return Number.isFinite(ms) ? ms : null;
};

const getRunTimestamp = (run: BacktestRunSummary): number | null => {
  const direct = parseTimestamp(run.created_at);
  if (direct !== null) return direct;

  const raw = run as unknown as Record<string, unknown>;
  return (
    parseTimestamp(raw.updated_at) ?? parseTimestamp(raw.start_date) ?? parseTimestamp(raw.end_date)
  );
};

const buildPnlSeries = (runs: BacktestRunSummary[]): PnlPoint[] => {
  const completed = runs.filter((r) => String(r.status ?? '').toUpperCase() === 'COMPLETED');
  const sorted = [...completed].sort((a, b) => {
    const ta = getRunTimestamp(a) ?? Number.MAX_SAFE_INTEGER;
    const tb = getRunTimestamp(b) ?? Number.MAX_SAFE_INTEGER;
    return ta - tb;
  });

  const pnlTimeSeries: PnlPoint[] = [];
  let cumulative = 0;
  const seenDates = new Set<string>();

  for (let i = 0; i < sorted.length; i += 1) {
    const r = sorted[i];
    const ts = getRunTimestamp(r);
    const fallbackTs = Date.now() - (sorted.length - i) * 24 * 60 * 60 * 1000;
    const dateStr = new Date(ts ?? fallbackTs).toISOString().substring(0, 10);
    cumulative += safeNum(r.total_pnl);

    if (seenDates.has(dateStr)) {
      const last = pnlTimeSeries[pnlTimeSeries.length - 1];
      if (last?.time === dateStr) last.value = parseFloat(cumulative.toFixed(2));
    } else {
      pnlTimeSeries.push({ time: dateStr, value: parseFloat(cumulative.toFixed(2)) });
      seenDates.add(dateStr);
    }
  }

  return pnlTimeSeries;
};

const buildDashboardStats = (runs: BacktestRunSummary[]): DashboardStats => {
  const norm = (s?: string) => String(s ?? '').toUpperCase();

  const completed = runs.filter((r) => norm(r.status) === 'COMPLETED');
  const running = runs.filter((r) => norm(r.status) === 'RUNNING' || norm(r.status) === 'PENDING');
  const failed = runs.filter((r) => norm(r.status) === 'FAILED' || norm(r.status) === 'CANCELLED');

  const totalPnl = completed.reduce((acc, r) => acc + safeNum(r.total_pnl), 0);
  const bestWinRate = completed.reduce((max, r) => Math.max(max, normalizePercent(r.win_rate)), 0);
  const bestSharpe = completed.reduce((max, r) => Math.max(max, safeNum(r.sharpe_ratio)), 0);
  const totalTrades = runs.reduce((acc, r) => acc + safeNum(r.total_trades), 0);
  const avgPnlPerRun = completed.length > 0 ? totalPnl / completed.length : 0;
  const pnlTimeSeries = buildPnlSeries(runs);

  return {
    total: runs.length,
    completed: completed.length,
    running: running.length,
    failed: failed.length,
    totalPnl,
    bestWinRate,
    bestSharpe,
    totalTrades,
    avgPnlPerRun,
    activeRuns: running,
    pnlTimeSeries,
  };
};

// ── Main Dashboard ────────────────────────────────────────────────────────────

export const DashboardPage: React.FC = () => {
  const { user } = useAuthStore();
  const [runs, setRuns] = useState<BacktestRunSummary[]>([]);
  const [stats, setStats] = useState<DashboardStats>({
    total: 0,
    completed: 0,
    running: 0,
    failed: 0,
    totalPnl: 0,
    bestWinRate: 0,
    bestSharpe: 0,
    totalTrades: 0,
    avgPnlPerRun: 0,
    activeRuns: [],
    pnlTimeSeries: [],
  });
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [statsWarning, setStatsWarning] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isComputingRef = useRef(false);
  const activeComputeIdRef = useRef(0);

  const computeStats = useCallback(async () => {
    if (isComputingRef.current) {
      return;
    }

    isComputingRef.current = true;
    const computeId = activeComputeIdRef.current + 1;
    activeComputeIdRef.current = computeId;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    try {
      const statsPromise = api.listBacktests(0, 25);
      const timeoutPromise = new Promise<Awaited<ReturnType<typeof api.listBacktests>>>(
        (_, reject) => {
          timeoutId = setTimeout(
            () => reject(new Error('Timed out while loading dashboard stats')),
            DASHBOARD_STATS_TIMEOUT_MS
          );
        }
      );

      const response = await Promise.race([statsPromise, timeoutPromise]);
      if (activeComputeIdRef.current !== computeId) {
        return;
      }
      const raw = toRecord(response);
      const rawData = toRecord(raw.data);

      const rawRuns: BacktestRunSummary[] = Array.isArray(rawData.backtests)
        ? (rawData.backtests as BacktestRunSummary[])
        : Array.isArray(raw.backtests)
          ? (raw.backtests as BacktestRunSummary[])
          : Array.isArray(rawData.runs)
            ? (rawData.runs as BacktestRunSummary[])
            : Array.isArray(raw.runs)
              ? (raw.runs as BacktestRunSummary[])
              : [];

      setRuns(rawRuns);
      setStats(buildDashboardStats(rawRuns));
      setStatsError(null);
      setStatsWarning(null);
    } catch (error) {
      if (activeComputeIdRef.current !== computeId) {
        return;
      }
      console.error('❌ Dashboard: failed to load stats', error);
      const classification = classifyApiError(error);
      if (classification.kind === 'transport') {
        setStatsError(
          'Backend service is unreachable from the browser. Verify API connectivity or Vite proxy setup.'
        );
      } else if (classification.statusCode === 401) {
        setStatsError('Your session appears to be unauthorized. Please sign in again.');
      } else if (error instanceof Error && error.message.toLowerCase().includes('timed out')) {
        // Non-fatal: backend is slow — keep last-good data visible, show warning badge only
        setStatsWarning('Backend is responding slowly — showing last available data.');
      } else {
        setStatsError(error instanceof Error ? error.message : 'Failed to load dashboard stats.');
      }
    } finally {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      if (activeComputeIdRef.current === computeId) {
        isComputingRef.current = false;
      }
      setStatsLoading(false);
    }
  }, []);

  useEffect(() => {
    void computeStats();
  }, [computeStats]);

  useEffect(() => {
    if (stats.running > 0 && !pollRef.current) {
      pollRef.current = setInterval(() => void computeStats(), 10000);
    } else if (stats.running === 0 && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [stats.running, computeStats]);

  // Animated counters
  const countTotal = useCountUp(stats.total);
  const countComplete = useCountUp(stats.completed);
  const countFailed = useCountUp(stats.failed);
  const countTrades = useCountUp(stats.totalTrades);

  const fmtPnl = (v: number) =>
    (v >= 0 ? '+' : '') + '$' + Math.abs(v).toLocaleString('en-US', { maximumFractionDigits: 2 });
  const fmtPct = (v: number) => v.toFixed(1) + '%';
  const fmtN = (v: number) => Math.round(v).toLocaleString('en-US');

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

  const pnlTimeSeries = useMemo(() => stats.pnlTimeSeries, [stats.pnlTimeSeries]);
  const pnlColor = stats.totalPnl >= 0 ? '#22c55e' : '#ef4444';

  const strategiesQuery = useQuery({
    queryKey: ['strategies', 'dashboard-lookup'],
    queryFn: async (): Promise<Array<{ id: number; name?: string; benchmark_symbol?: string }>> => {
      const response = await api.listStrategies(0, 500);
      return Array.isArray(response.data?.strategies)
        ? (response.data?.strategies as Array<{
            id: number;
            name?: string;
            benchmark_symbol?: string;
          }>)
        : [];
    },
    staleTime: 60_000,
  });

  const botsQuery = useBotInstances({ limit: 100 });
  const runtimeBots = useMemo(
    () => normalizeRuntimeBots(botsQuery.data?.data),
    [botsQuery.data?.data]
  );
  const runningRuntimeBots = runtimeBots.filter(
    (bot) => String(bot.status ?? '').toUpperCase() === 'RUNNING'
  );
  const degradedRuntimeBots = runtimeBots.filter((bot) =>
    ['FAILED', 'ERROR'].includes(String(bot.status ?? '').toUpperCase())
  );
  const transitioningRuntimeBots = runtimeBots.filter((bot) =>
    ['STARTING', 'STOPPING'].includes(String(bot.status ?? '').toUpperCase())
  );

  // Fetch how many strategy runtimes are currently live so the Active Now KPI
  // reflects real trading activity, not just active backtest runs.
  const strategyRuntimesQuery = useQuery({
    queryKey: ['strategy-runtimes', 'dashboard-active'],
    queryFn: async (): Promise<number> => {
      const strategies = strategiesQuery.data;
      if (!strategies || strategies.length === 0) return 0;
      const results = await Promise.allSettled(strategies.map((s) => api.getStrategyRuntime(s.id)));
      return results.filter(
        (r) =>
          r.status === 'fulfilled' &&
          String((r.value as { data?: { status?: string } }).data?.status ?? '').toLowerCase() ===
            'running'
      ).length;
    },
    enabled: (strategiesQuery.data?.length ?? 0) > 0,
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
  const runningStrategyCount = strategyRuntimesQuery.data ?? 0;
  const totalActiveCount = stats.running + runningStrategyCount + runningRuntimeBots.length;
  const countRunning = useCountUp(totalActiveCount);
  const intelligence = useMemo(() => buildIntelligence(runs, new Map<number, string>()), [runs]);
  const spotlightIntelRequest = useMemo(() => {
    const strategiesById = new Map(
      (strategiesQuery.data ?? [])
        .filter((strategy) => Number.isInteger(strategy.id) && strategy.id > 0)
        .map((strategy) => [strategy.id, strategy])
    );

    return buildCodexAssetContextRequest(
      [intelligence.bestStrategy, intelligence.safestStrategy, intelligence.mostConsistentStrategy]
        .filter((strategy): strategy is NonNullable<typeof strategy> => Boolean(strategy))
        .map((aggregate) => ({
          label: aggregate.label,
          symbol: strategiesById.get(aggregate.strategyId ?? -1)?.benchmark_symbol,
        })),
      1
    );
  }, [
    intelligence.bestStrategy,
    intelligence.mostConsistentStrategy,
    intelligence.safestStrategy,
    strategiesQuery.data,
  ]);

  const codexOverviewQuery = useQuery({
    queryKey: ['codex', 'dashboard-overview'],
    queryFn: async () => {
      const response = await api.getCodexMarketOverview(1, 3);
      return response.data;
    },
    staleTime: 30_000,
  });

  return (
    <PageContainer size="wide" className="space-y-6">
      <section className="operator-hero animate-fade-in px-6 py-6 sm:px-8 sm:py-8">
        <div className="relative grid gap-6 xl:grid-cols-[1.18fr,0.82fr]">
          <div>
            <div className="surface-label">
              <Sparkles className="h-3.5 w-3.5" />
              Operator cockpit
            </div>
            <h1 className="mt-5 max-w-3xl text-3xl font-bold text-white sm:text-4xl">
              {greeting}, {user?.username ?? 'Trader'}.
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300 sm:text-base">
              Watch live runs, research quality, and market context from one steady desk before
              moving capital into the next strategy cycle.
            </p>

            <div className="mt-5 flex flex-wrap gap-3">
              <div className="operator-status-pill" data-tone="accent">
                <Clock className="h-3.5 w-3.5" />
                <LiveClock />
              </div>
              <div
                className="operator-status-pill"
                data-tone={totalActiveCount > 0 ? 'accent' : 'positive'}
              >
                <span
                  className={`h-2 w-2 rounded-full ${totalActiveCount > 0 ? 'bg-cyan-300 animate-pulse' : 'bg-emerald-300'}`}
                />
                {totalActiveCount > 0
                  ? `${totalActiveCount} active${
                      runningRuntimeBots.length > 0
                        ? ` (${runningRuntimeBots.length} bot${runningRuntimeBots.length === 1 ? '' : 's'})`
                        : runningStrategyCount > 0
                          ? ` (${runningStrategyCount} strategy runtime${runningStrategyCount === 1 ? '' : 's'})`
                          : ''
                    }`
                  : 'No live activity'}
              </div>
              <div
                className="operator-status-pill"
                data-tone={stats.totalPnl >= 0 ? 'positive' : 'danger'}
              >
                {stats.totalPnl >= 0 ? (
                  <TrendingUp className="h-3.5 w-3.5" />
                ) : (
                  <TrendingDown className="h-3.5 w-3.5" />
                )}
                {fmtPnl(stats.totalPnl)} lifetime P&amp;L
              </div>
            </div>

            <div className="operator-mini-grid mt-6">
              <div className="operator-hero-panel px-4 py-4">
                <p className="text-[10px] uppercase text-slate-500">Date</p>
                <p className="mt-2 text-sm font-semibold text-white">
                  {new Date().toLocaleDateString('en-US', {
                    weekday: 'long',
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric',
                  })}
                </p>
                <p className="mt-1 text-xs text-slate-500">Session context</p>
              </div>
              <div className="operator-hero-panel px-4 py-4">
                <p className="text-[10px] uppercase text-slate-500">Completed</p>
                <p className="mt-2 text-xl font-semibold text-white">{stats.completed}</p>
                <p className="mt-1 text-xs text-slate-500">Quality-scored runs</p>
              </div>
              <div className="operator-hero-panel px-4 py-4">
                <p className="text-[10px] uppercase text-slate-500">Trades simulated</p>
                <p className="mt-2 text-xl font-semibold text-white">{fmtN(countTrades)}</p>
                <p className="mt-1 text-xs text-slate-500">Loaded run archive</p>
              </div>
              <div className="operator-hero-panel px-4 py-4">
                <p className="text-[10px] uppercase text-slate-500">Best Sharpe</p>
                <p className="mt-2 text-xl font-semibold text-white">
                  {stats.bestSharpe.toFixed(2)}
                </p>
                <p className="mt-1 text-xs text-slate-500">Top risk-adjusted score</p>
              </div>
            </div>
          </div>

          <div className="grid gap-4">
            <div className="operator-hero-panel px-5 py-5">
              <div className="flex items-start gap-3">
                <div className="premium-icon-wrap text-teal-300">
                  <Activity className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-white">Live readiness</p>
                  <p className="mt-1 text-sm leading-6 text-slate-400">
                    Bot runtime health, active backtests, sync health, and alerts remain visible
                    before you move into detailed control desks.
                  </p>
                </div>
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                <div className="metric-tile px-4 py-4">
                  <p className="text-[10px] uppercase text-slate-500">Quality signal</p>
                  <p className="mt-2 text-sm font-semibold text-emerald-300">
                    {stats.bestWinRate > 0 ? fmtPct(stats.bestWinRate) : 'Awaiting completed runs'}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">Best observed win rate</p>
                </div>
                <div className="metric-tile px-4 py-4">
                  <p className="text-[10px] uppercase text-slate-500">Average run</p>
                  <p
                    className={`mt-2 text-sm font-semibold ${
                      stats.avgPnlPerRun >= 0 ? 'text-emerald-300' : 'text-rose-300'
                    }`}
                  >
                    {fmtPnl(stats.avgPnlPerRun)}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">Mean P&amp;L across completed runs</p>
                </div>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <Link to="/backtests/new" className="operator-action-card p-4 text-left">
                <div className="flex items-start gap-3">
                  <div className="rounded-lg bg-cyan-500/10 p-2.5 text-cyan-300">
                    <Rocket className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">Run backtest</p>
                    <p className="mt-1 text-xs leading-5 text-slate-500">
                      Validate a strategy with historical data before deployment.
                    </p>
                  </div>
                </div>
              </Link>
              <Link to="/backtests" className="operator-action-card p-4">
                <div className="flex items-start gap-3">
                  <div className="rounded-lg bg-emerald-500/10 p-2.5 text-emerald-300">
                    <Target className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">Backtest intelligence</p>
                    <p className="mt-1 text-xs leading-5 text-slate-500">
                      Open validation quality, strategy trust signals, and promotion readiness.
                    </p>
                  </div>
                </div>
              </Link>
              <Link to="/bots" className="operator-action-card p-4">
                <div className="flex items-start gap-3">
                  <div className="rounded-lg bg-amber-500/10 p-2.5 text-amber-300">
                    <Play className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">Bots</p>
                    <p className="mt-1 text-xs leading-5 text-slate-500">
                      Monitor health, degraded state, and instance actions from the Bots desk.
                    </p>
                  </div>
                </div>
              </Link>
              <Link to="/market-intel" className="operator-action-card p-4">
                <div className="flex items-start gap-3">
                  <div className="rounded-lg bg-teal-500/10 p-2.5 text-teal-300">
                    <Newspaper className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">Market context</p>
                    <p className="mt-1 text-xs leading-5 text-slate-500">
                      Keep macro and asset context close to research and runtime decisions.
                    </p>
                  </div>
                </div>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {statsError && (
        <div className="rounded-lg border border-red-700/60 bg-red-950/30 px-4 py-3 text-sm text-red-200">
          {statsError}
        </div>
      )}
      {!statsError && statsWarning && (
        <div className="rounded-lg border border-yellow-700/50 bg-yellow-950/20 px-4 py-2 text-xs text-yellow-300 flex items-center gap-2">
          <span className="inline-block h-2 w-2 rounded-full bg-yellow-400 animate-pulse" />
          {statsWarning}
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          label="Total Runs"
          icon={<BarChart2 className="w-5 h-5" />}
          value={statsLoading ? '—' : fmtN(countTotal)}
          subtitle={`${stats.completed} completed`}
          color="teal"
          animDelay={0}
        />
        <KpiCard
          label="Completed"
          icon={<Target className="w-5 h-5" />}
          value={statsLoading ? '—' : fmtN(countComplete)}
          subtitle={
            stats.total > 0
              ? `${((stats.completed / stats.total) * 100).toFixed(0)}% success`
              : undefined
          }
          color="green"
          animDelay={60}
        />
        <KpiCard
          label="Active Now"
          icon={<Activity className="w-5 h-5" />}
          value={statsLoading ? '—' : fmtN(countRunning)}
          subtitle={
            runningRuntimeBots.length > 0
              ? `${runningRuntimeBots.length} live bot${runningRuntimeBots.length === 1 ? '' : 's'}`
              : runningStrategyCount > 0
              ? `${runningStrategyCount} strategy runtime${runningStrategyCount === 1 ? '' : 's'} live`
              : stats.running > 0
                ? 'Backtest in progress'
                : 'All idle'
          }
          color={totalActiveCount > 0 ? 'cyan' : 'teal'}
          trend={totalActiveCount > 0 ? 'up' : 'neutral'}
          animDelay={120}
        />
        <KpiCard
          label="Failed / Cancelled"
          icon={<AlertCircle className="w-5 h-5" />}
          value={statsLoading ? '—' : fmtN(countFailed)}
          subtitle={stats.failed === 0 ? 'No failures' : 'Review errors'}
          color={stats.failed > 0 ? 'rose' : 'emerald'}
          animDelay={180}
        />
      </div>

      {/* ── KPI row 2 ───────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          label="Lifetime P&L"
          icon={<TrendingUp className="w-5 h-5" />}
          value={statsLoading ? '—' : fmtPnl(stats.totalPnl)}
          subtitle={`avg ${fmtPnl(stats.avgPnlPerRun)}/run`}
          color={stats.totalPnl >= 0 ? 'green' : 'red'}
          trend={stats.totalPnl >= 0 ? 'up' : 'down'}
          animDelay={240}
        />
        <KpiCard
          label="Best Win Rate"
          icon={<Zap className="w-5 h-5" />}
          value={statsLoading ? '—' : fmtPct(stats.bestWinRate)}
          subtitle="Best completed run"
          color="amber"
          animDelay={300}
        />
        <KpiCard
          label="Best Sharpe"
          icon={<Rocket className="w-5 h-5" />}
          value={statsLoading ? '—' : stats.bestSharpe.toFixed(2)}
          subtitle="Risk-adj. return"
          color="cyan"
          animDelay={360}
        />
        <KpiCard
          label="Trades Simulated"
          icon={<Play className="w-5 h-5" />}
          value={statsLoading ? '—' : fmtN(countTrades)}
          subtitle="Across all runs"
          color="cyan"
          animDelay={420}
        />
      </div>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-4">
        <StrategySpotlightCard
          title="Best Strategy"
          subtitle="Highest blended score"
          href="/backtests"
          icon={<Sparkles className="h-5 w-5 text-emerald-300" />}
          accentClass="bg-emerald-500/10"
          titleValue={intelligence.bestStrategy?.label}
          primaryMetric={
            intelligence.bestStrategy
              ? `P&L ${formatIntelligenceCurrency(intelligence.bestStrategy.totalPnl)}`
              : undefined
          }
          secondaryMetric={
            intelligence.bestStrategy
              ? `Sharpe ${intelligence.bestStrategy.avgSharpe.toFixed(2)}`
              : undefined
          }
          emptyMessage="Run a few completed backtests to rank your top-performing setup."
        />
        <StrategySpotlightCard
          title="Safest Strategy"
          subtitle="Lowest drawdown among viable runs"
          href="/backtests"
          icon={<ShieldCheck className="h-5 w-5 text-cyan-300" />}
          accentClass="bg-cyan-500/10"
          titleValue={intelligence.safestStrategy?.label}
          primaryMetric={
            intelligence.safestStrategy
              ? `Drawdown ${formatIntelligencePercent(intelligence.safestStrategy.avgDrawdownPct)}`
              : undefined
          }
          secondaryMetric={
            intelligence.safestStrategy
              ? `Sharpe ${intelligence.safestStrategy.avgSharpe.toFixed(2)}`
              : undefined
          }
          emptyMessage="Safety rankings appear once completed runs have drawdown data."
        />
        <StrategySpotlightCard
          title="Most Consistent"
          subtitle="Best profitability discipline"
          href="/backtests"
          icon={<Layers3 className="h-5 w-5 text-amber-300" />}
          accentClass="bg-amber-500/10"
          titleValue={intelligence.mostConsistentStrategy?.label}
          primaryMetric={
            intelligence.mostConsistentStrategy
              ? `Hit rate ${formatIntelligencePercent(intelligence.mostConsistentStrategy.profitabilityRatePct)}`
              : undefined
          }
          secondaryMetric={
            intelligence.mostConsistentStrategy
              ? `${intelligence.mostConsistentStrategy.completedRuns} completed runs`
              : undefined
          }
          emptyMessage="Consistency scoring needs a few completed runs before it becomes meaningful."
        />
        <div
          className="operator-section-card relative overflow-hidden p-5"
          style={{
            background:
              'linear-gradient(135deg, rgba(18,24,25,.96) 0%, rgba(9,13,14,.94) 58%, rgba(20,83,74,.22) 100%)',
          }}
        >
          <div className="relative">
            <div className="mb-3 inline-flex rounded-lg border border-teal-500/20 bg-teal-500/10 px-3 py-1 text-[11px] font-semibold uppercase text-teal-300">
              Market Intel
            </div>
            <h2 className="text-lg font-semibold text-white">Codex.io Snapshot</h2>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              Keep one eye on fast movers and another on liquid, safer setups before you jump from
              analysis into action.
            </p>
            <div className="mt-4 space-y-3">
              {[
                ...(codexOverviewQuery.data?.movers ?? []).slice(0, 1),
                ...(codexOverviewQuery.data?.safe_movers ?? []).slice(0, 1),
              ].map((token) => (
                <div
                  key={token.id}
                  className="rounded-lg border border-slate-700/60 bg-stone-950/55 px-3 py-2"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-white">{token.symbol}</p>
                      <p className="text-xs text-slate-500">{formatCodexUsd(token.price_usd)}</p>
                    </div>
                    <p
                      className={`text-sm font-semibold ${token.price_change_pct_24h >= 0 ? 'text-green-400' : 'text-red-400'}`}
                    >
                      {formatCodexPct(token.price_change_pct_24h)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
            <Link
              to="/market-intel"
              className="mt-5 inline-flex items-center gap-2 rounded-lg border border-teal-500/30 bg-teal-500/15 px-4 py-2 text-sm font-medium text-teal-100 transition hover:bg-teal-500/20"
            >
              Open Market Intel
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      <CodexAssetIntelStrip title="Strategy Asset Context" request={spotlightIntelRequest} />

      <section className="grid grid-cols-1 gap-6 xl:grid-cols-[1.22fr,0.78fr]">
        <div
          className="operator-section-card p-5 animate-fade-slide-up"
          style={{ animationDelay: '200ms' }}
        >
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="flex items-center gap-2 text-base font-semibold text-white">
                <TrendingUp className="h-4 w-4" style={{ color: pnlColor }} />
                Cumulative P&amp;L curve
              </h2>
              <p className="mt-1 text-xs text-slate-400">
                Completed backtest returns over time, kept visible as the command-center anchor
                chart.
              </p>
            </div>
            {pnlTimeSeries.length > 0 && (
              <div
                className={`text-lg font-bold ${stats.totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}
              >
                {fmtPnl(stats.totalPnl)}
              </div>
            )}
          </div>
          <CumulativePnlChart
            data={pnlTimeSeries}
            height={320}
            positiveColor="#22c55e"
            negativeColor="#ef4444"
          />
        </div>

        <div className="grid gap-6">
          <div
            className="operator-section-card p-5 animate-fade-slide-up"
            style={{ animationDelay: '280ms' }}
          >
            <div className="mb-4 flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-cyan-500/10 p-2.5 text-cyan-300">
                  <Play className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-white">Live bot runtime</p>
                  <p className="text-xs text-slate-400">
                    Active bots, degraded state, and runtime transitions stay visible here.
                  </p>
                </div>
              </div>
              <span
                className="operator-status-pill"
                data-tone={runningRuntimeBots.length > 0 ? 'positive' : 'warning'}
              >
                {runningRuntimeBots.length > 0 ? `${runningRuntimeBots.length} running` : 'No bots live'}
              </span>
            </div>

            <div className="grid grid-cols-3 gap-3 border-b border-slate-800/70 pb-4 text-center">
              <div>
                <p className="text-[11px] text-slate-500">Instances</p>
                <p className="text-sm font-semibold text-white">
                  {botsQuery.isLoading ? '—' : runtimeBots.length}
                </p>
              </div>
              <div>
                <p className="text-[11px] text-slate-500">Transitioning</p>
                <p className="text-sm font-semibold text-cyan-300">
                  {transitioningRuntimeBots.length}
                </p>
              </div>
              <div>
                <p className="text-[11px] text-slate-500">Needs attention</p>
                <p
                  className={`text-sm font-semibold ${
                    degradedRuntimeBots.length > 0 ? 'text-rose-300' : 'text-emerald-300'
                  }`}
                >
                  {degradedRuntimeBots.length}
                </p>
              </div>
            </div>

            {botsQuery.isError ? (
              <InlineNotice
                tone="danger"
                title="Bot runtime state unavailable"
                description={
                  botsQuery.error instanceof Error
                    ? botsQuery.error.message
                    : 'Unable to load runtime state from the backend.'
                }
                className="mt-4"
              />
            ) : runningRuntimeBots.length === 0 ? (
              <div className="mt-4">
                <EmptyState
                  icon={Play}
                  title="No live bots are running"
                  description="Deploy from a validated strategy/backtest or start an existing runtime from the Bots desk."
                  action={
                    <Link to="/bots" className="premium-button premium-button-primary px-4 py-2 text-sm">
                      Open Bots
                      <ArrowRight className="h-4 w-4" />
                    </Link>
                  }
                />
              </div>
            ) : (
              <div className="mt-4 space-y-3">
                {runningRuntimeBots.slice(0, 4).map((bot) => (
                  <Link
                    key={bot.instance_id}
                    to="/bots"
                    className="block rounded-lg border border-slate-700/60 bg-slate-950/45 p-3 transition hover:border-cyan-500/40 hover:bg-slate-900/70"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-white">
                          {bot.instance_name || bot.instance_id}
                        </p>
                        <p className="mt-1 truncate text-xs text-slate-500">
                          {bot.strategy || 'runtime'} · {bot.started_at ? `started ${new Date(bot.started_at).toLocaleTimeString()}` : 'start time unavailable'}
                        </p>
                      </div>
                      <span className="operator-status-pill" data-tone="positive">
                        {bot.status}
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>

          <div
            className="operator-section-card p-5 animate-fade-slide-up"
            style={{ animationDelay: '340ms' }}
          >
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-cyan-500/10 p-2.5 text-cyan-300">
                  <Activity className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-white">Active runs</p>
                  <p className="text-xs text-slate-400">
                    Progress stays visible without leaving the page.
                  </p>
                </div>
              </div>
              <span
                className="operator-status-pill"
                data-tone={stats.running > 0 ? 'accent' : 'positive'}
              >
                {stats.running > 0 ? `${stats.running} running` : 'Idle'}
              </span>
            </div>

            {stats.activeRuns.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-3 py-10 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-800">
                  <Activity className="h-6 w-6 text-slate-500" />
                </div>
                <p className="text-sm text-slate-400">No active runs right now</p>
                <p className="text-xs text-slate-500">
                  Open Backtests when you are ready to start a new validation cycle.
                </p>
              </div>
            ) : (
              <div className="max-h-80 space-y-3 overflow-y-auto">
                {stats.activeRuns.map((run) => (
                  <ActiveRunCard key={run.run_id} run={run} />
                ))}
              </div>
            )}

            <div className="mt-4 grid grid-cols-3 gap-3 border-t border-slate-800/70 pt-4 text-center">
              <div>
                <p className="text-[11px] text-slate-500">Best win rate</p>
                <p className="text-sm font-semibold text-white">
                  {stats.bestWinRate > 0 ? fmtPct(stats.bestWinRate) : '—'}
                </p>
              </div>
              <div>
                <p className="text-[11px] text-slate-500">Best Sharpe</p>
                <p className="text-sm font-semibold text-white">
                  {stats.bestSharpe > 0 ? stats.bestSharpe.toFixed(2) : '—'}
                </p>
              </div>
              <div>
                <p className="text-[11px] text-slate-500">Avg P&amp;L / run</p>
                <p
                  className={`text-sm font-semibold ${stats.avgPnlPerRun >= 0 ? 'text-green-400' : 'text-red-400'}`}
                >
                  {stats.completed > 0 ? fmtPnl(stats.avgPnlPerRun) : '—'}
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-6 xl:grid-cols-[1.1fr,0.9fr]">
        <CoinDeskNewsPanel compact />
        <div className="grid gap-6">
          <div className="animate-fade-slide-up" style={{ animationDelay: '390ms' }}>
            <SyncHealthPanel />
          </div>

          <div className="operator-section-card p-5">
            <div className="flex items-start gap-3">
              <div className="premium-icon-wrap text-cyan-300">
                <Newspaper className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-white">
                  Market context, not just metrics
                </h2>
                <p className="mt-1 text-sm leading-6 text-slate-400">
                  Use the newsroom and market-intel workspace together so operator decisions stay
                  tied to the broader market regime.
                </p>
              </div>
            </div>
            <div className="mt-5 grid grid-cols-1 gap-3">
              <Link to="/market-intel/news" className="operator-action-card p-4">
                <p className="text-sm font-semibold text-white">Open Market News</p>
                <p className="mt-1 text-xs text-slate-400">
                  See the full CoinDesk-powered newsroom view.
                </p>
              </Link>
              <Link to="/market-intel" className="operator-action-card p-4">
                <p className="text-sm font-semibold text-white">Open Market Intel</p>
                <p className="mt-1 text-xs text-slate-400">
                  Inspect movers, safer tokens, and asset context in one place.
                </p>
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section
        className="operator-section-card p-5 animate-fade-slide-up"
        style={{ animationDelay: '420ms' }}
      >
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-white">Recent activity</h2>
            <p className="text-sm text-slate-400">
              Latest validation and runtime signals, with deep reports kept under Backtests.
            </p>
          </div>
          <Link to="/backtests/runs" className="premium-button premium-button-secondary px-4 py-2 text-sm">
            Open runs
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
        {statsLoading ? (
          <div className="rounded-lg border border-slate-800 bg-slate-950/45 p-5 text-sm text-slate-400">
            Loading recent activity...
          </div>
        ) : runs.length === 0 ? (
          <EmptyState
            icon={Activity}
            title="No activity yet"
            description="Validated backtests, running jobs, and bot events will appear here once the desk has data."
            action={
              <Link to="/backtests/new" className="premium-button premium-button-primary px-4 py-2 text-sm">
                Run first backtest
                <ArrowRight className="h-4 w-4" />
              </Link>
            }
          />
        ) : (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {runs.slice(0, 6).map((run) => (
              <Link
                key={run.run_id}
                to={`/backtest/${run.run_id}`}
                className="rounded-lg border border-slate-800 bg-slate-950/45 p-4 transition hover:border-cyan-500/35 hover:bg-slate-900/70"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-white">
                      {run.name || run.run_id}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      {String(run.status ?? 'unknown').toUpperCase()}
                    </p>
                  </div>
                  <span
                    className={`text-sm font-semibold ${safeNum(run.total_pnl) >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}
                  >
                    {fmtPnl(safeNum(run.total_pnl))}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </PageContainer>
  );
};
