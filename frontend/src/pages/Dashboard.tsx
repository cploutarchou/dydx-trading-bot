/**
 * Dashboard – Premium redesign
 * ─ Hero greeting + live clock
 * ─ Animated KPI cards (8)
 * ─ TradingView cumulative PnL chart
 * ─ Active runs monitor + Quick Launch accordion
 * ─ Full BacktestList
 */

import {
  Activity,
  AlertCircle,
  BarChart2,
  ChevronDown,
  ChevronUp,
  Clock,
  Play,
  Rocket,
  Target,
  TrendingDown,
  TrendingUp,
  Zap,
} from 'lucide-react';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import api from '../api';
import { devFallback, MOCK_BACKTEST_RUNS } from '../api/mockData';
import { BacktestList } from '../components/BacktestList';
import { BacktestRunner } from '../components/BacktestRunner';
import { CumulativePnlChart, type PnlPoint } from '../components/CumulativePnlChart';
import { useAuthStore } from '../store/auth';

// ── Types ─────────────────────────────────────────────────────────────────────

interface BacktestRunSummary {
  run_id: string;
  name?: string;
  status: string;
  total_pnl: number;
  win_rate: number;
  sharpe_ratio?: number;
  total_trades: number;
  created_at: string;
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
  blue:    { border: 'border-blue-500/30',    bg: 'bg-blue-500/10',    icon: 'text-blue-400'    },
  green:   { border: 'border-green-500/30',   bg: 'bg-green-500/10',   icon: 'text-green-400'   },
  red:     { border: 'border-red-500/30',     bg: 'bg-red-500/10',     icon: 'text-red-400'     },
  purple:  { border: 'border-purple-500/30',  bg: 'bg-purple-500/10',  icon: 'text-purple-400'  },
  amber:   { border: 'border-amber-500/30',   bg: 'bg-amber-500/10',   icon: 'text-amber-400'   },
  cyan:    { border: 'border-cyan-500/30',    bg: 'bg-cyan-500/10',    icon: 'text-cyan-400'    },
  emerald: { border: 'border-emerald-500/30', bg: 'bg-emerald-500/10', icon: 'text-emerald-400' },
  rose:    { border: 'border-rose-500/30',    bg: 'bg-rose-500/10',    icon: 'text-rose-400'    },
};

