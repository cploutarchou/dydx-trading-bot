/**
 * Dashboard – Premium redesign
 * ─ Hero greeting + live clock
 * ─ Animated KPI cards (8)
 * ─ TradingView cumulative PnL chart
 * ─ Active runs monitor + Quick Launch accordion
 * ─ Full BacktestList
 */

import { useQuery } from '@tanstack/react-query';
import {
    Activity,
    AlertCircle,
    ArrowRight,
    BarChart2,
    ChevronDown,
    ChevronUp,
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
import { BacktestList } from '../components/BacktestList';
import { BacktestRunner } from '../components/BacktestRunner';
import { CodexAssetIntelStrip } from '../components/CodexAssetIntelStrip';
import { CoinDeskNewsPanel } from '../components/CoinDeskNewsPanel';
import { CumulativePnlChart, type PnlPoint } from '../components/CumulativePnlChart';
import { PageContainer } from '../components/PageContainer';
import { SyncHealthPanel } from '../components/SyncHealthPanel';
import {
    buildIntelligence,
    formatCurrency as formatIntelligenceCurrency,
    formatPercent as formatIntelligencePercent,
    type BacktestRun,
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
    <span className="font-mono tabular-nums text-blue-300">
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
  color: 'blue' | 'green' | 'red' | 'purple' | 'amber' | 'cyan' | 'emerald' | 'rose';
  trend?: 'up' | 'down' | 'neutral';
  animDelay?: number;
}

const colorMap: Record<KpiCardProps['color'], { border: string; bg: string; icon: string }> = {
  blue: { border: 'border-blue-500/30', bg: 'bg-blue-500/10', icon: 'text-blue-400' },
  green: { border: 'border-green-500/30', bg: 'bg-green-500/10', icon: 'text-green-400' },
  red: { border: 'border-red-500/30', bg: 'bg-red-500/10', icon: 'text-red-400' },
  purple: { border: 'border-purple-500/30', bg: 'bg-purple-500/10', icon: 'text-purple-400' },
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
      className={`relative bg-slate-800/60 backdrop-blur-sm border ${c.border} rounded-xl p-5
        transition-all duration-300 hover:bg-slate-800 hover:shadow-xl cursor-default animate-fade-slide-up`}
      style={{ animationDelay: `${animDelay}ms` }}
    >
      <div className="flex items-start justify-between mb-3">
        <div className={`p-2.5 rounded-lg ${c.bg}`}>
          <div className={c.icon}>{icon}</div>
        </div>
        {trend && trend !== 'neutral' && (
          <span
            className={`text-xs font-medium flex items-center gap-0.5 ${trend === 'up' ? 'text-green-400' : 'text-red-400'}`}
          >
            {trend === 'up' ? (
              <TrendingUp className="w-3.5 h-3.5" />
            ) : (
              <TrendingDown className="w-3.5 h-3.5" />
            )}
          </span>
        )}
      </div>
      <p className="text-2xl font-bold text-white tracking-tight">{value}</p>
      <p className="text-xs text-slate-400 mt-1">{label}</p>
      {subtitle && <p className="text-[11px] text-slate-500 mt-0.5">{subtitle}</p>}
    </div>
  );
};

// ── ActiveRunCard ─────────────────────────────────────────────────────────────

