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
import { BacktestList } from '../components/BacktestList';
import { CodexAssetIntelStrip } from '../components/CodexAssetIntelStrip';
import { PageContainer } from '../components/PageContainer';
import { TerminalDataGrid, type TerminalColumn } from '../components/TerminalDataGrid';
import {
  type BacktestRun,
  buildIntelligence,
  extractBacktestRuns,
  formatCurrency,
  formatDateTime,
  formatPercent,
  isActiveBacktestRun,
  normalizePercent,
  safeNumber,
  type StrategyAggregate,
  type StrategyRef,
} from '../features/backtests/intelligence';
import { buildBacktestIntelRequest } from '../features/codex/marketIntel';

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
      return extractBacktestRuns(response);
    },
    staleTime: 10_000,
    refetchInterval: (query) =>
      (query.state.data ?? []).some((run) => isActiveBacktestRun(run as BacktestRun))
        ? 4_000
        : false,
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

  const intelligence = useMemo(
    () => buildIntelligence(backtestsQuery.data ?? [], strategiesById),
    [backtestsQuery.data, strategiesById]
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
      <section className="operator-hero px-6 py-6 sm:px-8 sm:py-8">
        <div className="relative grid gap-6 xl:grid-cols-[1.15fr,0.85fr]">
          <div>
            <div className="surface-label">
              <Sparkles className="h-3.5 w-3.5" />
              Backtest intelligence
            </div>
            <h1 className="mt-5 max-w-3xl text-3xl font-bold tracking-tight text-white sm:text-4xl">
              See every run, then decide which strategy actually deserves trust.
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">
              This page is tuned like a research control room: live activity near the top, weighted
              quality metrics, terminal-grade strategy ranking, and clearer notes about what should
              and should not influence promotion decisions.
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
            intelligence.mostConsistentStrategy && intelligence.mostConsistentStrategy.totalPnl >= 0
              ? 'text-green-400'
              : 'text-red-400'
          }
        />
      </section>

      <CodexAssetIntelStrip title="Assets Behind Your Top Runs" request={backtestIntelRequest} />

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
              No completed backtests yet. Launch your first run from the dashboard and the
              leaderboard will populate here.
            </div>
          }
        />

        <div className="space-y-6">
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
                Click any run below to inspect the full detailed report before promoting a setup to
                live runtime.
              </li>
            </ul>
          </div>
        </div>
      </section>

      <section className="operator-section-card p-5 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-white">All Backtests</h2>
            <p className="text-sm text-slate-400">
              Every run, with soft refresh behavior for active jobs and detail views one click away.
            </p>
          </div>
          <Link
            to="/dashboard"
            className="premium-button premium-button-secondary rounded-[1rem] px-4 py-2 text-sm"
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
