/**
 * Dashboard – simplified operator cockpit
 * ─ Greeting + live desk state
 * ─ Primary KPI cards
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
    Play,
    Rocket,
    Sparkles,
    Target,
    TrendingDown,
    TrendingUp,
} from 'lucide-react';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import api, { classifyApiError } from '../api';
import { useBotInstances } from '../api/hooks';
import { CumulativePnlChart, type PnlPoint } from '../components/CumulativePnlChart';
import { PageContainer } from '../components/PageContainer';
import { EmptyState, InlineNotice } from '../components/ui/PlatformUI';
import type { BacktestRun } from '../features/backtests/intelligence';
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

  // ── Backtest runs via React Query (replaces manual setInterval polling) ──────
  const backtestRunsQuery = useQuery({
    queryKey: ['dashboard', 'backtest-runs'],
    queryFn: async (): Promise<BacktestRunSummary[]> => {
      const response = await api.listBacktests(0, 25);
      const raw = toRecord(response);
      const rawData = toRecord(raw.data);
      return Array.isArray(rawData.backtests)
        ? (rawData.backtests as BacktestRunSummary[])
        : Array.isArray(raw.backtests)
          ? (raw.backtests as BacktestRunSummary[])
          : Array.isArray(rawData.runs)
            ? (rawData.runs as BacktestRunSummary[])
            : Array.isArray(raw.runs)
              ? (raw.runs as BacktestRunSummary[])
              : [];
    },
    staleTime: 10_000,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 10_000;
      const hasActive = data.some((r) =>
        ['RUNNING', 'PENDING'].includes(String(r.status ?? '').toUpperCase())
      );
      return hasActive ? 10_000 : 60_000;
    },
    refetchIntervalInBackground: false,
    retry: (failureCount, error) => {
      const classification = classifyApiError(error);
      if (classification.kind === 'transport') return false;
      if (classification.statusCode === 401) return false;
      return failureCount < 2;
    },
  });

  const runs = backtestRunsQuery.data ?? [];
  const stats = useMemo(() => buildDashboardStats(runs), [runs]);
  const statsLoading = backtestRunsQuery.isLoading;
  const statsError = useMemo(() => {
    if (!backtestRunsQuery.error) return null;
    const error = backtestRunsQuery.error;
    const classification = classifyApiError(error);
    if (classification.kind === 'transport') {
      return 'Backend service is unreachable from the browser. Verify API connectivity or Vite proxy setup.';
    }
    if (classification.statusCode === 401) {
      return 'Your session appears to be unauthorized. Please sign in again.';
    }
    return error instanceof Error ? error.message : 'Failed to load dashboard stats.';
  }, [backtestRunsQuery.error]);
  const statsWarning = useMemo(() => {
    if (!backtestRunsQuery.error) return null;
    const error = backtestRunsQuery.error;
    if (error instanceof Error && error.message.toLowerCase().includes('timed out')) {
      return 'Backend is responding slowly — showing last available data.';
    }
    return null;
  }, [backtestRunsQuery.error]);

  // Animated counters
  const countTotal = useCountUp(stats.total);

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
  const botActiveCount = runningRuntimeBots.length + runningStrategyCount;
  const attentionCount = degradedRuntimeBots.length + stats.failed;
  const countAttention = useCountUp(attentionCount);

  return (
    <PageContainer size="wide" className="space-y-6">
      <section className="operator-hero animate-fade-in px-5 py-5 sm:px-6">
        <div className="relative grid gap-5 xl:grid-cols-[1.1fr,0.9fr]">
          <div>
            <div className="surface-label">
              <Sparkles className="h-3.5 w-3.5" />
              Client dashboard
            </div>
            <h1 className="mt-4 max-w-3xl text-2xl font-bold text-white sm:text-3xl">
              {greeting}, {user?.username ?? 'Trader'}
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
              A simple operating view for the current desk: live activity, portfolio P&amp;L,
              backtest status, and anything that needs attention.
            </p>

            <div className="mt-4 flex flex-wrap gap-2">
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
          </div>

          <div className="operator-hero-panel p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-white">Next best actions</p>
                <p className="mt-1 text-xs text-slate-500">
                  Move through research, validation, deployment, then monitoring.
                </p>
              </div>
              <span
                className="operator-status-pill"
                data-tone={attentionCount > 0 ? 'danger' : 'positive'}
              >
                {attentionCount > 0
                  ? `${attentionCount} alert${attentionCount === 1 ? '' : 's'}`
                  : 'Desk healthy'}
              </span>
            </div>

            <div className="mt-4 grid gap-2 sm:grid-cols-2">
              <Link to="/market-intel" className="operator-action-card p-3 text-left">
                <div className="flex items-start gap-3">
                  <div className="rounded-lg bg-teal-500/10 p-2 text-teal-300">
                    <Sparkles className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">Research market</p>
                    <p className="mt-1 text-xs leading-5 text-slate-500">Open Market Intel.</p>
                  </div>
                </div>
              </Link>
              <Link to="/strategies" className="operator-action-card p-3 text-left">
                <div className="flex items-start gap-3">
                  <div className="rounded-lg bg-emerald-500/10 p-2 text-emerald-300">
                    <Target className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">Build strategy</p>
                    <p className="mt-1 text-xs leading-5 text-slate-500">Tune or create logic.</p>
                  </div>
                </div>
              </Link>
              <Link to="/backtests/new" className="operator-action-card p-3 text-left">
                <div className="flex items-start gap-3">
                  <div className="rounded-lg bg-cyan-500/10 p-2 text-cyan-300">
                    <Rocket className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">Run backtest</p>
                    <p className="mt-1 text-xs leading-5 text-slate-500">Validate before launch.</p>
                  </div>
                </div>
              </Link>
              <Link to="/bots" className="operator-action-card p-3">
                <div className="flex items-start gap-3">
                  <div className="rounded-lg bg-amber-500/10 p-2 text-amber-300">
                    <Play className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">Deploy bot</p>
                    <p className="mt-1 text-xs leading-5 text-slate-500">Control live runtimes.</p>
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

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard
          label="Live Activity"
          icon={<Activity className="w-5 h-5" />}
          value={statsLoading ? '—' : fmtN(countRunning)}
          subtitle={`${botActiveCount} bot/runtime, ${stats.running} backtest`}
          color={totalActiveCount > 0 ? 'cyan' : 'teal'}
          trend={totalActiveCount > 0 ? 'up' : 'neutral'}
          animDelay={0}
        />
        <KpiCard
          label="Backtest Archive"
          icon={<BarChart2 className="w-5 h-5" />}
          value={statsLoading ? '—' : fmtN(countTotal)}
          subtitle={`${stats.completed} completed, ${stats.failed} failed`}
          color="teal"
          animDelay={60}
        />
        <KpiCard
          label="Lifetime P&L"
          icon={<TrendingUp className="w-5 h-5" />}
          value={statsLoading ? '—' : fmtPnl(stats.totalPnl)}
          subtitle={`avg ${fmtPnl(stats.avgPnlPerRun)}/completed run`}
          color={stats.totalPnl >= 0 ? 'green' : 'red'}
          trend={stats.totalPnl >= 0 ? 'up' : 'down'}
          animDelay={120}
        />
        <KpiCard
          label="Needs Attention"
          icon={<AlertCircle className="w-5 h-5" />}
          value={statsLoading ? '—' : fmtN(countAttention)}
          subtitle={
            attentionCount > 0
              ? `${degradedRuntimeBots.length} bot, ${stats.failed} backtest`
              : 'No runtime or backtest alerts'
          }
          color={attentionCount > 0 ? 'rose' : 'emerald'}
          animDelay={180}
        />
      </div>

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
                {runningRuntimeBots.length > 0
                  ? `${runningRuntimeBots.length} running`
                  : 'No bots live'}
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
                    <Link
                      to="/bots"
                      className="premium-button premium-button-primary px-4 py-2 text-sm"
                    >
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
                          {bot.strategy || 'runtime'} ·{' '}
                          {bot.started_at
                            ? `started ${new Date(bot.started_at).toLocaleTimeString()}`
                            : 'start time unavailable'}
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
          <Link
            to="/backtests/runs"
            className="premium-button premium-button-secondary px-4 py-2 text-sm"
          >
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
              <Link
                to="/backtests/new"
                className="premium-button premium-button-primary px-4 py-2 text-sm"
              >
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