const ActiveRunCard: React.FC<{ run: BacktestRunSummary }> = ({ run }) => {
  const pct = Math.min(100, Math.max(0, run.progress_pct ?? 0));
  const isRunning = run.status.toUpperCase() === 'RUNNING';
  return (
    <div className="bg-slate-900/60 border border-slate-700 rounded-lg p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <span className="relative flex h-2 w-2 shrink-0">
            {isRunning && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
            )}
            <span
              className={`relative inline-flex rounded-full h-2 w-2 ${isRunning ? 'bg-blue-400' : 'bg-yellow-400'}`}
            />
          </span>
          <span className="text-xs font-mono text-blue-400 truncate">
            {(run.name || run.run_id).substring(0, 22)}
          </span>
        </div>
        <span className="text-xs text-slate-400 tabular-nums shrink-0 ml-2">
          {pct > 0 ? `${pct.toFixed(1)}%` : '…'}
        </span>
      </div>
      <div className="w-full bg-slate-700 rounded-full h-1.5 overflow-hidden">
        <div
          className="h-1.5 rounded-full bg-blue-500 transition-all duration-700"
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
  <div className="rounded-2xl border border-slate-700/60 bg-slate-800/60 p-5 backdrop-blur-sm">
    <div className="mb-4 flex items-start justify-between gap-3">
      <div className="flex items-center gap-3">
        <div className={`rounded-xl p-2 ${accentClass}`}>{icon}</div>
        <div>
          <p className="text-sm font-semibold text-white">{title}</p>
          <p className="text-xs text-slate-500">{subtitle}</p>
        </div>
      </div>
      <Link
        to={href}
        className="inline-flex items-center gap-1 text-xs font-medium text-blue-300 transition hover:text-blue-200"
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
  const [refreshTrigger, setRefreshTrigger] = useState(0);
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
  const [launcherOpen, setLauncherOpen] = useState(false);
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
      const statsPromise = api.listBacktests(0, 500);
      const timeoutPromise = new Promise<Awaited<ReturnType<typeof api.listBacktests>>>(
        (_, reject) => {
          timeoutId = setTimeout(
            () => reject(new Error('Timed out while loading dashboard stats')),
            25000
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
  }, [computeStats, refreshTrigger]);

  useEffect(() => {
    if (stats.running > 0 && !pollRef.current) {
      pollRef.current = setInterval(() => void computeStats(), 4000);
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
  const countRunning = useCountUp(stats.running);
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
      {/* ── Hero ────────────────────────────────────────────────────── */}
      <div
        className="relative rounded-2xl overflow-hidden border border-slate-700/60 animate-fade-in"
        style={{
          background:
            'linear-gradient(135deg,rgba(30,41,59,.9) 0%,rgba(15,23,42,.95) 60%,rgba(20,30,50,.9) 100%)',
        }}
      >
        <div className="absolute -top-20 -right-20 w-72 h-72 bg-blue-600/8 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-16 -left-16 w-56 h-56 bg-purple-600/8 rounded-full blur-3xl pointer-events-none" />

        <div className="relative px-6 py-5 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <div>
            <p className="text-slate-400 text-sm">{greeting},</p>
            <h1 className="text-2xl font-bold text-white mt-0.5">
              {user?.username ?? 'Trader'} <span className="gradient-text">👋</span>
            </h1>
            <p className="text-slate-500 text-sm mt-1">
              {new Date().toLocaleDateString('en-US', {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric',
              })}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3 text-sm">
            <div className="flex items-center gap-2 text-slate-300">
              <Clock className="w-4 h-4 text-blue-400" />
              <LiveClock />
            </div>
            {stats.running > 0 && (
              <div className="flex items-center gap-2 text-blue-300 bg-blue-500/10 border border-blue-500/20 rounded-lg px-3 py-1.5 text-xs font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                {stats.running} active {stats.running === 1 ? 'run' : 'runs'}
              </div>
            )}
            <div
              className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium border ${
                stats.totalPnl >= 0
                  ? 'text-green-300 bg-green-500/10 border-green-500/20'
                  : 'text-red-300 bg-red-500/10 border-red-500/20'
              }`}
            >
              {stats.totalPnl >= 0 ? (
                <TrendingUp className="w-3.5 h-3.5" />
              ) : (
                <TrendingDown className="w-3.5 h-3.5" />
              )}
              {fmtPnl(stats.totalPnl)} lifetime P&L
            </div>
          </div>
        </div>
      </div>

      {statsError && (
        <div className="rounded-xl border border-red-700/60 bg-red-900/25 px-4 py-3 text-sm text-red-200">
          {statsError}
        </div>
      )}

      {/* ── KPI row 1 ───────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          label="Total Runs"
          icon={<BarChart2 className="w-5 h-5" />}
          value={statsLoading ? '—' : fmtN(countTotal)}
          subtitle={`${stats.completed} completed`}
          color="blue"
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
          subtitle={stats.running > 0 ? 'In progress' : 'All idle'}
          color={stats.running > 0 ? 'cyan' : 'blue'}
          trend={stats.running > 0 ? 'up' : 'neutral'}
          animDelay={120}
        />
        <KpiCard
          label="Failed / Cancelled"
          icon={<AlertCircle className="w-5 h-5" />}
          value={statsLoading ? '—' : fmtN(countFailed)}
          subtitle={stats.failed === 0 ? 'No failures 🎉' : 'Review errors'}
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
          color="purple"
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

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-[1.2fr,0.8fr]">
        <CoinDeskNewsPanel compact />
        <div className="premium-panel">
          <div className="flex items-start gap-3">
            <div className="premium-icon-wrap text-cyan-300">
              <Newspaper className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Market context, not just metrics</h2>
              <p className="mt-1 text-sm leading-6 text-slate-400">
                Use the newsroom and market-intel workspace together so client-facing decisions feel
                informed, current, and grounded in real market regime changes.
              </p>
            </div>
          </div>
          <div className="mt-5 grid grid-cols-1 gap-3">
            <Link
              to="/news"
              className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 transition hover:border-cyan-500/35 hover:bg-slate-950/70"
            >
              <p className="text-sm font-semibold text-white">Open Market News</p>
              <p className="mt-1 text-xs text-slate-400">
                See the full CoinDesk-powered newsroom view.
              </p>
            </Link>
            <Link
              to="/codex"
              className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 transition hover:border-cyan-500/35 hover:bg-slate-950/70"
            >
              <p className="text-sm font-semibold text-white">Open Market Intel</p>
              <p className="mt-1 text-xs text-slate-400">
                Inspect movers, safer tokens, and asset context in one place.
              </p>
            </Link>
          </div>
        </div>
      </section>

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
          className="relative overflow-hidden rounded-2xl border border-slate-700/60 p-5"
          style={{
            background:
              'linear-gradient(135deg, rgba(15,23,42,.96) 0%, rgba(30,41,59,.92) 55%, rgba(30,64,175,.18) 100%)',
          }}
        >
          <div className="absolute -right-10 -top-10 h-32 w-32 rounded-full bg-blue-500/10 blur-3xl" />
          <div className="relative">
            <div className="mb-3 inline-flex rounded-full border border-blue-500/20 bg-blue-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-blue-300">
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
                  className="rounded-xl border border-slate-700/60 bg-slate-950/45 px-3 py-2"
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
              to="/codex"
              className="mt-5 inline-flex items-center gap-2 rounded-lg border border-blue-500/30 bg-blue-500/15 px-4 py-2 text-sm font-medium text-blue-100 transition hover:bg-blue-500/20"
            >
              Open Market Intel
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      <CodexAssetIntelStrip title="Strategy Asset Context" request={spotlightIntelRequest} />

      {/* ── Equity curve ────────────────────────────────────────────── */}
      <div
        className="bg-slate-800/60 backdrop-blur-sm border border-slate-700/60 rounded-2xl p-5 animate-fade-slide-up"
        style={{ animationDelay: '200ms' }}
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-semibold text-white flex items-center gap-2">
              <TrendingUp className="w-4 h-4" style={{ color: pnlColor }} />
              Cumulative P&L Curve
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Completed backtest returns over time · Powered by TradingView
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
          height={300}
          positiveColor="#22c55e"
          negativeColor="#ef4444"
        />
      </div>

      {/* ── Quick Launch + Active Runs ──────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Quick Launch accordion */}
        <div
          className="bg-slate-800/60 backdrop-blur-sm border border-slate-700/60 rounded-2xl overflow-hidden animate-fade-slide-up"
          style={{ animationDelay: '300ms' }}
        >
          <button
            type="button"
            onClick={() => setLauncherOpen((o) => !o)}
            className="w-full flex items-center justify-between px-5 py-4 hover:bg-slate-700/30 transition-colors"
          >
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-500/15 rounded-lg">
                <Rocket className="w-4 h-4 text-blue-400" />
              </div>
              <div className="text-left">
                <p className="text-sm font-semibold text-white">Quick Launch Backtest</p>
                <p className="text-xs text-slate-400">Configure and start a new run</p>
              </div>
            </div>
            <div className="text-slate-400">
              {launcherOpen ? (
                <ChevronUp className="w-5 h-5" />
              ) : (
                <ChevronDown className="w-5 h-5" />
              )}
            </div>
          </button>

          {launcherOpen && (
            <div className="border-t border-slate-700/60">
              <BacktestRunner
                onBacktestComplete={() => {
                  setRefreshTrigger((t) => t + 1);
                  setLauncherOpen(false);
                }}
              />
            </div>
          )}
        </div>

        {/* Active Runs panel */}
        <div
          className="bg-slate-800/60 backdrop-blur-sm border border-slate-700/60 rounded-2xl p-5 flex flex-col animate-fade-slide-up"
          style={{ animationDelay: '360ms' }}
        >
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-cyan-500/15 rounded-lg">
                <Activity className="w-4 h-4 text-cyan-400" />
              </div>
              <div>
                <p className="text-sm font-semibold text-white">Active Runs</p>
                <p className="text-xs text-slate-400">Live progress monitor</p>
              </div>
            </div>
            {stats.running > 0 && (
              <span className="text-xs bg-blue-500/20 border border-blue-500/30 text-blue-300 px-2 py-0.5 rounded-full">
                {stats.running} running
              </span>
            )}
          </div>

          {stats.activeRuns.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center py-10 text-center gap-3">
              <div className="w-12 h-12 bg-slate-700/50 rounded-full flex items-center justify-center">
                <Activity className="w-6 h-6 text-slate-500" />
              </div>
              <p className="text-slate-400 text-sm">No active runs right now</p>
              <p className="text-slate-500 text-xs">Launch one from Quick Launch ↙</p>
            </div>
          ) : (
            <div className="space-y-2 overflow-y-auto max-h-72">
              {stats.activeRuns.map((run) => (
                <ActiveRunCard key={run.run_id} run={run} />
              ))}
            </div>
          )}

          {stats.completed > 0 && (
            <div className="mt-4 pt-4 border-t border-slate-700/50 grid grid-cols-3 gap-3 text-center">
              <div>
                <p className="text-[11px] text-slate-500">Best Win Rate</p>
                <p className="text-sm font-semibold text-white">{fmtPct(stats.bestWinRate)}</p>
              </div>
              <div>
                <p className="text-[11px] text-slate-500">Best Sharpe</p>
                <p className="text-sm font-semibold text-white">
                  {stats.bestSharpe > 0 ? stats.bestSharpe.toFixed(2) : '—'}
                </p>
              </div>
              <div>
                <p className="text-[11px] text-slate-500">Avg P&L / Run</p>
                <p
                  className={`text-sm font-semibold ${stats.avgPnlPerRun >= 0 ? 'text-green-400' : 'text-red-400'}`}
                >
                  {fmtPnl(stats.avgPnlPerRun)}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Sync Health ──────────────────────────────────────────────── */}
      <div className="animate-fade-slide-up" style={{ animationDelay: '390ms' }}>
        <SyncHealthPanel />
      </div>

      {/* ── Full Backtest List ──────────────────────────────────────── */}
      <div className="animate-fade-slide-up" style={{ animationDelay: '420ms' }}>
        <BacktestList refreshTrigger={refreshTrigger} />
      </div>
    </PageContainer>
  );
};
