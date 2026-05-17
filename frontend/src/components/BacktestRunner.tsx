import { useMutation } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import { Play } from 'lucide-react';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import api, {
    DYDX_CANDLE_RESOLUTION_OPTIONS,
    normalizeDydxCandleResolution,
    type PerpetualMarketsResponse,
} from '../api';
import { extractBacktestRuns, isActiveBacktestRun } from '../features/backtests/intelligence';
import { useStrategyStore } from '../store/strategies';
import { useToastStore } from './ErrorBoundary';
import { InlineNotice } from './ui/PlatformUI';

interface TradingParameters {
  [key: string]: unknown;
  zscore_threshold?: number;
  stats_window?: number;
  max_half_life?: number;
  usd_per_trade?: number;
  usd_min_collateral?: number;
  close_at_zscore_cross?: boolean;
  find_cointegrated_pairs?: boolean;
  manage_exits?: boolean;
  place_trades?: boolean;
  abort_all_positions?: boolean;
  max_positions?: number;
  max_drawdown_pct?: number;
  stop_loss_pct?: number;
  take_profit_pct?: number;
  trailing_stop_pct?: number;
  rebalance_interval_hours?: number;
  position_timeout_hours?: number;
  resolution?: string;
  candle_resolution?: string;
  transaction_fee?: number;
  slippage?: number;
  risk_free_rate?: number;
  benchmark_symbol?: string;
  max_history_days?: number;
  pair_selection_mode?: 'liquidity' | 'volatility' | 'cointegration' | 'input';
}

interface BacktestRunRequest {
  [key: string]: unknown;
  start_date: string;
  end_date: string;
  name?: string;
  description?: string;
  initial_balance?: number;
  max_pairs?: number;
  pairs?: string[];
  strategy_id?: number;
  benchmark_symbol?: string;
  pair_selection_mode?: 'liquidity' | 'volatility' | 'cointegration' | 'input';
  trading_parameters: TradingParameters;
}

const toRecord = (value: unknown): Record<string, unknown> =>
  typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : {};

const getErrorMessage = (error: unknown, fallback: string): string => {
  const errRecord = toRecord(error);
  const response = toRecord(errRecord.response);
  const data = toRecord(response.data);
  const messageFromApi = data.message;
  if (typeof messageFromApi === 'string' && messageFromApi.length > 0) {
    return messageFromApi;
  }
  return error instanceof Error ? error.message : fallback;
};

const toPositiveInteger = (value: unknown): number | null => {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
};

const extractUserBacktestQuota = (payload: unknown): number | null => {
  const root = toRecord(payload);
  const data = toRecord(root.data);
  return (
    toPositiveInteger(data.max_active_backtests) ?? toPositiveInteger(root.max_active_backtests)
  );
};

const countActiveBacktests = (payload: unknown): number =>
  extractBacktestRuns(payload).filter((run) => isActiveBacktestRun(run)).length;

const extractRunId = (result: unknown): string | null => {
  const record = toRecord(result);
  if (typeof record.run_id === 'string') return record.run_id;
  const nested = toRecord(record.data);
  return typeof nested.run_id === 'string' ? nested.run_id : null;
};

