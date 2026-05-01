import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Layers3, Search, Sparkles } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { useLocation, useNavigate } from 'react-router-dom';
import api from '../api';
import { PageContainer } from './PageContainer';

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (isRecord(error) && isRecord(error.response) && isRecord(error.response.data)) {
    const data = error.response.data as Record<string, unknown>;
    if (typeof data.message === 'string' && data.message.length > 0) return data.message;
    if (typeof data.detail === 'string' && data.detail.length > 0) return data.detail;
  }

  if (error instanceof Error) return error.message;
  return fallback;
};

const getErrorStatus = (error: unknown): number | null => {
  if (!isRecord(error) || !isRecord(error.response)) return null;
  const status = error.response.status;
  return typeof status === 'number' ? status : null;
};

const extractRunId = (response: unknown): string | null => {
  if (!isRecord(response)) return null;
  if (typeof response.run_id === 'string') return response.run_id;

  const nested = response.data;
  if (isRecord(nested) && typeof nested.run_id === 'string') return nested.run_id;
  return null;
};

interface Strategy {
  id: number;
  name: string;
  category: string;
  description: string;
  pair_selection_mode?: 'liquidity' | 'volatility' | 'cointegration' | 'input';
  selected_markets?: string[];
  zscore_threshold: number;
  stats_window: number;
  max_half_life: number;
  usd_per_trade: number;
  usd_min_collateral: number;
  close_at_zscore_cross: boolean;
  find_cointegrated_pairs: boolean;
  manage_exits: boolean;
  place_trades: boolean;
  abort_all_positions: boolean;
  max_positions: number;
  max_drawdown_pct: number;
  stop_loss_pct: number;
  take_profit_pct: number;
  trailing_stop_pct: number;
  rebalance_interval_hours: number;
  position_timeout_hours: number;
  transaction_fee?: number;
  slippage?: number;
  starting_balance?: number;
  resolution?: string;
  candle_resolution?: string;
  max_history_days?: number;
  benchmark_symbol?: string;
  risk_free_rate?: number;
  initial_amount?: number;
  is_public: boolean;
  created_at: string;
  updated_at: string;
}

interface StrategyListResult {
  strategies: Strategy[];
  total: number;
}

interface StrategyBacktestRunPayload extends Record<string, unknown> {
  start_date: string;
  end_date: string;
  name: string;
  description: string;
  strategy_id: number;
  initial_balance?: number;
  pair_selection_mode?: 'liquidity' | 'volatility' | 'cointegration' | 'input';
  pairs?: string[];
  trading_parameters: Record<string, unknown>;
}

const ITEMS_PER_PAGE = 10;
const strategyLibraryQueryKey = (page: number) => ['strategies', 'library', page] as const;

const fetchStrategiesPage = async (page: number): Promise<StrategyListResult> => {
  const response = await api.listStrategies(page * ITEMS_PER_PAGE, ITEMS_PER_PAGE);
  const payload = response.data;
  return {
    strategies: Array.isArray(payload?.strategies) ? (payload.strategies as Strategy[]) : [],
    total: typeof payload?.total === 'number' ? payload.total : 0,
  };
};