const KpiCard: React.FC<KpiCardProps> = ({ label, value, subtitle, icon, color, trend, animDelay = 0 }) => {
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
          <span className={`text-xs font-medium flex items-center gap-0.5 ${trend === 'up' ? 'text-green-400' : 'text-red-400'}`}>
            {trend === 'up' ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
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
            <span className={`relative inline-flex rounded-full h-2 w-2 ${isRunning ? 'bg-blue-400' : 'bg-yellow-400'}`} />
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

// ── Helpers ───────────────────────────────────────────────────────────────────

const toRecord = (v: unknown): Record<string, unknown> =>
  v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {};

const safeNum = (v: unknown, fallback = 0): number => {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
};

// ── Main Dashboard ────────────────────────────────────────────────────────────

export const DashboardPage: React.FC = () => {
  const { user } = useAuthStore();
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [stats, setStats] = useState<DashboardStats>({
    total: 0, completed: 0, running: 0, failed: 0,
    totalPnl: 0, bestWinRate: 0, bestSharpe: 0,
    totalTrades: 0, avgPnlPerRun: 0,
    activeRuns: [], pnlTimeSeries: [],
  });
  const [statsLoading, setStatsLoading] = useState(true);
  const [launcherOpen, setLauncherOpen] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const computeStats = useCallback(async () => {
    try {
      const response = await api.listBacktests(0, 500);
      const raw = toRecord(response);
      const rawData = toRecord(raw.data);

      const rawRuns: BacktestRunSummary[] = Array.isArray(rawData.backtests)
        ? (rawData.backtests as BacktestRunSummary[])
        : [];

      const runs = devFallback(rawRuns, MOCK_BACKTEST_RUNS as unknown as BacktestRunSummary[]);

      const norm = (s?: string) => String(s ?? '').toUpperCase();

      const completed = runs.filter((r) => norm(r.status) === 'COMPLETED');
      const running   = runs.filter((r) => norm(r.status) === 'RUNNING' || norm(r.status) === 'PENDING');
      const failed    = runs.filter((r) => norm(r.status) === 'FAILED' || norm(r.status) === 'CANCELLED');

      const totalPnl    = completed.reduce((acc, r) => acc + safeNum(r.total_pnl), 0);
      const bestWinRate = completed.reduce((max, r) => Math.max(max, safeNum(r.win_rate)), 0);
      const bestSharpe  = completed.reduce((max, r) => Math.max(max, safeNum(r.sharpe_ratio)), 0);
      const totalTrades = runs.reduce((acc, r) => acc + safeNum(r.total_trades), 0);
      const avgPnlPerRun = completed.length > 0 ? totalPnl / completed.length : 0;

      const sorted = [...completed].sort(
        (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      );

      const pnlTimeSeries: PnlPoint[] = [];
      let cumulative = 0;
      const seenDates = new Set<string>();

      for (const r of sorted) {
        const d = new Date(r.created_at);
        if (isNaN(d.getTime())) continue;
        const dateStr = d.toISOString().substring(0, 10);
        cumulative += safeNum(r.total_pnl);

        if (seenDates.has(dateStr)) {
          const last = pnlTimeSeries[pnlTimeSeries.length - 1];
          if (last?.time === dateStr) last.value = parseFloat(cumulative.toFixed(2));
        } else {
          pnlTimeSeries.push({ time: dateStr, value: parseFloat(cumulative.toFixed(2)) });
          seenDates.add(dateStr);
        }
      }

      setStats({
        total: runs.length, completed: completed.length,
        running: running.length, failed: failed.length,
        totalPnl, bestWinRate, bestSharpe, totalTrades, avgPnlPerRun,
        activeRuns: running, pnlTimeSeries,
      });
    } catch {
      /* silent – BacktestList shows its own error state */
    } finally {
      setStatsLoading(false);
    }
  }, []);

  useEffect(() => { void computeStats(); }, [computeStats, refreshTrigger]);

  useEffect(() => {
    if (stats.running > 0 && !pollRef.current) {
      pollRef.current = setInterval(() => void computeStats(), 4000);
    } else if (stats.running === 0 && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    };
  }, [stats.running, computeStats]);

  // Animated counters
  const countTotal    = useCountUp(stats.total);
  const countComplete = useCountUp(stats.completed);
  const countRunning  = useCountUp(stats.running);
  const countFailed   = useCountUp(stats.failed);
  const countTrades   = useCountUp(stats.totalTrades);

  const fmtPnl = (v: number) =>
    (v >= 0 ? '+' : '') + '$' + Math.abs(v).toLocaleString('en-US', { maximumFractionDigits: 2 });
  const fmtPct = (v: number) => v.toFixed(1) + '%';
  const fmtN   = (v: number) => Math.round(v).toLocaleString('en-US');

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

  const pnlTimeSeries = useMemo(() => stats.pnlTimeSeries, [stats.pnlTimeSeries]);
  const pnlColor = stats.totalPnl >= 0 ? '#22c55e' : '#ef4444';

  return (
    <div className="min-h-screen bg-slate-900 p-6 space-y-6">

      {/* ── Hero ────────────────────────────────────────────────────── */}
      <div
        className="relative rounded-2xl overflow-hidden border border-slate-700/60 animate-fade-in"
        style={{ background: 'linear-gradient(135deg,rgba(30,41,59,.9) 0%,rgba(15,23,42,.95) 60%,rgba(20,30,50,.9) 100%)' }}
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
              {new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
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
            <div className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium border ${
              stats.totalPnl >= 0
                ? 'text-green-300 bg-green-500/10 border-green-500/20'
                : 'text-red-300 bg-red-500/10 border-red-500/20'
            }`}>
              {stats.totalPnl >= 0 ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
              {fmtPnl(stats.totalPnl)} lifetime P&L
            </div>
          </div>
        </div>
      </div>

      {/* ── KPI row 1 ───────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Total Runs" icon={<BarChart2 className="w-5 h-5" />}
          value={statsLoading ? '—' : fmtN(countTotal)}
          subtitle={`${stats.completed} completed`} color="blue" animDelay={0} />
        <KpiCard label="Completed" icon={<Target className="w-5 h-5" />}
          value={statsLoading ? '—' : fmtN(countComplete)}
          subtitle={stats.total > 0 ? `${((stats.completed / stats.total) * 100).toFixed(0)}% success` : undefined}
          color="green" animDelay={60} />
        <KpiCard label="Active Now" icon={<Activity className="w-5 h-5" />}
          value={statsLoading ? '—' : fmtN(countRunning)}
          subtitle={stats.running > 0 ? 'In progress' : 'All idle'}
          color={stats.running > 0 ? 'cyan' : 'blue'}
          trend={stats.running > 0 ? 'up' : 'neutral'} animDelay={120} />
        <KpiCard label="Failed / Cancelled" icon={<AlertCircle className="w-5 h-5" />}
          value={statsLoading ? '—' : fmtN(countFailed)}
          subtitle={stats.failed === 0 ? 'No failures 🎉' : 'Review errors'}
          color={stats.failed > 0 ? 'rose' : 'emerald'} animDelay={180} />
      </div>

      {/* ── KPI row 2 ───────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Lifetime P&L" icon={<TrendingUp className="w-5 h-5" />}
          value={statsLoading ? '—' : fmtPnl(stats.totalPnl)}
          subtitle={`avg ${fmtPnl(stats.avgPnlPerRun)}/run`}
          color={stats.totalPnl >= 0 ? 'green' : 'red'}
          trend={stats.totalPnl >= 0 ? 'up' : 'down'} animDelay={240} />
        <KpiCard label="Best Win Rate" icon={<Zap className="w-5 h-5" />}
          value={statsLoading ? '—' : fmtPct(stats.bestWinRate)}
          subtitle="Best completed run" color="amber" animDelay={300} />
        <KpiCard label="Best Sharpe" icon={<Rocket className="w-5 h-5" />}
          value={statsLoading ? '—' : stats.bestSharpe.toFixed(2)}
          subtitle="Risk-adj. return" color="purple" animDelay={360} />
        <KpiCard label="Trades Simulated" icon={<Play className="w-5 h-5" />}
          value={statsLoading ? '—' : fmtN(countTrades)}
          subtitle="Across all runs" color="cyan" animDelay={420} />
      </div>

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
            <div className={`text-lg font-bold ${stats.totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {fmtPnl(stats.totalPnl)}
            </div>
          )}
        </div>
        <CumulativePnlChart data={pnlTimeSeries} height={300} positiveColor="#22c55e" negativeColor="#ef4444" />
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
              {launcherOpen ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
            </div>
          </button>

          {launcherOpen && (
            <div className="border-t border-slate-700/60">
              <BacktestRunner onBacktestComplete={() => {
                setRefreshTrigger((t) => t + 1);
                setLauncherOpen(false);
              }} />
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
                <p className={`text-sm font-semibold ${stats.avgPnlPerRun >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {fmtPnl(stats.avgPnlPerRun)}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Full Backtest List ──────────────────────────────────────── */}
      <div className="animate-fade-slide-up" style={{ animationDelay: '420ms' }}>
        <BacktestList refreshTrigger={refreshTrigger} />
      </div>
    </div>
  );
};