export const BacktestRunner: React.FC<{ onBacktestComplete?: () => void }> = ({
  onBacktestComplete,
}) => {
  type ApiBacktestRequest = Parameters<typeof api.runBacktest>[0];
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { strategies, fetchStrategies } = useStrategyStore();
  const successToast = useToastStore((state) => state.success);
  const errorToast = useToastStore((state) => state.error);
  const warningToast = useToastStore((state) => state.warning);
  const [useStrategy, setUseStrategy] = useState(false);
  const [selectedStrategyId, setSelectedStrategyId] = useState<number | null>(null);
  const [formData, setFormData] = useState<BacktestRunRequest>({
    start_date: '2024-01-01',
    end_date: '2024-03-31',
    name: 'ui-backtest',
    initial_balance: 1000,
    benchmark_symbol: 'BTC-USD',
    max_pairs: 0,
    pair_selection_mode: 'liquidity',
    trading_parameters: {
      resolution: '1HOUR',
      zscore_threshold: 1.5,
      stats_window: 21,
      usd_per_trade: 10,
      transaction_fee: 0.0005,
      slippage: 0.001,
      risk_free_rate: 0.02,
      max_history_days: 90,
      benchmark_symbol: 'BTC-USD',
      pair_selection_mode: 'liquidity',
    },
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [availableMarkets, setAvailableMarkets] = useState<string[]>([]);
  const [selectedMarkets, setSelectedMarkets] = useState<string[]>([]);
  const [marketsLoading, setMarketsLoading] = useState(false);
  const [marketsError, setMarketsError] = useState<string | null>(null);
  const [marketsSource, setMarketsSource] = useState<string>('unknown');
  const [marketsStale, setMarketsStale] = useState(false);
  const requestedStrategyId = useMemo(() => {
    const raw = searchParams.get('strategy_id');
    const parsed = raw ? Number(raw) : NaN;
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  }, [searchParams]);
  const presets = [
    {
      id: 'disciplined',
      label: 'Disciplined',
      description: 'Higher threshold, tighter size, safer first-pass evaluation.',
      values: { zscore_threshold: 1.8, usd_per_trade: 8, stats_window: 30, max_pairs: 8 },
    },
    {
      id: 'balanced',
      label: 'Balanced',
      description: 'Default desk preset for general signal review.',
      values: { zscore_threshold: 1.5, usd_per_trade: 12, stats_window: 21, max_pairs: 12 },
    },
    {
      id: 'exploratory',
      label: 'Exploratory',
      description: 'Broader market search for idea generation and route discovery.',
      values: { zscore_threshold: 1.25, usd_per_trade: 15, stats_window: 14, max_pairs: 20 },
    },
  ] as const;

  const runBacktestMutation = useMutation({
    mutationFn: (payload: ApiBacktestRequest) => api.runBacktest(payload),
  });

  // Fetch strategies on mount
  useEffect(() => {
    void fetchStrategies();
  }, [fetchStrategies]);

  useEffect(() => {
    let cancelled = false;

    const loadMarkets = async () => {
      setMarketsLoading(true);
      setMarketsError(null);
      try {
        const response = await api.getPerpetualMarkets(120);
        const markets = Array.isArray(response.data?.markets) ? response.data.markets : [];
        const responseData = (response.data || {}) as PerpetualMarketsResponse;
        const source = String(responseData.source || 'unknown');
        const staticFallback =
          Boolean(responseData.static_fallback) || source.trim().toLowerCase() === 'static_fallback';
        if (!cancelled) {
          if (staticFallback) {
            setAvailableMarkets([]);
            setMarketsSource(source);
            setMarketsStale(false);
            setMarketsError('Market list came from a static fallback. Live dYdX data is required.');
            return;
          }
          setAvailableMarkets(markets);
          setMarketsSource(source);
          setMarketsStale(Boolean(responseData.cache_stale));
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setMarketsError(getErrorMessage(err, 'Unable to load dYdX markets'));
        }
      } finally {
        if (!cancelled) {
          setMarketsLoading(false);
        }
      }
    };

    void loadMarkets();
    return () => {
      cancelled = true;
    };
  }, []);

  const TRADING_PARAM_FIELDS = new Set([
    'zscore_threshold',
    'stats_window',
    'max_half_life',
    'usd_per_trade',
    'usd_min_collateral',
    'close_at_zscore_cross',
    'find_cointegrated_pairs',
    'manage_exits',
    'place_trades',
    'abort_all_positions',
    'max_positions',
    'max_drawdown_pct',
    'stop_loss_pct',
    'take_profit_pct',
    'trailing_stop_pct',
    'rebalance_interval_hours',
    'position_timeout_hours',
    'resolution',
    'transaction_fee',
    'slippage',
    'risk_free_rate',
    'benchmark_symbol',
    'max_history_days',
    'pair_selection_mode',
  ]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    if (TRADING_PARAM_FIELDS.has(name)) {
      setFormData((prev) => ({
        ...prev,
        trading_parameters: {
          ...prev.trading_parameters,
          [name]:
            name === 'stats_window' ||
            name === 'max_positions' ||
            name === 'max_history_days' ||
            name === 'rebalance_interval_hours' ||
            name === 'position_timeout_hours'
              ? parseInt(value)
              : name === 'zscore_threshold' ||
                  name === 'usd_per_trade' ||
                  name === 'max_half_life' ||
                  name === 'usd_min_collateral' ||
                  name === 'max_drawdown_pct' ||
                  name === 'stop_loss_pct' ||
                  name === 'take_profit_pct' ||
                  name === 'trailing_stop_pct' ||
                  name === 'transaction_fee' ||
                  name === 'slippage' ||
                  name === 'risk_free_rate'
                ? parseFloat(value)
                : value,
        },
      }));
    } else {
      setFormData((prev) => ({
        ...prev,
        [name]: name === 'max_pairs' || name === 'initial_balance' ? parseInt(value) : value,
      }));
    }
  };

  const applyStrategyDefaults = useCallback(
    (id: number | null, enabled: boolean) => {
      setSelectedStrategyId(id);

      if (id && enabled) {
        const strategy = strategies.find((s) => s.id === id);
        if (strategy) {
          const strategyMarkets = Array.isArray(strategy.selected_markets)
            ? strategy.selected_markets
            : [];
          setSelectedMarkets(strategyMarkets.slice(0, 20));
          setFormData((prev) => ({
            ...prev,
            strategy_id: id,
            initial_balance:
              strategy.starting_balance || strategy.initial_amount || prev.initial_balance,
            benchmark_symbol: strategy.benchmark_symbol || prev.benchmark_symbol,
            trading_parameters: {
              ...prev.trading_parameters,
              resolution: strategy.candle_resolution || strategy.resolution,
              candle_resolution: strategy.candle_resolution || strategy.resolution,
              zscore_threshold: strategy.zscore_threshold,
              stats_window: strategy.stats_window,
              max_half_life: strategy.max_half_life,
              usd_per_trade: strategy.usd_per_trade,
              usd_min_collateral: strategy.usd_min_collateral,
              close_at_zscore_cross: strategy.close_at_zscore_cross,
              find_cointegrated_pairs: strategy.find_cointegrated_pairs,
              manage_exits: strategy.manage_exits,
              place_trades: strategy.place_trades,
              abort_all_positions: strategy.abort_all_positions,
              max_positions: strategy.max_positions,
              max_drawdown_pct: strategy.max_drawdown_pct,
              stop_loss_pct: strategy.stop_loss_pct,
              take_profit_pct: strategy.take_profit_pct,
              trailing_stop_pct: strategy.trailing_stop_pct,
              rebalance_interval_hours: strategy.rebalance_interval_hours,
              position_timeout_hours: strategy.position_timeout_hours,
              transaction_fee: strategy.transaction_fee,
              slippage: strategy.slippage,
              risk_free_rate: strategy.risk_free_rate,
              benchmark_symbol: strategy.benchmark_symbol,
              max_history_days: strategy.max_history_days,
              pair_selection_mode: strategy.pair_selection_mode,
            },
          }));
        }
      }
    },
    [strategies]
  );

  const handleStrategyChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const id = e.target.value ? parseInt(e.target.value, 10) : null;
    applyStrategyDefaults(id, useStrategy);
  };

  useEffect(() => {
    if (
      !requestedStrategyId ||
      strategies.length === 0 ||
      selectedStrategyId === requestedStrategyId
    ) {
      return;
    }
    setUseStrategy(true);
    applyStrategyDefaults(requestedStrategyId, true);
  }, [applyStrategyDefaults, requestedStrategyId, selectedStrategyId, strategies.length]);

  const toggleMarket = (market: string) => {
    setSelectedMarkets((prev) => {
      if (prev.includes(market)) {
        return prev.filter((item) => item !== market);
      }
      if (prev.length >= 20) {
        return prev;
      }
      return [...prev, market];
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    try {
      if (formData.start_date > formData.end_date) {
        const message = 'Choose a start date that comes before the end date.';
        setError(message);
        errorToast('Backtest dates need attention', message);
        return;
      }

      const tp = formData.trading_parameters;
      const explicitBenchmarkSymbol = String(
        tp.benchmark_symbol ?? formData.benchmark_symbol ?? ''
      ).trim();
      // benchmark_symbol is a performance-comparison reference, not a trading market.
      // Never derive it from selectedMarkets — only use explicit config or default to BTC-USD.
      const effectiveBenchmarkSymbol = explicitBenchmarkSymbol || 'BTC-USD';
      const activeMode = tp.pair_selection_mode || formData.pair_selection_mode || 'liquidity';

      if (activeMode === 'input' && selectedMarkets.length < 2) {
        const message =
          selectedMarkets.length === 0
            ? 'Pair selection mode is set to "input" — please select at least two markets to define the backtest universe.'
            : 'Pair selection mode is set to "input" — please select at least two markets (one pair minimum).';
        setError(message);
        errorToast('Markets required', message);
        return;
      }

      if (activeMode !== 'input' && selectedMarkets.length === 1) {
        const message =
          'Select at least two markets for a constrained backtest universe, or clear the selection to use all available markets.';
        setError(message);
        errorToast('Market selection needs attention', message);
        return;
      }

      setLoading(true);

      const [currentUserResponse, backtestListResponse] = await Promise.all([
        api.getCurrentUser(),
        api.listBacktests(0, 250),
      ]);
      const userQuota = extractUserBacktestQuota(currentUserResponse);
      if (userQuota !== null) {
        const activeBacktests = countActiveBacktests(backtestListResponse);
        if (activeBacktests >= userQuota) {
          const message = `You already have ${activeBacktests} active backtest${activeBacktests === 1 ? '' : 's'}. Your admin limit is ${userQuota}. Wait for an active run to complete before starting another one.`;
          setError(message);
          warningToast('Active backtest limit reached', message);
          return;
        }
      }

      // Ensure max_history_days covers the full requested period plus a warmup
      // buffer so the bot service doesn't silently cap the backtest window.
      const periodDays =
        Math.max(
          0,
          Math.round(
            (new Date(formData.end_date).getTime() - new Date(formData.start_date).getTime()) /
              (1000 * 60 * 60 * 24)
          )
        ) + 1;
      const effectiveMaxHistoryDays = Math.max(Number(tp.max_history_days ?? 90), periodDays + 30);
      if (selectedMarkets.length < 2) {
        throw new Error('Select at least two dYdX markets before starting a backtest.');
      }

      const cleanedData = {
        start_date: formData.start_date,
        end_date: formData.end_date,
        name: formData.name || 'ui-backtest',
        initial_balance: Number(formData.initial_balance),
        max_pairs: selectedMarkets.length > 0 ? selectedMarkets.length : Number(formData.max_pairs),
        benchmark_symbol: effectiveBenchmarkSymbol,
        pair_selection_mode: activeMode,
        ...(selectedMarkets.length > 0 && { pairs: selectedMarkets }),
        trading_parameters: {
          ...(tp.zscore_threshold !== undefined && {
            zscore_threshold: Number(tp.zscore_threshold),
          }),
          ...(tp.stats_window !== undefined && { stats_window: Number(tp.stats_window) }),
          ...(tp.max_half_life !== undefined && { max_half_life: Number(tp.max_half_life) }),
          ...(tp.usd_per_trade !== undefined && { usd_per_trade: Number(tp.usd_per_trade) }),
          ...(tp.usd_min_collateral !== undefined && {
            usd_min_collateral: Number(tp.usd_min_collateral),
          }),
          ...(tp.close_at_zscore_cross !== undefined && {
            close_at_zscore_cross: tp.close_at_zscore_cross,
          }),
          ...(tp.find_cointegrated_pairs !== undefined && {
            find_cointegrated_pairs: tp.find_cointegrated_pairs,
          }),
          ...(tp.manage_exits !== undefined && { manage_exits: tp.manage_exits }),
          ...(tp.place_trades !== undefined && { place_trades: tp.place_trades }),
          ...(tp.abort_all_positions !== undefined && {
            abort_all_positions: tp.abort_all_positions,
          }),
          ...(tp.max_positions !== undefined && { max_positions: Number(tp.max_positions) }),
          ...(tp.max_drawdown_pct !== undefined && {
            max_drawdown_pct: Number(tp.max_drawdown_pct),
          }),
          ...(tp.stop_loss_pct !== undefined && { stop_loss_pct: Number(tp.stop_loss_pct) }),
          ...(tp.take_profit_pct !== undefined && { take_profit_pct: Number(tp.take_profit_pct) }),
          ...(tp.trailing_stop_pct !== undefined && {
            trailing_stop_pct: Number(tp.trailing_stop_pct),
          }),
          ...(tp.rebalance_interval_hours !== undefined && {
            rebalance_interval_hours: Number(tp.rebalance_interval_hours),
          }),
          ...(tp.position_timeout_hours !== undefined && {
            position_timeout_hours: Number(tp.position_timeout_hours),
          }),
          ...(tp.transaction_fee !== undefined && {
            transaction_fee: Number(tp.transaction_fee),
          }),
          ...(tp.slippage !== undefined && { slippage: Number(tp.slippage) }),
          ...(tp.risk_free_rate !== undefined && {
            risk_free_rate: Number(tp.risk_free_rate),
          }),
          ...(tp.resolution !== undefined && { resolution: tp.resolution }),
          benchmark_symbol: effectiveBenchmarkSymbol,
          ...(tp.max_history_days !== undefined && {
            max_history_days: effectiveMaxHistoryDays,
          }),
          ...(tp.pair_selection_mode !== undefined && {
            pair_selection_mode: tp.pair_selection_mode,
          }),
        },
        ...(useStrategy && selectedStrategyId && { strategy_id: selectedStrategyId }),
      } satisfies BacktestRunRequest;
      const result = await runBacktestMutation.mutateAsync(cleanedData as ApiBacktestRequest);
      const runId = extractRunId(result);

      if (onBacktestComplete) {
        onBacktestComplete();
      }

      if (runId) {
        successToast(
          'Backtest launched',
          `${cleanedData.name || 'Research run'} is now entering the execution queue.`
        );
        navigate(`/backtest/${runId}`);
      } else {
        const message = 'The backtest started, but the backend did not return a run ID.';
        setError(message);
        errorToast('Launch response incomplete', message);
      }
    } catch (err: unknown) {
      console.error('❌ BacktestRunner: Error:', err);
      const fallbackMessage = getErrorMessage(err, 'Failed to start backtest');
      let message = fallbackMessage;

      if (err instanceof AxiosError) {
        const statusCode = err.response?.status;
        const payload = toRecord(err.response?.data);
        const reason =
          typeof payload.reason === 'string'
            ? payload.reason
            : typeof toRecord(payload.data).reason === 'string'
              ? String(toRecord(payload.data).reason)
              : '';

        if (statusCode === 429) {
          message =
            reason === 'backtest_user_capacity_reached'
              ? 'You reached your active backtest quota. Wait for a run to finish or ask an admin to raise your limit.'
              : reason === 'persistence_pool_overload'
                ? 'Backtest capacity is temporarily saturated by persistence load. Please retry shortly.'
                : fallbackMessage;
        }
      }

      setError(message);
      errorToast('Unable to start backtest', message);
    } finally {
      setLoading(false);
    }
  };

  const durationDays = useMemo(() => {
    const start = new Date(formData.start_date);
    const end = new Date(formData.end_date);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return 0;
    return Math.max(0, Math.round((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)) + 1);
  }, [formData.end_date, formData.start_date]);

  const selectedPairPreview = useMemo(() => {
    const pairs: string[] = [];
    for (let i = 0; i < selectedMarkets.length - 1; i += 1) {
      for (let j = i + 1; j < selectedMarkets.length; j += 1) {
        pairs.push(`${selectedMarkets[i]}/${selectedMarkets[j]}`);
      }
    }
    return pairs.slice(0, 5);
  }, [selectedMarkets]);

  const scanScopeLabel =
    selectedMarkets.length > 0
      ? `${selectedPairPreview.length} pair${selectedPairPreview.length === 1 ? '' : 's'} from ${selectedMarkets.length} markets`
      : Number(formData.max_pairs) > 0
        ? `${formData.max_pairs} markets`
        : 'All available markets';
  const selectedMode =
    (formData.trading_parameters
      .pair_selection_mode as BacktestRunRequest['pair_selection_mode']) || 'liquidity';
  const normalizedMarketsSource = marketsSource.trim().toLowerCase();
  const marketSourceBadge = useMemo(() => {
    if (marketsStale || normalizedMarketsSource === 'cache_stale') {
      return {
        label: 'Source: stale cache',
        className: 'border-amber-500/50 bg-amber-500/10 text-amber-200',
      };
    }
    if (normalizedMarketsSource === 'cache') {
      return {
        label: 'Source: cache',
        className: 'border-cyan-500/40 bg-cyan-500/10 text-cyan-200',
      };
    }
    if (normalizedMarketsSource === 'dydx') {
      return {
        label: 'Source: live dYdX',
        className: 'border-emerald-500/45 bg-emerald-500/10 text-emerald-200',
      };
    }
    return {
      label: 'Source: unknown',
      className: 'border-slate-600/70 bg-slate-700/40 text-slate-200',
    };
  }, [marketsSource, marketsStale, normalizedMarketsSource]);

  const marketSourceWarning = useMemo(() => {
    if (marketsStale || normalizedMarketsSource === 'cache_stale') {
      return 'Using stale cached market list while upstream refresh is unavailable.';
    }
    return null;
  }, [marketsStale, normalizedMarketsSource]);

  const pairSelectionNotes: Record<
    NonNullable<BacktestRunRequest['pair_selection_mode']>,
    string
  > = {
    liquidity: 'Favors deeper markets and steadier execution assumptions.',
    volatility: 'Pushes toward faster movers and wider spread behavior.',
    cointegration: 'Prioritizes statistically ranked pairs first.',
    input: 'Keeps your existing pair order without re-ranking.',
  };

  const applyPreset = (preset: (typeof presets)[number]) => {
    setFormData((prev) => ({
      ...prev,
      max_pairs: preset.values.max_pairs,
      trading_parameters: {
        ...prev.trading_parameters,
        zscore_threshold: preset.values.zscore_threshold,
        usd_per_trade: preset.values.usd_per_trade,
        stats_window: preset.values.stats_window,
      },
    }));
  };

  const inputClass =
    'premium-input bg-stone-950/80 px-3 py-2 text-sm text-white placeholder:text-slate-600';
  const labelClass = 'mb-2 block text-xs font-semibold uppercase text-slate-400';

  return (
    <div className="border-t border-slate-800/80 bg-stone-950/30 p-5">
      <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-[10px] font-semibold uppercase text-cyan-300">Backtest ticket</p>
          <h3 className="mt-1 text-xl font-bold text-white">Start new research run</h3>
        </div>
        <p className="max-w-xl text-sm leading-6 text-slate-400">
          Tune the run, keep risk assumptions explicit, and send the job through the backend control
          plane.
        </p>
      </div>

      {error && (
        <InlineNotice
          tone="danger"
          title="Backtest launch blocked"
          description={error}
          className="mb-4"
        />
      )}

      <div className="mb-4 grid gap-3 lg:grid-cols-4">
        <div className="metric-tile px-4 py-4">
          <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Window</p>
          <p className="mt-2 text-sm font-semibold text-white">{durationDays} days</p>
          <p className="mt-1 text-xs text-slate-500">
            {formData.start_date} to {formData.end_date}
          </p>
        </div>
        <div className="metric-tile px-4 py-4">
          <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Scan scope</p>
          <p className="mt-2 text-sm font-semibold text-white">{scanScopeLabel}</p>
          <p className="mt-1 text-xs text-slate-500">{pairSelectionNotes[selectedMode]}</p>
        </div>
        <div className="metric-tile px-4 py-4">
          <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Risk size</p>
          <p className="mt-2 text-sm font-semibold text-white">
            ${Number(formData.trading_parameters.usd_per_trade || 0).toFixed(2)}
          </p>
          <p className="mt-1 text-xs text-slate-500">Capital per trade attempt</p>
        </div>
        <div className="metric-tile px-4 py-4">
          <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Launch mode</p>
          <p className="mt-2 text-sm font-semibold text-white">
            {useStrategy && selectedStrategyId ? 'Strategy-linked' : 'Manual ticket'}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {useStrategy && selectedStrategyId
              ? `Saved strategy #${selectedStrategyId} loaded. This run will stay linked to that strategy.`
              : 'Operators set assumptions directly before queueing the run.'}
          </p>
        </div>
      </div>

      <div className="mb-4 rounded-lg border border-slate-800 bg-stone-950/55 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-300">
              Operator presets
            </p>
            <p className="mt-1 text-sm text-slate-400">
              Start from a proven posture, then fine-tune the research ticket.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {presets.map((preset) => (
              <button
                key={preset.id}
                type="button"
                onClick={() => applyPreset(preset)}
                className="rounded-lg border border-slate-700/70 bg-slate-900/70 px-3 py-2 text-left text-sm text-slate-200 transition hover:border-cyan-500/35 hover:text-white"
              >
                <span className="block font-medium">{preset.label}</span>
                <span className="mt-1 block text-xs text-slate-500">{preset.description}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="rounded-lg border border-slate-800 bg-stone-950/55 p-4">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={useStrategy}
              onChange={(e) => {
                setUseStrategy(e.target.checked);
                if (!e.target.checked) {
                  setSelectedStrategyId(null);
                  setFormData((prev) => {
                    const next = { ...prev };
                    delete next.strategy_id;
                    return next;
                  });
                }
              }}
              className="h-4 w-4 rounded border-slate-700 bg-stone-950 text-cyan-500"
            />
            <span className="text-sm font-medium text-gray-300">Use Saved Strategy</span>
          </label>

          {useStrategy && (
            <>
              <select
                value={selectedStrategyId || ''}
                onChange={handleStrategyChange}
                className={`${inputClass} mt-3`}
              >
                <option value="">Select a strategy...</option>
                {strategies.map((strategy) => (
                  <option key={strategy.id} value={strategy.id}>
                    {strategy.name} (Z-score: {strategy.zscore_threshold})
                  </option>
                ))}
              </select>

              {selectedStrategyId && (
                <p className="mt-2 text-xs text-cyan-300">
                  Strategy #{selectedStrategyId} parameters loaded below. The backtest payload will
                  include this relation so results can link back to the source strategy.
                </p>
              )}
            </>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Start Date</label>
            <input
              type="date"
              name="start_date"
              value={formData.start_date}
              onChange={handleChange}
              className={inputClass}
              required
            />
          </div>

          <div>
            <label className={labelClass}>End Date</label>
            <input
              type="date"
              name="end_date"
              value={formData.end_date}
              onChange={handleChange}
              className={inputClass}
              required
            />
          </div>

          <div>
            <label className={labelClass}>Number of Markets (0 = All)</label>
            <input
              type="number"
              name="max_pairs"
              value={formData.max_pairs}
              onChange={handleChange}
              min="0"
              max="50"
              className={inputClass}
            />
            <p className="mt-1 text-xs text-gray-400">
              Set to 0 to scan opportunities across all available markets.
            </p>
          </div>
          <div>
            <label className={labelClass}>Pair Selection Mode</label>
            <select
              name="pair_selection_mode"
              value={formData.trading_parameters.pair_selection_mode || 'liquidity'}
              onChange={(e) => {
                const value = e.target.value as
                  | 'liquidity'
                  | 'volatility'
                  | 'cointegration'
                  | 'input';
                setFormData((prev) => ({
                  ...prev,
                  pair_selection_mode: value,
                  trading_parameters: {
                    ...prev.trading_parameters,
                    pair_selection_mode: value,
                  },
                }));
              }}
              className={inputClass}
            >
              <option value="liquidity">Liquidity (highest volume first)</option>
              <option value="cointegration">Cointegration (strict statistical ranking)</option>
              <option value="volatility">Volatility (highest movement first)</option>
              <option value="input">Input order (no ranking)</option>
            </select>
          </div>
          <div className="md:col-span-2">
            <div className="mb-2 flex items-center justify-between gap-3">
              <label className="block text-xs font-semibold uppercase text-slate-400">
                dYdX Markets
              </label>
              <span
                className={`rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${marketSourceBadge.className}`}
                title="Market data source health"
              >
                {marketSourceBadge.label}
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setSelectedMarkets(availableMarkets.slice(0, 5))}
                  disabled={availableMarkets.length === 0}
                  className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-300 disabled:opacity-50"
                >
                  First 5
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedMarkets([])}
                  disabled={selectedMarkets.length === 0}
                  className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-300 disabled:opacity-50"
                >
                  Clear
                </button>
              </div>
            </div>
            <div className="rounded border border-slate-800 bg-stone-950/70 p-3">
              {marketsLoading ? (
                <p className="text-sm text-slate-400">Loading markets...</p>
              ) : marketsError ? (
                <p className="text-sm text-amber-300">{marketsError}</p>
              ) : (
                <div className="grid max-h-44 grid-cols-2 gap-2 overflow-y-auto pr-1 sm:grid-cols-3 lg:grid-cols-4">
                  {availableMarkets.map((market) => {
                    const checked = selectedMarkets.includes(market);
                    const disabled = !checked && selectedMarkets.length >= 5;
                    return (
                      <label
                        key={market}
                        className={`flex items-center gap-2 rounded border px-2 py-1.5 text-xs ${
                          checked
                            ? 'border-cyan-500 bg-cyan-500/10 text-cyan-100'
                            : 'border-slate-800 text-slate-300'
                        } ${disabled ? 'opacity-45' : ''}`}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={disabled}
                          onChange={() => toggleMarket(market)}
                          className="h-3.5 w-3.5 rounded border-slate-600 bg-slate-900 text-cyan-500"
                        />
                        <span className="truncate">{market}</span>
                      </label>
                    );
                  })}
                </div>
              )}
            </div>
            {marketSourceWarning && !marketsError && (
              <p className="mt-2 text-xs text-amber-200">{marketSourceWarning}</p>
            )}
            <p className="mt-1 text-xs text-gray-400">
              Optional. Select 2-5 markets; the run processes the first five generated pair
              combinations.
            </p>
            {selectedPairPreview.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {selectedPairPreview.map((pair) => (
                  <span
                    key={pair}
                    className="rounded border border-cyan-500/40 bg-cyan-500/10 px-2 py-1 text-xs text-cyan-100"
                  >
                    {pair}
                  </span>
                ))}
              </div>
            )}
          </div>
          <div>
            <label className={labelClass}>Z-Score Threshold</label>
            <input
              type="number"
              name="zscore_threshold"
              value={formData.trading_parameters.zscore_threshold}
              onChange={handleChange}
              step="0.1"
              min="0.5"
              max="3"
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Stats Window (days)</label>
            <input
              type="number"
              name="stats_window"
              value={formData.trading_parameters.stats_window}
              onChange={handleChange}
              min="5"
              max="60"
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>USD Per Trade</label>
            <input
              type="number"
              name="usd_per_trade"
              value={formData.trading_parameters.usd_per_trade}
              onChange={handleChange}
              step="1"
              min="1"
              max="1000"
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Starting Balance</label>
            <input
              type="number"
              name="initial_balance"
              value={formData.initial_balance ?? 1000}
              onChange={handleChange}
              step="100"
              min="100"
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Candle Resolution</label>
            <select
              name="resolution"
              value={normalizeDydxCandleResolution(
                formData.trading_parameters.resolution || '1HOUR'
              )}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  trading_parameters: {
                    ...prev.trading_parameters,
                    resolution: normalizeDydxCandleResolution(e.target.value),
                  },
                }))
              }
              className={inputClass}
            >
              {DYDX_CANDLE_RESOLUTION_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelClass}>Transaction Fee</label>
            <input
              type="number"
              name="transaction_fee"
              value={formData.trading_parameters.transaction_fee ?? 0.0005}
              onChange={handleChange}
              step="0.0001"
              min="0"
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Slippage</label>
            <input
              type="number"
              name="slippage"
              value={formData.trading_parameters.slippage ?? 0.001}
              onChange={handleChange}
              step="0.0001"
              min="0"
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Benchmark Symbol</label>
            <input
              type="text"
              name="benchmark_symbol"
              value={
                formData.benchmark_symbol ||
                formData.trading_parameters.benchmark_symbol ||
                'BTC-USD'
              }
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  benchmark_symbol: e.target.value,
                  trading_parameters: {
                    ...prev.trading_parameters,
                    benchmark_symbol: e.target.value,
                  },
                }))
              }
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Risk-Free Rate</label>
            <input
              type="number"
              name="risk_free_rate"
              value={formData.trading_parameters.risk_free_rate ?? 0.02}
              onChange={handleChange}
              step="0.001"
              min="0"
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Max History Days</label>
            <input
              type="number"
              name="max_history_days"
              value={formData.trading_parameters.max_history_days ?? 90}
              onChange={handleChange}
              min="1"
              max="3650"
              className={inputClass}
            />
          </div>
        </div>

        <InlineNotice
          tone="warning"
          title="Before you launch"
          description="Check the time window, market scope, transaction fee, and slippage assumptions so the run answers the right research question."
        />

        <button
          type="submit"
          disabled={loading || runBacktestMutation.isPending}
          className="premium-button premium-button-primary mt-6 flex w-full items-center justify-center gap-2 py-3 text-white disabled:opacity-50"
        >
          <Play className="w-4 h-4" />
          {loading || runBacktestMutation.isPending ? 'Running Backtest...' : 'Start Backtest'}
        </button>
      </form>
    </div>
  );
};
