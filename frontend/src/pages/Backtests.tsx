import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  ArrowRight,
  Award,
  BarChart3,
  ChevronRight,
  Layers3,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
} from 'lucide-react';
import React, { useMemo } from 'react';
import { Link } from 'react-router-dom';
import api from '../api';
import { devFallback, MOCK_BACKTEST_RUNS, shouldUseDevMocks } from '../api/mockData';
import { BacktestList } from '../components/BacktestList';
import { PageContainer } from '../components/PageContainer';
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

const StatCard: React.FC<{
  label: string;
  value: string;
  hint: string;
  icon: React.ReactNode;
}> = ({ label, value, hint, icon }) => (
  <div className="rounded-2xl border border-slate-700/60 bg-slate-800/60 p-5 backdrop-blur-sm">
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
  <div className="rounded-2xl border border-slate-700/60 bg-slate-800/60 p-5 backdrop-blur-sm">
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
            <p className="font-semibold text-slate-200">{formatPercent(aggregate.avgDrawdownPct)}</p>
          </div>
        </div>
      </>
    ) : (
      <p className="text-sm text-slate-400">No completed backtests yet. Run a backtest to unlock this ranking.</p>
    )}
  </div>
);

export const BacktestsPage: React.FC = () => {
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
      const response = await api.listBacktests(0, 500);
      return devFallback(extractBacktestRuns(response), MOCK_BACKTEST_RUNS as unknown as BacktestRun[]);
    },
    staleTime: 10_000,
    refetchInterval: (query) =>
      (query.state.data ?? []).some((run) => isActiveBacktestRun(run as BacktestRun)) ? 4_000 : false,
  });

  const strategiesById = useMemo(
    () =>
      new Map(
        (strategiesQuery.data ?? [])
          .filter((strategy) => Number.isInteger(strategy.id) && strategy.id > 0)
          .map((strategy) => [strategy.id, strategy.name])
      ),
    [strategiesQuery.data]
  );

  const usingMockData =
    shouldUseDevMocks() &&
    (backtestsQuery.data ?? []).some((run) => String(run.run_id).startsWith('mock-run-'));

  const intelligence = useMemo(
    () => buildIntelligence(backtestsQuery.data ?? [], strategiesById),
    [backtestsQuery.data, strategiesById]
  );

  if (backtestsQuery.isLoading) {
    return (
      <PageContainer size="wide" className="space-y-6">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-800/60 p-10 text-center text-slate-300">
          Building your backtest intelligence workspace...
        </div>
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
          <Link
            to="/dashboard"
            className="mt-4 inline-flex items-center gap-2 rounded-lg border border-red-600/50 bg-red-900/30 px-4 py-2 text-sm font-medium text-red-100 transition hover:bg-red-900/50"
          >
            Return to dashboard
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer size="wide" className="space-y-6">
      <section
        className="relative overflow-hidden rounded-3xl border border-slate-700/60 px-6 py-6 sm:px-8"
        style={{
          background:
            'linear-gradient(135deg, rgba(15,23,42,.96) 0%, rgba(17,24,39,.94) 45%, rgba(12,74,110,.28) 100%)',
        }}
      >
        <div className="absolute -right-20 top-0 h-56 w-56 rounded-full bg-cyan-500/10 blur-3xl" />
        <div className="absolute -bottom-12 left-0 h-40 w-40 rounded-full bg-emerald-500/10 blur-3xl" />

        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-cyan-300">
              <Sparkles className="h-3.5 w-3.5" />
              Backtest Intelligence
            </div>
            <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
              See every backtest, and understand which strategies actually deserve trust.
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
              Rankings below are built from completed runs and weighted toward profitability, risk-adjusted
              return, consistency, and drawdown discipline so you can spot the strongest setups quickly.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-2xl border border-slate-700/60 bg-slate-900/45 px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Runs</p>
              <p className="mt-1 text-xl font-semibold text-white">{intelligence.totalRuns}</p>
            </div>
            <div className="rounded-2xl border border-slate-700/60 bg-slate-900/45 px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Completed</p>
              <p className="mt-1 text-xl font-semibold text-white">{intelligence.completedRuns}</p>
            </div>
            <div className="rounded-2xl border border-slate-700/60 bg-slate-900/45 px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Active</p>
              <p className="mt-1 text-xl font-semibold text-cyan-300">{intelligence.activeRuns}</p>
            </div>
            <div className="rounded-2xl border border-slate-700/60 bg-slate-900/45 px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Tracked Setups</p>
              <p className="mt-1 text-xl font-semibold text-white">{intelligence.strategies.length}</p>
            </div>
          </div>
        </div>

        {usingMockData && (
          <div className="relative mt-5 inline-flex rounded-full border border-amber-700 bg-amber-950/40 px-3 py-1 text-xs font-medium text-amber-300">
            Development mock data is currently active.
          </div>
        )}
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

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <InsightCard
          title="Best Performing Strategy"
          icon={<Award className="h-5 w-5 text-amber-300" />}
          aggregate={intelligence.bestStrategy}
          accent="bg-amber-500/10"
          secondary={intelligence.bestStrategy && intelligence.bestStrategy.totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}
        />
        <InsightCard
          title="Safest Strategy"
          icon={<ShieldCheck className="h-5 w-5 text-emerald-300" />}
          aggregate={intelligence.safestStrategy}
          accent="bg-emerald-500/10"
          secondary={intelligence.safestStrategy && intelligence.safestStrategy.totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}
        />
        <InsightCard
          title="Most Consistent Strategy"
          icon={<Layers3 className="h-5 w-5 text-cyan-300" />}
          aggregate={intelligence.mostConsistentStrategy}
          accent="bg-cyan-500/10"
          secondary={intelligence.mostConsistentStrategy && intelligence.mostConsistentStrategy.totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}
        />
      </section>

      <section className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,.9fr)]">
        <div className="overflow-hidden rounded-2xl border border-slate-700/60 bg-slate-800/60 backdrop-blur-sm">
          <div className="border-b border-slate-700/60 px-6 py-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-white">Strategy Leaderboard</h2>
                <p className="mt-1 text-sm text-slate-400">
                  Weighted for profitability, Sharpe, consistency, and drawdown discipline.
                </p>
              </div>
              <span className="rounded-full border border-slate-600 bg-slate-900/60 px-3 py-1 text-xs text-slate-300">
                {intelligence.strategies.length} ranked
              </span>
            </div>
          </div>

          {intelligence.strategies.length === 0 ? (
            <div className="px-6 py-10 text-sm text-slate-400">
              No completed backtests yet. Launch your first backtest from the dashboard and rankings will appear here.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-900/45 text-xs uppercase tracking-[0.16em] text-slate-500">
                  <tr>
                    <th className="px-6 py-3 text-left">Rank</th>
                    <th className="px-6 py-3 text-left">Strategy / Setup</th>
                    <th className="px-6 py-3 text-right">Runs</th>
                    <th className="px-6 py-3 text-right">Total P&amp;L</th>
                    <th className="px-6 py-3 text-right">Win Rate</th>
                    <th className="px-6 py-3 text-right">Sharpe</th>
                    <th className="px-6 py-3 text-right">Drawdown</th>
                  </tr>
                </thead>
                <tbody>
                  {intelligence.strategies.slice(0, 8).map((strategy, index) => (
                    <tr key={strategy.key} className="border-t border-slate-700/50 text-slate-300">
                      <td className="px-6 py-4">
                        <span className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-600 bg-slate-900/70 text-xs font-semibold text-white">
                          {index + 1}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <p className="font-medium text-white">{strategy.label}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          {strategy.completedRuns} completed
                          {strategy.activeRuns > 0 ? ` · ${strategy.activeRuns} active` : ''}
                          {strategy.lastRunAt ? ` · last run ${formatDateTime(strategy.lastRunAt)}` : ''}
                        </p>
                      </td>
                      <td className="px-6 py-4 text-right">{strategy.totalRuns}</td>
                      <td
                        className={`px-6 py-4 text-right font-semibold ${
                          strategy.totalPnl >= 0 ? 'text-green-400' : 'text-red-400'
                        }`}
                      >
                        {formatCurrency(strategy.totalPnl)}
                      </td>
                      <td className="px-6 py-4 text-right">{formatPercent(strategy.avgWinRatePct)}</td>
                      <td className="px-6 py-4 text-right">{strategy.avgSharpe.toFixed(2)}</td>
                      <td className="px-6 py-4 text-right">{formatPercent(strategy.avgDrawdownPct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="space-y-6">
          <div className="rounded-2xl border border-slate-700/60 bg-slate-800/60 p-5 backdrop-blur-sm">
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
              <p className="text-sm text-slate-400">Top runs will appear after your first completed backtest.</p>
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
                        <p className="mt-1 text-xs text-slate-500">{formatDateTime(run.created_at)}</p>
                      </div>
                      <ChevronRight className="h-4 w-4 shrink-0 text-slate-500" />
                    </div>
                    <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
                      <div>
                        <p className="text-slate-500">P&amp;L</p>
                        <p className={`font-semibold ${safeNumber(run.total_pnl) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {formatCurrency(safeNumber(run.total_pnl))}
                        </p>
                      </div>
                      <div>
                        <p className="text-slate-500">Sharpe</p>
                        <p className="font-semibold text-slate-200">{safeNumber(run.sharpe_ratio).toFixed(2)}</p>
                      </div>
                      <div>
                        <p className="text-slate-500">Win Rate</p>
                        <p className="font-semibold text-slate-200">{formatPercent(normalizePercent(run.win_rate))}</p>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-slate-700/60 bg-slate-800/60 p-5 backdrop-blur-sm">
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
              <li>Drawdown is treated as a risk penalty, so high-return but unstable setups won’t dominate unfairly.</li>
              <li>Strategies with more completed runs receive a confidence boost over single lucky outliers.</li>
              <li>Click any run below to inspect the full detailed report before promoting a setup to live runtime.</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-white">All Backtests</h2>
            <p className="text-sm text-slate-400">Every run, with live updates for active jobs.</p>
          </div>
          <Link
            to="/dashboard"
            className="inline-flex items-center gap-2 rounded-lg border border-slate-600 bg-slate-800 px-4 py-2 text-sm font-medium text-slate-200 transition hover:bg-slate-700"
          >
            Launch a new backtest
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
        <BacktestList />
      </section>
    </PageContainer>
  );
};