export default function StrategyLibrary() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [successToast, setSuccessToast] = useState<{ message: string; strategyId?: number } | null>(
    null
  );
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(0);
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);
  const [runModalOpen, setRunModalOpen] = useState(false);
  const [selectedStrategy, setSelectedStrategy] = useState<Strategy | null>(null);
  const [backtestStartDate, setBacktestStartDate] = useState('');
  const [backtestEndDate, setBacktestEndDate] = useState('');
  const [runError, setRunError] = useState<string | null>(null);
  const secondaryActionButtonClass =
    'flex-1 rounded-xl border border-slate-700/70 bg-slate-900/70 px-3 py-2 text-sm font-medium text-white transition hover:border-cyan-500/35 hover:bg-slate-900';
  const statsTileClass = 'workspace-card px-4 py-4';

  const strategiesQuery = useQuery({
    queryKey: strategyLibraryQueryKey(currentPage),
    queryFn: () => fetchStrategiesPage(currentPage),
    staleTime: 60 * 1000,
    refetchOnMount: 'always',
  });

  const deleteMutation = useMutation({
    mutationFn: (strategyId: number) => api.deleteStrategy(strategyId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['strategies'] });
    },
  });

  const duplicateMutation = useMutation({
    mutationFn: async (strategy: Strategy) => {
      const {
        id: _id,
        created_at: _created_at,
        updated_at: _updated_at,
        ...newStrategy
      } = strategy;
      return api.createStrategy({
        ...newStrategy,
        name: `${strategy.name} (Copy)`,
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['strategies'] });
    },
  });

  const runBacktestMutation = useMutation({
    mutationFn: (payload: StrategyBacktestRunPayload) => api.runBacktest(payload),
  });

  const strategies = strategiesQuery.data?.strategies ?? [];
  const totalStrategies = strategiesQuery.data?.total ?? 0;

  const filteredStrategies = useMemo(
    () =>
      strategies.filter(
        (s) =>
          s.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
          s.description.toLowerCase().includes(searchTerm.toLowerCase())
      ),
    [searchTerm, strategies]
  );

  const totalPages = Math.ceil(totalStrategies / ITEMS_PER_PAGE);

  useEffect(() => {
    const navState = (location.state ?? null) as Record<string, unknown> | null;
    const toastMessage =
      navState && typeof navState.strategyToast === 'string' ? navState.strategyToast : null;
    const toastStrategyId =
      navState && typeof navState.strategyId === 'number' ? navState.strategyId : undefined;
    if (!toastMessage) return;

    setSuccessToast({ message: toastMessage, strategyId: toastStrategyId });
    navigate(`${location.pathname}${location.search}`, { replace: true, state: null });
  }, [location.pathname, location.search, location.state, navigate]);

  useEffect(() => {
    if (!successToast) return;
    const timer = window.setTimeout(() => setSuccessToast(null), 3200);
    return () => window.clearTimeout(timer);
  }, [successToast]);

  const handleDelete = async (strategyId: number) => {
    try {
      setError(null);
      await deleteMutation.mutateAsync(strategyId);
      setDeleteConfirmId(null);
    } catch (err: unknown) {
      console.error('Failed to delete strategy:', err);
      setError(getErrorMessage(err, 'Failed to delete strategy'));
    }
  };

  const handleDuplicate = async (strategy: Strategy) => {
    try {
      setError(null);
      await duplicateMutation.mutateAsync(strategy);
    } catch (err: unknown) {
      console.error('Failed to duplicate strategy:', err);
      setError(getErrorMessage(err, 'Failed to duplicate strategy'));
    }
  };

  const handleRunStrategy = (strategy: Strategy) => {
    setSelectedStrategy(strategy);
    setRunModalOpen(true);
    setRunError(null);
    const endDate = new Date();
    const startDate = new Date(endDate);
    startDate.setDate(startDate.getDate() - 30);
    setBacktestStartDate(startDate.toISOString().split('T')[0]);
    setBacktestEndDate(endDate.toISOString().split('T')[0]);
  };

  const buildRunPayload = (): StrategyBacktestRunPayload | null => {
    if (!selectedStrategy || !backtestStartDate || !backtestEndDate) return null;
    const pairSelectionMode = selectedStrategy.pair_selection_mode || 'liquidity';
    const resolution = selectedStrategy.resolution || selectedStrategy.candle_resolution || '1HOUR';
    const strategyBenchmark = selectedStrategy.benchmark_symbol?.trim();
    // benchmark_symbol is a performance-comparison reference, not a trading market.
    // Never derive it from selected_markets — only use strategy config or default to BTC-USD.
    const benchmarkSymbol =
      strategyBenchmark && strategyBenchmark.length > 0 ? strategyBenchmark : 'BTC-USD';
    const tradingParameters: Record<string, unknown> = {
      zscore_threshold: selectedStrategy.zscore_threshold,
      stats_window: selectedStrategy.stats_window,
      max_half_life: selectedStrategy.max_half_life,
      usd_per_trade: selectedStrategy.usd_per_trade,
      usd_min_collateral: selectedStrategy.usd_min_collateral,
      close_at_zscore_cross: selectedStrategy.close_at_zscore_cross,
      find_cointegrated_pairs: selectedStrategy.find_cointegrated_pairs,
      manage_exits: selectedStrategy.manage_exits,
      place_trades: selectedStrategy.place_trades,
      abort_all_positions: selectedStrategy.abort_all_positions,
      max_positions: selectedStrategy.max_positions,
      max_drawdown_pct: selectedStrategy.max_drawdown_pct,
      stop_loss_pct: selectedStrategy.stop_loss_pct,
      take_profit_pct: selectedStrategy.take_profit_pct,
      trailing_stop_pct: selectedStrategy.trailing_stop_pct,
      rebalance_interval_hours: selectedStrategy.rebalance_interval_hours,
      position_timeout_hours: selectedStrategy.position_timeout_hours,
      transaction_fee: selectedStrategy.transaction_fee ?? 0.0005,
      slippage: selectedStrategy.slippage ?? 0.001,
      risk_free_rate: selectedStrategy.risk_free_rate ?? 0.02,
      benchmark_symbol: benchmarkSymbol,
      max_history_days: selectedStrategy.max_history_days ?? 90,
      resolution,
      candle_resolution: resolution,
      pair_selection_mode: pairSelectionMode,
    };

    return {
      start_date: backtestStartDate,
      end_date: backtestEndDate,
      name: `${selectedStrategy.name} Backtest`,
      description: selectedStrategy.description || `Backtest for strategy ${selectedStrategy.name}`,
      strategy_id: selectedStrategy.id,
      initial_balance: selectedStrategy.starting_balance ?? selectedStrategy.initial_amount ?? 1000,
      pair_selection_mode: pairSelectionMode,
      ...(selectedStrategy.selected_markets?.length
        ? { pairs: selectedStrategy.selected_markets }
        : {}),
      trading_parameters: tradingParameters,
    };
  };

  const handleExecuteBacktest = async () => {
    if (!selectedStrategy || !backtestStartDate || !backtestEndDate) {
      setRunError('Please enter valid start and end dates');
      return;
    }

    const strategyMode = selectedStrategy.pair_selection_mode || 'liquidity';
    const hasMarkets =
      Array.isArray(selectedStrategy.selected_markets) &&
      selectedStrategy.selected_markets.length >= 2;
    if (strategyMode === 'input' && !hasMarkets) {
      setRunError(
        'This strategy uses manual pair selection ("input" mode) but has no markets configured. Edit the strategy to add at least two markets before running a backtest.'
      );
      return;
    }

    try {
      setRunError(null);

      const runPayload = buildRunPayload();
      if (!runPayload) {
        setRunError('Unable to build backtest payload. Please check dates and strategy.');
        return;
      }

      const response = await runBacktestMutation.mutateAsync(runPayload);
      const runId = extractRunId(response);
      if (runId) {
        navigate(`/backtest/${runId}`);
        setRunModalOpen(false);
        setSelectedStrategy(null);
      } else {
        setRunError('Backtest started but no run ID returned');
      }
    } catch (err: unknown) {
      console.error('❌ Failed to run backtest:', {
        status: isRecord(err) && isRecord(err.response) ? err.response.status : undefined,
        statusText: isRecord(err) && isRecord(err.response) ? err.response.statusText : undefined,
        message: getErrorMessage(err, 'Failed to run backtest'),
        data: isRecord(err) && isRecord(err.response) ? err.response.data : undefined,
      });

      const status = getErrorStatus(err);
      if (status === 401) {
        setRunError('Your session has expired. Please login again.');
      } else if (status === 403) {
        setRunError('You do not have permission to run this backtest.');
      } else if (status === 404) {
        setRunError('Strategy not found. It may have been deleted.');
      } else {
        setRunError(getErrorMessage(err, 'Failed to run backtest'));
      }
    }
  };

  if (strategiesQuery.isLoading && strategies.length === 0) {
    return (
      <PageContainer size="wide" className="flex min-h-[60vh] items-center justify-center">
        <div className="premium-panel w-full max-w-md py-10 text-center">
          <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-b-2 border-blue-500"></div>
          <p className="text-base font-medium text-white">Loading strategies...</p>
          <p className="mt-2 text-sm text-slate-500">
            Preparing your workspace library and filters.
          </p>
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer size="wide">
      <section className="premium-hero mb-8 px-6 py-7 sm:px-8">
        <div className="premium-orb -right-10 top-0 h-40 w-40 bg-cyan-500/10" />
        <div className="premium-orb -left-6 bottom-0 h-36 w-36 bg-emerald-500/10" />
        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <div className="premium-kicker">Strategy Library</div>
            <h1 className="mt-4 text-3xl font-bold text-white sm:text-4xl">
              Build, compare, and launch strategies that look ready for real capital.
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
              Your strategy workspace now feels like an operating system, not a form. Search faster,
              inspect risk posture at a glance, and move directly into live runtime or backtesting.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 justify-end">
            <button
              onClick={() => navigate('/strategies/manage')}
              className="premium-button premium-button-secondary"
            >
              Managed Runtimes
            </button>
            <button
              onClick={() => navigate('/bots')}
              className="premium-button premium-button-secondary"
            >
              Bots
            </button>
            <button
              onClick={() => navigate('/strategies/new')}
              className="premium-button premium-button-primary"
            >
              New Strategy
            </button>
          </div>
        </div>
      </section>

      {successToast && (
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-emerald-200 animate-fade-slide-up">
          <p className="text-sm font-medium">✅ {successToast.message}</p>
          {successToast.strategyId && (
            <button
              onClick={() => navigate(`/strategies/${successToast.strategyId}/edit`)}
              className="rounded-lg border border-emerald-400/40 bg-emerald-500/15 px-3 py-1.5 text-xs font-semibold text-emerald-100 transition hover:bg-emerald-500/25"
            >
              View strategy
            </button>
          )}
        </div>
      )}

      {(error || strategiesQuery.isError) && (
        <div className="mb-6 rounded-xl border border-red-500 bg-red-500/10 px-4 py-3">
          <p className="text-red-400">
            {error || getErrorMessage(strategiesQuery.error, 'Failed to load strategies')}
          </p>
        </div>
      )}

      <section className="premium-panel mb-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-3">
            <div className="premium-icon-wrap text-cyan-300">
              <Search className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Search and compare faster</h2>
              <p className="mt-1 text-sm text-slate-400">
                Filter by narrative, inspect risk posture at a glance, and move straight into
                action.
              </p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:min-w-85">
            <div className={statsTileClass}>
              <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Visible</p>
              <p className="mt-1 text-lg font-semibold text-white">{filteredStrategies.length}</p>
            </div>
            <div className={statsTileClass}>
              <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
                Library total
              </p>
              <p className="mt-1 text-lg font-semibold text-white">{totalStrategies}</p>
            </div>
          </div>
        </div>
        <div className="relative mt-5">
          <Search className="pointer-events-none absolute left-4 top-3.5 h-4 w-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search strategies by name, narrative, or description..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="premium-input pl-11"
          />
        </div>
      </section>

      {filteredStrategies.length === 0 ? (
        <div className="premium-panel py-12 text-center">
          <div className="workspace-card mx-auto flex h-16 w-16 items-center justify-center rounded-3xl text-cyan-300">
            <Sparkles className="h-7 w-7" />
          </div>
          <p className="mb-2 mt-5 text-base font-medium text-slate-300">
            {strategies.length === 0
              ? 'No strategies yet. Create one to get started!'
              : 'No strategies match your search.'}
          </p>
          <p className="mb-4 text-sm text-slate-500">
            Adjust the search phrase or start a new strategy from a clean template.
          </p>
          {strategies.length === 0 && (
            <button
              onClick={() => navigate('/strategies/new')}
              className="premium-button premium-button-primary"
            >
              Create First Strategy
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {filteredStrategies.map((strategy) => (
            <div
              key={strategy.id}
              className="premium-panel premium-panel-hover animate-fade-slide-up p-6"
            >
              <div className="flex justify-between items-start mb-3">
                <div className="flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-lg font-semibold text-white mb-1">{strategy.name}</h3>
                    <span className="inline-flex items-center rounded-full border border-slate-700/70 bg-slate-950/50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                      <Layers3 className="mr-1.5 h-3 w-3" />
                      {strategy.category}
                    </span>
                  </div>
                  <p className="text-slate-400 text-sm mb-2">{strategy.description}</p>
                  <div className="flex gap-3 flex-wrap">
                    {strategy.is_public && (
                      <span className="inline-block rounded-full border border-blue-500/20 bg-blue-500/10 px-2.5 py-1 text-xs text-blue-300">
                        🌐 Public
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4 my-4 border-t border-slate-700/70 py-4 sm:grid-cols-2 xl:grid-cols-4">
                <div className="workspace-card p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    Z-Score Threshold
                  </p>
                  <p className="text-lg font-semibold text-cyan-300">{strategy.zscore_threshold}</p>
                </div>
                <div className="workspace-card p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    Stats Window (h)
                  </p>
                  <p className="text-lg font-semibold text-cyan-300">{strategy.stats_window}</p>
                </div>
                <div className="workspace-card p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    Max Half-Life (h)
                  </p>
                  <p className="text-lg font-semibold text-cyan-300">{strategy.max_half_life}</p>
                </div>
                <div className="workspace-card p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                    Max History Days
                  </p>
                  <p className="text-lg font-semibold text-cyan-300">
                    {strategy.max_history_days ?? 90}
                  </p>
                </div>
              </div>

              <div className="mb-4 text-xs text-slate-500">
                Updated: {new Date(strategy.updated_at).toLocaleDateString()} at{' '}
                {new Date(strategy.updated_at).toLocaleTimeString()}
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => handleRunStrategy(strategy)}
                  className="flex-1 rounded-xl border border-emerald-900/15 bg-emerald-700 px-3 py-2 text-sm font-medium text-white shadow-sm shadow-emerald-950/10 transition hover:bg-emerald-600"
                >
                  Run Backtest
                </button>
                <button
                  onClick={() => navigate(`/backtests/new?strategy_id=${strategy.id}`)}
                  className={secondaryActionButtonClass}
                >
                  New Ticket
                </button>
                <button
                  onClick={() => navigate(`/strategies/${strategy.id}/edit`)}
                  className={secondaryActionButtonClass}
                >
                  Edit
                </button>
                <button
                  onClick={() => void handleDuplicate(strategy)}
                  disabled={duplicateMutation.isPending}
                  className={`${secondaryActionButtonClass} disabled:opacity-60`}
                >
                  Duplicate
                </button>
                {deleteConfirmId === strategy.id ? (
                  <>
                    <button
                      onClick={() => void handleDelete(strategy.id)}
                      disabled={deleteMutation.isPending}
                      className="flex-1 rounded-xl bg-red-600 px-3 py-2 text-white text-sm font-medium transition hover:bg-red-500 disabled:opacity-60"
                    >
                      Confirm Delete
                    </button>
                    <button
                      onClick={() => setDeleteConfirmId(null)}
                      className={secondaryActionButtonClass}
                    >
                      Cancel
                    </button>
                  </>
                ) : (
                  <button
                    onClick={() => setDeleteConfirmId(strategy.id)}
                    className="flex-1 rounded-xl border border-slate-700/70 bg-slate-900/70 px-3 py-2 text-sm font-medium text-white transition hover:border-red-500/35 hover:bg-slate-900"
                  >
                    🗑️ Delete
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <div className="mt-8 flex justify-center gap-2">
          <button
            onClick={() => setCurrentPage(Math.max(0, currentPage - 1))}
            disabled={currentPage === 0}
            className="rounded-2xl border border-slate-700/70 bg-slate-900/60 px-4 py-2 text-white transition hover:border-cyan-500/35 hover:bg-slate-900 disabled:opacity-50"
          >
            ← Previous
          </button>
          <div className="flex items-center gap-2">
            {Array.from({ length: totalPages }, (_, i) => (
              <button
                key={i}
                onClick={() => setCurrentPage(i)}
                className={`px-3 py-2 rounded transition ${
                  currentPage === i
                    ? 'bg-cyan-600 text-white'
                    : 'border border-slate-700/70 bg-slate-900/60 text-gray-300 hover:border-cyan-500/35 hover:bg-slate-900'
                }`}
              >
                {i + 1}
              </button>
            ))}
          </div>
          <button
            onClick={() => setCurrentPage(Math.min(totalPages - 1, currentPage + 1))}
            disabled={currentPage === totalPages - 1}
            className="rounded-2xl border border-slate-700/70 bg-slate-900/60 px-4 py-2 text-white transition hover:border-cyan-500/35 hover:bg-slate-900 disabled:opacity-50"
          >
            Next →
          </button>
        </div>
      )}

      {runModalOpen &&
        selectedStrategy &&
        typeof document !== 'undefined' &&
        createPortal(
          <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-950/70 p-4 backdrop-blur-sm">
            <div className="premium-panel my-6 w-full max-w-md max-h-[calc(100vh-3rem)] overflow-y-auto">
              <h2 className="text-xl font-bold text-white mb-4">
                Run Backtest: {selectedStrategy.name}
              </h2>

              <div className="workspace-card mb-4 p-4">
                <p className="mb-2 text-sm text-slate-400">Strategy Parameters:</p>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="text-slate-300">
                    Z-Score:{' '}
                    <span className="text-cyan-300">{selectedStrategy.zscore_threshold}</span>
                  </div>
                  <div className="text-slate-300">
                    Stats Window:{' '}
                    <span className="text-cyan-300">{selectedStrategy.stats_window}h</span>
                  </div>
                  <div className="text-slate-300">
                    Max Positions:{' '}
                    <span className="text-cyan-300">{selectedStrategy.max_positions}</span>
                  </div>
                  <div className="text-slate-300">
                    USD/Trade:{' '}
                    <span className="text-cyan-300">${selectedStrategy.usd_per_trade}</span>
                  </div>
                  <div className="text-slate-300">
                    Max Drawdown:{' '}
                    <span className="text-cyan-300">{selectedStrategy.max_drawdown_pct}%</span>
                  </div>
                  <div className="text-slate-300">
                    Stop Loss:{' '}
                    <span className="text-cyan-300">{selectedStrategy.stop_loss_pct}%</span>
                  </div>
                </div>
              </div>

              {runError && (
                <div className="mb-4 rounded-lg border border-red-500 bg-red-500/10 p-3 text-sm text-red-400">
                  {runError}
                </div>
              )}

              <div className="space-y-3 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">Start Date</label>
                  <input
                    type="date"
                    value={backtestStartDate}
                    onChange={(e) => setBacktestStartDate(e.target.value)}
                    className="premium-input"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">End Date</label>
                  <input
                    type="date"
                    value={backtestEndDate}
                    onChange={(e) => setBacktestEndDate(e.target.value)}
                    className="premium-input"
                  />
                </div>
              </div>

              <div className="workspace-card mb-4 p-3">
                <p className="text-xs text-slate-300 mb-2">Request payload preview</p>
                <pre className="text-[11px] text-slate-400 whitespace-pre-wrap break-all">
                  {JSON.stringify(buildRunPayload(), null, 2)}
                </pre>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => void handleExecuteBacktest()}
                  disabled={runBacktestMutation.isPending}
                  className="flex-1 rounded border border-emerald-900/15 bg-emerald-700 px-4 py-2 font-medium text-white shadow-sm shadow-emerald-950/10 transition hover:bg-emerald-600 disabled:bg-emerald-700/50"
                >
                  {runBacktestMutation.isPending ? 'Running...' : '▶️ Run Backtest'}
                </button>
                <button
                  onClick={() => {
                    setRunModalOpen(false);
                    setSelectedStrategy(null);
                    setRunError(null);
                  }}
                  disabled={runBacktestMutation.isPending}
                  className="flex-1 rounded border border-slate-700/70 bg-slate-900/70 px-4 py-2 font-medium text-white transition hover:border-cyan-500/35 hover:bg-slate-900 disabled:opacity-60"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>,
          document.body
        )}
    </PageContainer>
  );
}
