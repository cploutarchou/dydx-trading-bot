import { useQueryClient } from '@tanstack/react-query';
import { CheckSquare, ListChecks, RefreshCw, Sparkles, Star, Trophy, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import api, {
    DYDX_CANDLE_RESOLUTION_OPTIONS,
    normalizeDydxCandleResolution,
    toAIBacktestSummary,
    type AIBacktestSummary,
    type AIMarketProvider,
} from '../api';
import { getAIProviderLabel, useAIProviderAvailability } from '../features/ai/providerAvailability';
import type { Strategy } from '../store/strategies';
import { AIStrategyAdvisor } from './AIStrategyAdvisor';
import { PageContainer } from './PageContainer';

interface StrategyFormData {
  name: string;
  category: string;
  description: string;
  is_public: boolean;
  runtime_network: 'testnet' | 'mainnet';
  runtime_subaccount: number;
  selected_markets: string[];
  pair_selection_mode: 'liquidity' | 'volatility' | 'cointegration' | 'input';
  resolution: string;
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
  initial_amount: number;
  max_history_days: number;
  transaction_fee?: number;
  slippage?: number;
}

// Preset configurations
const PRESETS = {
  conservative: {
    zscore_threshold: 2.0,
    stats_window: 30,
    max_half_life: 20,
    description: 'Conservative strategy with higher Z-score threshold and longer stats window',
  },
  balanced: {
    zscore_threshold: 1.5,
    stats_window: 21,
    max_half_life: 12,
    description: 'Balanced strategy for moderate risk/reward',
  },
  aggressive: {
    zscore_threshold: 1.0,
    stats_window: 14,
    max_half_life: 8,
    description: 'Aggressive strategy with lower thresholds for frequent trading',
  },
};

const MAX_SELECTED_MARKETS = 150;
const DEFAULT_AUTO_SELECTED_MARKETS = 35;
const MAX_BACKTEST_RUNS_FOR_FILTERS = 120;
const TRADE_FETCH_BATCH_SIZE = 6;
const MARKET_STATS_CACHE_TTL_MS = 90_000;
const AUTO_MARKET_LIMIT_PREFERENCE_KEY = 'strategy-builder-auto-market-limit';

type MarketSelectionView = 'all' | 'selected' | 'unselected';

type MarketAggregateStats = {
  tradeCount: number;
  totalPnl: number;
  winCount: number;
};

type HistoricalMarketStatsSnapshot = {
  capturedAt: number;
  marketUniverseSize: number;
  runsAnalyzed: number;
  marketStats: Record<string, MarketAggregateStats>;
};
type AIMarketObjective =
  | 'balanced'
  | 'volume'
  | 'tradeable'
  | 'future_gainers'
  | 'volatility'
  | 'cointegration';

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (error instanceof Error) return error.message;
  if (typeof error === 'object' && error !== null) {
    const err = error as {
      response?: { data?: { message?: string } };
      message?: string;
    };
    return err.response?.data?.message || err.message || fallback;
  }
  return fallback;
};

const toRecord = (value: unknown): Record<string, unknown> =>
  typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : {};

const asString = (value: unknown): string | null => {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
};

const asNumber = (value: unknown): number => {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
};

const loadPreferredAutoMarketLimit = (): number => {
  if (typeof window === 'undefined') {
    return DEFAULT_AUTO_SELECTED_MARKETS;
  }

  const stored = Number(window.localStorage.getItem(AUTO_MARKET_LIMIT_PREFERENCE_KEY));
  if (!Number.isFinite(stored)) {
    return DEFAULT_AUTO_SELECTED_MARKETS;
  }

  return Math.min(MAX_SELECTED_MARKETS, Math.max(2, Math.round(stored)));
};

export default function StrategyBuilder() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const { id: strategyId } = useParams<{ id?: string }>();
  const isEditMode = !!strategyId;

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [loadingExisting, setLoadingExisting] = useState(isEditMode);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [availableMarkets, setAvailableMarkets] = useState<string[]>([]);
  const [marketsLoading, setMarketsLoading] = useState(false);
  const [marketsError, setMarketsError] = useState<string | null>(null);
  const [marketFilterLoading, setMarketFilterLoading] = useState<
    null | 'top20' | 'popular' | 'profitable' | 'ai'
  >(null);
  const [marketFilterError, setMarketFilterError] = useState<string | null>(null);
  const [aiMarketProvider, setAIMarketProvider] = useState<AIMarketProvider>('deepseek');
  const [aiMarketObjective, setAIMarketObjective] = useState<AIMarketObjective>('balanced');
  const [autoMarketLimit, setAutoMarketLimit] = useState(loadPreferredAutoMarketLimit);
  const [showPairPreview, setShowPairPreview] = useState(false);
  const [recentBacktests, setRecentBacktests] = useState<AIBacktestSummary[]>([]);
  const [marketSearchQuery, setMarketSearchQuery] = useState('');
  const [marketSelectionView, setMarketSelectionView] = useState<MarketSelectionView>('all');
  const [historicalMarketStats, setHistoricalMarketStats] =
    useState<HistoricalMarketStatsSnapshot | null>(null);
  const [marketStatsClockMs, setMarketStatsClockMs] = useState(() => Date.now());
  const [rankingRefreshing, setRankingRefreshing] = useState(false);
  const { availableProviders: availableAIProviders, isLoading: aiProviderStatusLoading } =
    useAIProviderAvailability();

  useEffect(() => {
    if (availableAIProviders.length === 0) {
      return;
    }

    if (!availableAIProviders.includes(aiMarketProvider)) {
      setAIMarketProvider((availableAIProviders[0] ?? availableAIProviders[0]!));
    }
  }, [aiMarketProvider, availableAIProviders]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    window.localStorage.setItem(AUTO_MARKET_LIMIT_PREFERENCE_KEY, String(autoMarketLimit));
  }, [autoMarketLimit]);

  useEffect(() => {
    if (!historicalMarketStats || typeof window === 'undefined') {
      return;
    }

    setMarketStatsClockMs(Date.now());
    const intervalId = window.setInterval(() => {
      setMarketStatsClockMs(Date.now());
    }, 1000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [historicalMarketStats]);

  // Get pre-loaded config from backtest or sessionStorage
  const getPreloadedConfig = () => {
    try {
      // Check location state first (passed from navigate)
      if (location.state?.configSnapshot) {
        return location.state.configSnapshot;
      }
      // Check sessionStorage
      const stored = sessionStorage.getItem('strategyConfig');
      if (stored) {
        const config = JSON.parse(stored);
        sessionStorage.removeItem('strategyConfig'); // Clean up after use
        return config;
      }
    } catch (err) {
      console.error('Failed to load preloaded config:', err);
    }
    return null;
  };

  const {
    control,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors },
  } = useForm<StrategyFormData>({
    defaultValues: {
      name: '',
      category: 'pairs_trading',
      description: '',
      is_public: false,
      runtime_network: 'testnet',
      runtime_subaccount: 0,
      selected_markets: [],
      pair_selection_mode: 'cointegration',
      resolution: '1HOUR',
      zscore_threshold: 1.5,
      stats_window: 21,
      max_half_life: 24,
      usd_per_trade: 10.0,
      usd_min_collateral: 100.0,
      close_at_zscore_cross: true,
      find_cointegrated_pairs: true,
      manage_exits: true,
      place_trades: true,
      abort_all_positions: false,
      max_positions: 5,
      max_drawdown_pct: 15.0,
      stop_loss_pct: 2.0,
      take_profit_pct: 5.0,
      trailing_stop_pct: 1.0,
      rebalance_interval_hours: 24,
      position_timeout_hours: 72,
      initial_amount: 300.0,
      max_history_days: 90,
      transaction_fee: 0.0005,
      slippage: 0.001,
    },
  });

  // react-hook-form's watch() is not React-Compiler-optimizable; that is
  // expected for this form library and only skips compilation for this file.
  // eslint-disable-next-line react-hooks/incompatible-library
  const formValues = watch();
  const fieldLabelClass = 'mb-2 block text-sm font-semibold text-slate-200';
  const helperTextClass = 'mt-2 text-xs leading-5 text-slate-500';
  const inlineValueClass = 'font-semibold text-cyan-300';
  const compactInputClass = 'premium-input px-4 py-2.5 text-sm';
  const sectionTitleClass = 'mb-4 text-lg font-semibold text-white';
  const dividerClass = 'my-2 border-t border-slate-800/80';
  const marketToolbarButtonClass =
    'inline-flex h-10 items-center gap-2 rounded-lg border border-slate-700/80 bg-slate-950/70 px-3 text-xs font-semibold text-slate-300 transition hover:border-cyan-500/50 hover:text-cyan-100 disabled:cursor-not-allowed disabled:opacity-50';
  const marketToolbarSelectClass =
    'h-10 rounded-lg border border-slate-700/80 bg-slate-950/70 px-3 text-xs font-semibold text-slate-300 outline-none transition hover:border-cyan-500/50 focus:border-cyan-500';

  // Load existing strategy if in edit mode
  useEffect(() => {
    if (isEditMode && strategyId) {
      loadStrategy(parseInt(strategyId, 10));
    }
  }, [isEditMode, strategyId]);

  useEffect(() => {
    let cancelled = false;

    const loadRecentBacktests = async () => {
      if (!isEditMode || !strategyId) {
        if (!cancelled) {
          setRecentBacktests([]);
        }
        return;
      }

      const parsedId = Number.parseInt(strategyId, 10);
      if (!Number.isFinite(parsedId) || parsedId <= 0) {
        if (!cancelled) {
          setRecentBacktests([]);
        }
        return;
      }

      try {
        const response = await api.listBacktestsByStrategy(parsedId, 5);
        const items = Array.isArray(response.data?.backtests) ? response.data.backtests : [];
        const summaries: AIBacktestSummary[] = items
          .map((b) => toAIBacktestSummary(b))
          .filter((summary): summary is AIBacktestSummary => summary !== null);

        if (!cancelled) {
          setRecentBacktests(summaries);
        }
      } catch {
        if (!cancelled) {
          setRecentBacktests([]);
        }
      }
    };

    void loadRecentBacktests();
    return () => {
      cancelled = true;
    };
  }, [isEditMode, strategyId]);

  useEffect(() => {
    let cancelled = false;

    const loadMarkets = async () => {
      setMarketsLoading(true);
      setMarketsError(null);
      try {
        const response = await api.getPerpetualMarkets(160);
        const markets = Array.isArray(response.data?.markets) ? response.data.markets : [];
        if (!cancelled) {
          setAvailableMarkets(markets);
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

  // Load preloaded config from backtest
  useEffect(() => {
    const preloadedConfig = getPreloadedConfig();
    if (preloadedConfig && !isEditMode) {
      reset({
        ...formValues,
        ...preloadedConfig,
        // Keep form metadata, but override with preloaded parameters
        name: preloadedConfig.name || formValues.name,
        category: preloadedConfig.category || 'pairs_trading',
        description: preloadedConfig.description || 'Created from backtest configuration',
      });
      setSuccessMessage('✅ Strategy parameters loaded from backtest!');
      setTimeout(() => setSuccessMessage(null), 3000);
    }
  }, [location]);

  const loadStrategy = async (id: number) => {
    try {
      setLoadingExisting(true);
      const response = await api.getStrategy(id);
      if (response.data) {
        const { candle_resolution: _candleResolution, ...strategyData } = response.data;
        const resolution = normalizeDydxCandleResolution(
          response.data.resolution || response.data.candle_resolution || '1HOUR'
        );

        reset({
          ...strategyData,
          resolution,
          max_history_days: Number(response.data.max_history_days ?? 90),
          selected_markets: Array.isArray(response.data.selected_markets)
            ? response.data.selected_markets
            : [],
        });
      }
    } catch (err: unknown) {
      setError(`Failed to load strategy: ${getErrorMessage(err, 'Unknown error')}`);
      console.error('Failed to load strategy:', err);
    } finally {
      setLoadingExisting(false);
    }
  };

  const applyPreset = (presetName: keyof typeof PRESETS) => {
    const preset = PRESETS[presetName];
    reset({
      ...formValues,
      zscore_threshold: preset.zscore_threshold,
      stats_window: preset.stats_window,
      max_half_life: preset.max_half_life,
      description: preset.description,
    });
    setSuccessMessage(
      `${presetName.charAt(0).toUpperCase() + presetName.slice(1)} preset applied!`
    );
    setTimeout(() => setSuccessMessage(null), 3000);
  };

  const onSubmit = async (data: StrategyFormData) => {
    try {
      setLoading(true);
      setError(null);
      setSuccessMessage(null);

      // Convert string values to numbers for all numeric fields
      const initialAmount = Number(data.initial_amount);
      const selectedMarkets = Array.isArray(data.selected_markets) ? data.selected_markets : [];
      if (selectedMarkets.length === 1) {
        setError('Select at least two markets, or leave market selection empty.');
        return;
      }
      if (selectedMarkets.length > MAX_SELECTED_MARKETS) {
        setError(`Select no more than ${MAX_SELECTED_MARKETS} markets for this strategy.`);
        return;
      }
      const cleanedData = {
        ...data,
        runtime_network: data.runtime_network,
        runtime_subaccount: Number(data.runtime_subaccount),
        selected_markets: selectedMarkets,
        resolution: normalizeDydxCandleResolution(data.resolution),
        candle_resolution: normalizeDydxCandleResolution(data.resolution),
        zscore_threshold: Number(data.zscore_threshold),
        stats_window: Number(data.stats_window),
        max_half_life: Number(data.max_half_life),
        usd_per_trade: Number(data.usd_per_trade),
        // Auto-set min collateral to match initial_amount (consolidated from UI)
        usd_min_collateral: initialAmount,
        max_positions: Number(data.max_positions),
        max_drawdown_pct: Number(data.max_drawdown_pct),
        stop_loss_pct: Number(data.stop_loss_pct),
        take_profit_pct: Number(data.take_profit_pct),
        trailing_stop_pct: Number(data.trailing_stop_pct),
        rebalance_interval_hours: Number(data.rebalance_interval_hours),
        position_timeout_hours: Number(data.position_timeout_hours),
        max_history_days: Number(data.max_history_days ?? 90),
        starting_balance: initialAmount,
        initial_amount: initialAmount,
        transaction_fee: data.transaction_fee ? Number(data.transaction_fee) : 0.0005,
        slippage: data.slippage ? Number(data.slippage) : 0.001,
      };

      if (isEditMode && strategyId) {
        // Update existing strategy
        const response = await api.updateStrategy(parseInt(strategyId, 10), cleanedData);
        if (response.success) {
          const updatedStrategyId = Number.parseInt(strategyId, 10);
          await queryClient.invalidateQueries({ queryKey: ['strategies'] });
          setSuccessMessage(`Strategy "${cleanedData.name}" updated successfully!`);
          setTimeout(() => {
            navigate('/strategies', {
              state: {
                strategyToast: `Strategy "${cleanedData.name}" updated successfully.`,
                strategyId: Number.isFinite(updatedStrategyId) ? updatedStrategyId : undefined,
              },
            });
          }, 1500);
        } else {
          setError(response.message || 'Failed to update strategy');
        }
      } else {
        // Create new strategy
        const response = await api.createStrategy(cleanedData);
        if (response.success) {
          const createdStrategyId =
            typeof response.data?.id === 'number' ? response.data.id : undefined;
          await queryClient.invalidateQueries({ queryKey: ['strategies'] });
          setSuccessMessage(`Strategy "${cleanedData.name}" created successfully!`);
          reset();
          setTimeout(() => {
            navigate('/strategies', {
              state: {
                strategyToast: `Strategy "${cleanedData.name}" created successfully.`,
                strategyId: createdStrategyId,
              },
            });
          }, 1500);
        } else {
          setError(response.message || 'Failed to create strategy');
        }
      }
    } catch (err: unknown) {
      console.error('Submit error:', err);
      setError(getErrorMessage(err, 'An error occurred'));
    } finally {
      setLoading(false);
    }
  };

  const selectedMarkets = Array.isArray(formValues.selected_markets)
    ? formValues.selected_markets
    : [];

  const strategyForAdvisor = useMemo<Strategy>(() => {
    const normalizedResolution = normalizeDydxCandleResolution(formValues.resolution || '1HOUR');
    return {
      id: strategyId ? Number.parseInt(strategyId, 10) : -1,
      name: formValues.name || (isEditMode ? 'Editing Strategy' : 'Draft Strategy'),
      category: formValues.category,
      description: formValues.description,
      is_public: formValues.is_public,
      runtime_network: formValues.runtime_network,
      runtime_subaccount: Number(formValues.runtime_subaccount ?? 0),
      selected_markets: selectedMarkets,
      resolution: normalizedResolution,
      candle_resolution: normalizedResolution,
      zscore_threshold: Number(formValues.zscore_threshold),
      stats_window: Number(formValues.stats_window),
      max_half_life: Number(formValues.max_half_life),
      usd_per_trade: Number(formValues.usd_per_trade),
      usd_min_collateral: Number(formValues.usd_min_collateral),
      close_at_zscore_cross: Boolean(formValues.close_at_zscore_cross),
      find_cointegrated_pairs: Boolean(formValues.find_cointegrated_pairs),
      manage_exits: Boolean(formValues.manage_exits),
      place_trades: Boolean(formValues.place_trades),
      abort_all_positions: Boolean(formValues.abort_all_positions),
      max_positions: Number(formValues.max_positions),
      max_drawdown_pct: Number(formValues.max_drawdown_pct),
      stop_loss_pct: Number(formValues.stop_loss_pct),
      take_profit_pct: Number(formValues.take_profit_pct),
      trailing_stop_pct: Number(formValues.trailing_stop_pct),
      rebalance_interval_hours: Number(formValues.rebalance_interval_hours),
      position_timeout_hours: Number(formValues.position_timeout_hours),
      initial_amount: Number(formValues.initial_amount),
      max_history_days: Number(formValues.max_history_days ?? 90),
      transaction_fee: Number(formValues.transaction_fee ?? 0.0005),
      slippage: Number(formValues.slippage ?? 0.001),
    };
  }, [formValues, isEditMode, selectedMarkets, strategyId]);

  const handleApplyAdvisorParams = async (
    params: Partial<Strategy>
  ): Promise<Array<keyof Strategy>> => {
    const appliedKeys: Array<keyof Strategy> = [];

    const setFormField = <K extends keyof StrategyFormData>(
      fieldName: K,
      value: StrategyFormData[K]
    ) => {
      (setValue as (name: K, value: StrategyFormData[K], options: Parameters<typeof setValue>[2]) => void)(fieldName, value, {
        shouldDirty: true,
        shouldTouch: true,
        shouldValidate: true,
      });
    };

    Object.entries(params).forEach(([rawKey, rawValue]) => {
      const key = rawKey as keyof Strategy;

      if (key === 'resolution' || key === 'candle_resolution') {
        setFormField('resolution', normalizeDydxCandleResolution(String(rawValue)));
        appliedKeys.push(key);
        return;
      }

      if (!(key in formValues)) {
        return;
      }

      switch (typeof rawValue) {
        case 'number':
          (setFormField as unknown as (name: string, value: unknown) => void)(
            key,
            Number(rawValue)
          );
          appliedKeys.push(key);
          break;
        case 'boolean':
          (setFormField as unknown as (name: string, value: unknown) => void)(key, rawValue);
          appliedKeys.push(key);
          break;
        case 'string':
          (setFormField as unknown as (name: string, value: unknown) => void)(key, rawValue);
          appliedKeys.push(key);
          break;
        default:
          break;
      }
    });

    const dedupedAppliedKeys = Array.from(new Set(appliedKeys));
    const appliedCount = dedupedAppliedKeys.length;
    if (appliedCount === 0) {
      const message = 'No editable AI suggestions were detected for this form.';
      setError(message);
      throw new Error(message);
    }

    setSuccessMessage(`✅ Applied ${appliedCount} AI suggestion${appliedCount === 1 ? '' : 's'}`);
    setTimeout(() => setSuccessMessage(null), 3000);
    return dedupedAppliedKeys;
  };

  const buildAIMarketCriteria = (preset: 'popular' | 'profitable' | 'ai') => {
    const pairSelectionMode = String(formValues.pair_selection_mode || 'cointegration');
    const objective =
      preset === 'popular'
        ? 'volume'
        : preset === 'profitable'
          ? 'future_gainers'
          : aiMarketObjective === 'balanced'
            ? pairSelectionMode
            : aiMarketObjective;
    const riskWeight = Math.min(
      1,
      Math.max(0.35, Number(formValues.max_drawdown_pct || 20) <= 15 ? 0.8 : 0.55)
    );
    const tradeSize = Number(formValues.usd_per_trade || 0);
    const needsTradeability = tradeSize >= 250 || Number(formValues.max_positions || 0) >= 4;

    return {
      objective,
      volume_weight: preset === 'popular' || objective === 'volume' ? 0.95 : 0.68,
      liquidity_weight: needsTradeability || objective === 'tradeable' ? 0.92 : 0.75,
      tradeability_weight: needsTradeability || objective === 'tradeable' ? 0.95 : 0.72,
      momentum_weight:
        objective === 'future_gainers' ? 0.88 : preset === 'profitable' ? 0.72 : 0.35,
      volatility_weight:
        objective === 'volatility' || pairSelectionMode === 'volatility' ? 0.86 : 0.45,
      cointegration_weight:
        objective === 'cointegration' || pairSelectionMode === 'cointegration' ? 0.9 : 0.58,
      risk_weight: riskWeight,
      future_gainers: objective === 'future_gainers',
      notes: [
        `category=${formValues.category || 'pairs_trading'}`,
        `resolution=${normalizeDydxCandleResolution(formValues.resolution || '1HOUR')}`,
        `zscore=${formValues.zscore_threshold || 1.5}`,
        `stats_window=${formValues.stats_window || 21}`,
        `max_half_life=${formValues.max_half_life || 12}`,
        `usd_per_trade=${formValues.usd_per_trade || 0}`,
        `max_positions=${formValues.max_positions || 0}`,
      ].join('; '),
    };
  };
  const selectedPairPreview = useMemo(() => {
    const pairs: string[] = [];
    for (let i = 0; i < selectedMarkets.length - 1; i += 1) {
      for (let j = i + 1; j < selectedMarkets.length; j += 1) {
        pairs.push(`${selectedMarkets[i]}/${selectedMarkets[j]}`);
      }
    }
    return pairs.slice(0, 8);
  }, [selectedMarkets]);
  const candidatePairCount = (selectedMarkets.length * (selectedMarkets.length - 1)) / 2;

  const marketRankingFreshnessLabel = useMemo(() => {
    if (!historicalMarketStats) {
      return null;
    }

    const ageMs = Math.max(0, marketStatsClockMs - historicalMarketStats.capturedAt);
    const totalSeconds = Math.floor(ageMs / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    const ageLabel =
      minutes > 0 ? `${minutes}m${seconds > 0 ? ` ${seconds}s` : ''} ago` : `${totalSeconds}s ago`;

    const isFresh = ageMs <= MARKET_STATS_CACHE_TTL_MS;
    return {
      text: isFresh ? `Rankings: ${ageLabel}` : `Rankings stale (${ageLabel}) — click to refresh`,
      isFresh,
    };
  }, [historicalMarketStats, marketStatsClockMs]);

  const forceRefreshRankings = async () => {
    if (rankingRefreshing || availableMarkets.length === 0) {
      return;
    }

    try {
      setRankingRefreshing(true);
      setHistoricalMarketStats(null);
      setMarketFilterError(null);

      const availableSet = new Set(availableMarkets);
      const runIds: string[] = [];
      let skip = 0;
      const pageLimit = 100;
      let total = Number.POSITIVE_INFINITY;

      while (skip < total && runIds.length < MAX_BACKTEST_RUNS_FOR_FILTERS) {
        const response = await api.listBacktests(skip, pageLimit);
        const root = toRecord(response);
        const data = toRecord(root.data);
        const rows = Array.isArray(data.backtests) ? data.backtests : [];

        if (typeof data.total === 'number' && Number.isFinite(data.total)) {
          total = data.total;
        }
        if (rows.length === 0) break;

        rows.forEach((row) => {
          const run = toRecord(row);
          const runId = asString(run.run_id);
          if (runId) runIds.push(runId);
        });

        skip += rows.length;
        if (rows.length < pageLimit) break;
      }

      const dedupedRunIds = Array.from(new Set(runIds)).slice(0, MAX_BACKTEST_RUNS_FOR_FILTERS);
      if (dedupedRunIds.length === 0) {
        setMarketFilterError('No historical backtests found. Ranking data could not be refreshed.');
        return;
      }

      const marketStatsMap = new Map<string, MarketAggregateStats>();
      for (let index = 0; index < dedupedRunIds.length; index += TRADE_FETCH_BATCH_SIZE) {
        const batch = dedupedRunIds.slice(index, index + TRADE_FETCH_BATCH_SIZE);
        const responses = await Promise.all(
          batch.map(async (runId) => {
            try {
              return await api.getBacktestTradesDetailed(runId, undefined, undefined, 0, 1000);
            } catch {
              return null;
            }
          })
        );

        responses.forEach((response) => {
          if (!response) return;
          const root = toRecord(response);
          const data = toRecord(root.data);
          const trades = Array.isArray(data.trades) ? data.trades : [];

          trades.forEach((trade) => {
            const row = toRecord(trade);
            const market1 = asString(row.market_1);
            const market2 = asString(row.market_2);
            const pnlRaw = asNumber(row.pnl_usd ?? row.pnl ?? row.total_pnl ?? 0);
            const perMarketPnl = pnlRaw / 2;
            const isWin = pnlRaw > 0;

            [market1, market2].forEach((market) => {
              if (!market || !availableSet.has(market)) return;
              const current = marketStatsMap.get(market) ?? {
                tradeCount: 0,
                totalPnl: 0,
                winCount: 0,
              };
              current.tradeCount += 1;
              current.totalPnl += perMarketPnl;
              if (isWin) current.winCount += 1;
              marketStatsMap.set(market, current);
            });
          });
        });
      }

      const nextSnapshot: HistoricalMarketStatsSnapshot = {
        capturedAt: Date.now(),
        marketUniverseSize: availableMarkets.length,
        runsAnalyzed: dedupedRunIds.length,
        marketStats: Object.fromEntries(marketStatsMap.entries()),
      };
      setHistoricalMarketStats(nextSnapshot);
      setMarketFilterError(`Rankings refreshed from ${dedupedRunIds.length} backtests.`);
    } catch (err: unknown) {
      setMarketFilterError(getErrorMessage(err, 'Failed to refresh ranking data'));
    } finally {
      setRankingRefreshing(false);
    }
  };

  const applyMarketPreset = async (
    preset: 'top20' | 'popular' | 'profitable' | 'ai',
    onChange: (_value: string[]) => void,
    currentSelection: string[]
  ) => {
    const normalizedCurrentSelection = Array.isArray(currentSelection) ? currentSelection : [];
    const selectionLimit = Math.min(
      MAX_SELECTED_MARKETS,
      Math.max(2, Math.round(Number(autoMarketLimit) || DEFAULT_AUTO_SELECTED_MARKETS))
    );

    const normalizeTopMarkets = (markets: string[]): string[] => {
      const unique = Array.from(
        new Set(
          markets
            .map((market) => market.trim())
            .filter((market) => market.length > 0)
            .filter((market) => availableMarkets.includes(market))
        )
      );
      return unique.slice(0, selectionLimit);
    };

    setMarketFilterError(null);

    if (preset === 'top20') {
      onChange(normalizeTopMarkets(availableMarkets));
      return;
    }

    if (availableAIProviders.length === 0) {
      if (preset === 'ai') {
        setMarketFilterError(
          'AI providers are unavailable for your account. Falling back to top markets.'
        );
        onChange(normalizeTopMarkets(availableMarkets));
        return;
      }
    }

    try {
      setMarketFilterLoading(preset);
      const aiMode =
        preset === 'popular'
          ? 'most_popular'
          : preset === 'profitable'
            ? 'most_profitable'
            : 'ai_recommended';
      const aiResponse =
        availableAIProviders.length > 0
          ? await api.selectAIMarkets({
              provider: aiMarketProvider,
              mode: aiMode,
              markets: availableMarkets,
              limit: selectionLimit,
              strategy: `${formValues.category || 'pairs_trading'} strategy using ${normalizeDydxCandleResolution(formValues.resolution || '1HOUR')} candles`,
              criteria: buildAIMarketCriteria(preset),
            })
          : null;
      const aiMarkets = normalizeTopMarkets(aiResponse?.data?.selected_markets || []);
      if (aiMarkets.length >= 2) {
        onChange(aiMarkets);
        setMarketFilterError(
          aiResponse?.data?.used_ai
            ? aiResponse.data.rationale || null
            : aiResponse?.data?.fallback_reason || null
        );
        return;
      }

      if (preset === 'ai') {
        setMarketFilterError('AI returned too few valid dYdX markets. Using current top markets.');
        onChange(normalizeTopMarkets(availableMarkets));
        return;
      }

      const availableSet = new Set(availableMarkets);
      let statsSnapshot = historicalMarketStats;
      const isCachedSnapshotUsable =
        !!statsSnapshot &&
        Date.now() - statsSnapshot.capturedAt <= MARKET_STATS_CACHE_TTL_MS &&
        statsSnapshot.marketUniverseSize === availableMarkets.length;

      if (!isCachedSnapshotUsable) {
        const runIds: string[] = [];
        let skip = 0;
        const pageLimit = 100;
        let total = Number.POSITIVE_INFINITY;

        while (skip < total && runIds.length < MAX_BACKTEST_RUNS_FOR_FILTERS) {
          const response = await api.listBacktests(skip, pageLimit);
          const root = toRecord(response);
          const data = toRecord(root.data);
          const rows = Array.isArray(data.backtests) ? data.backtests : [];

          if (typeof data.total === 'number' && Number.isFinite(data.total)) {
            total = data.total;
          }

          if (rows.length === 0) {
            break;
          }

          rows.forEach((row) => {
            const run = toRecord(row);
            const runId = asString(run.run_id);
            if (runId) {
              runIds.push(runId);
            }
          });

          skip += rows.length;
          if (rows.length < pageLimit) {
            break;
          }
        }

        const dedupedRunIds = Array.from(new Set(runIds)).slice(0, MAX_BACKTEST_RUNS_FOR_FILTERS);

        if (dedupedRunIds.length === 0) {
          setMarketFilterError('No historical backtests found yet. Using current top markets.');
          onChange(normalizeTopMarkets(availableMarkets));
          return;
        }

        const marketStatsMap = new Map<string, MarketAggregateStats>();
        for (let index = 0; index < dedupedRunIds.length; index += TRADE_FETCH_BATCH_SIZE) {
          const batch = dedupedRunIds.slice(index, index + TRADE_FETCH_BATCH_SIZE);
          const responses = await Promise.all(
            batch.map(async (runId) => {
              try {
                return await api.getBacktestTradesDetailed(runId, undefined, undefined, 0, 1000);
              } catch {
                return null;
              }
            })
          );

          responses.forEach((response) => {
            if (!response) return;
            const root = toRecord(response);
            const data = toRecord(root.data);
            const trades = Array.isArray(data.trades) ? data.trades : [];

            trades.forEach((trade) => {
              const row = toRecord(trade);
              const market1 = asString(row.market_1);
              const market2 = asString(row.market_2);
              const pnlRaw = asNumber(row.pnl_usd ?? row.pnl ?? row.total_pnl ?? 0);
              const perMarketPnl = pnlRaw / 2;
              const isWin = pnlRaw > 0;

              [market1, market2].forEach((market) => {
                if (!market || !availableSet.has(market)) {
                  return;
                }
                const current = marketStatsMap.get(market) ?? {
                  tradeCount: 0,
                  totalPnl: 0,
                  winCount: 0,
                };
                current.tradeCount += 1;
                current.totalPnl += perMarketPnl;
                if (isWin) {
                  current.winCount += 1;
                }
                marketStatsMap.set(market, current);
              });
            });
          });
        }

        statsSnapshot = {
          capturedAt: Date.now(),
          marketUniverseSize: availableMarkets.length,
          runsAnalyzed: dedupedRunIds.length,
          marketStats: Object.fromEntries(marketStatsMap.entries()),
        };
        setHistoricalMarketStats(statsSnapshot);
      }

      if (!statsSnapshot) {
        setMarketFilterError('No historical market statistics were available. Using current top markets.');
        onChange(normalizeTopMarkets(availableMarkets));
        return;
      }

      const scoredMarkets = Object.entries(statsSnapshot.marketStats)
        .filter(([market]) => availableSet.has(market))
        .map(([market, stats]) => {
          const winRate = stats.tradeCount > 0 ? stats.winCount / stats.tradeCount : 0;
          const avgPnl = stats.tradeCount > 0 ? stats.totalPnl / stats.tradeCount : 0;

          const score =
            preset === 'popular'
              ? stats.tradeCount * 1.35 + winRate * 10 + Math.max(0, stats.totalPnl) * 0.01
              : avgPnl * 1.4 + winRate * 8 + Math.log10(stats.tradeCount + 1) * 2;

          return {
            market,
            score,
            tradeCount: stats.tradeCount,
            totalPnl: stats.totalPnl,
          };
        })
        .filter((entry) =>
          preset === 'profitable' ? entry.tradeCount >= 2 : entry.tradeCount >= 1
        );

      const rankedMarkets = scoredMarkets
        .sort((a, b) => {
          if (b.score !== a.score) return b.score - a.score;
          if (b.tradeCount !== a.tradeCount) return b.tradeCount - a.tradeCount;
          if (b.totalPnl !== a.totalPnl) return b.totalPnl - a.totalPnl;
          return a.market.localeCompare(b.market);
        })
        .map((entry) => entry.market);

      const topRanked = normalizeTopMarkets(rankedMarkets);

      if (topRanked.length < 2) {
        setMarketFilterError('Not enough historical market data yet. Falling back to top markets.');
        onChange(normalizeTopMarkets(availableMarkets));
        return;
      }

      onChange(topRanked);
      setMarketFilterError(
        `Ranked from ${statsSnapshot.runsAnalyzed} recent backtests${Date.now() - statsSnapshot.capturedAt <= MARKET_STATS_CACHE_TTL_MS ? ' (cached)' : ''}.`
      );
      console.log('📊 StrategyBuilder: Applied market preset', {
        preset,
        selectedCount: topRanked.length,
        previousCount: normalizedCurrentSelection.length,
        runsAnalyzed: statsSnapshot.runsAnalyzed,
      });
    } catch (err: unknown) {
      console.error('❌ StrategyBuilder: Failed to apply market preset', { preset, err });
      setMarketFilterError(getErrorMessage(err, 'Failed to apply market filter preset'));
    } finally {
      setMarketFilterLoading(null);
    }
  };

  if (loadingExisting) {
    return (
      <PageContainer size="narrow" className="flex min-h-[60vh] items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-white">Loading strategy...</p>
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer size="narrow">
      {/* Header */}
      <div className="mb-6">
        <h2 className="mb-2 text-3xl font-bold text-white">
          {isEditMode ? 'Edit Strategy' : 'Create New Strategy'}
        </h2>
        <p className="max-w-2xl text-sm leading-6 text-slate-500">
          {isEditMode
            ? 'Update your trading strategy parameters'
            : 'Configure parameters for your trading strategy'}
        </p>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="mb-6 rounded-xl border border-red-500 bg-red-500/10 px-4 py-3">
          <p className="text-red-400">{error}</p>
        </div>
      )}

      {/* Success Alert */}
      {successMessage && (
        <div className="mb-6 rounded-xl border border-green-500 bg-green-500/10 px-4 py-3">
          <p className="text-green-400">{successMessage}</p>
        </div>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit(onSubmit)} className="premium-panel space-y-6 sm:space-y-7">
        {/* Strategy Name */}
        <div>
          <label htmlFor="name" className={fieldLabelClass}>
            Strategy Name <span className="text-red-400">*</span>
          </label>
          <Controller
            name="name"
            control={control}
            rules={{
              required: 'Strategy name is required',
              minLength: { value: 3, message: 'Name must be at least 3 characters' },
              maxLength: { value: 100, message: 'Name must not exceed 100 characters' },
            }}
            render={({ field }) => (
              <input
                id="name"
                {...field}
                type="text"
                placeholder="e.g., Aggressive BTC/ETH Pair"
                className={compactInputClass}
              />
            )}
          />
          {errors.name && <p className="mt-1 text-red-400 text-sm">{errors.name.message}</p>}
        </div>

        {/* Category */}
        <div>
          <label className={fieldLabelClass} htmlFor="category">Category <span className="text-red-400">*</span></label>
          <Controller
            name="category"
            control={control}
            render={({ field }) => (
              <select id="category" {...field} className={`${compactInputClass} pr-10`}>
                <option value="pairs_trading">Pairs Trading (Cointegration)</option>
                <option value="momentum">Momentum</option>
                <option value="mean_reversion">Mean Reversion</option>
              </select>
            )}
          />
        </div>

        {/* Candle Resolution */}
        <div>
          <label className={fieldLabelClass} htmlFor="resolution">Candle Resolution <span className="text-red-400">*</span></label>
          <Controller
            name="resolution"
            control={control}
            rules={{
              required: 'Candle resolution is required',
            }}
            render={({ field }) => (
              <select id="resolution"
                {...field}
                value={normalizeDydxCandleResolution(field.value)}
                onChange={(event) =>
                  field.onChange(normalizeDydxCandleResolution(event.target.value))
                }
                className={`${compactInputClass} pr-10`}
              >
                {DYDX_CANDLE_RESOLUTION_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                    {option.value === '1HOUR' ? ' (Recommended)' : ''}
                  </option>
                ))}
              </select>
            )}
          />
          <p className={helperTextClass}>
            Timeframe for candle data (1HOUR recommended for stable backtests)
          </p>
          {['1MIN', '5MINS'].includes(normalizeDydxCandleResolution(formValues.resolution)) ? (
            <p className="mt-3 rounded-lg border border-yellow-400/30 bg-yellow-400/10 px-3 py-2 text-xs leading-5 text-yellow-400">
              High-frequency resolutions significantly increase backtest time. Consider using 1HOUR
              or higher for faster results.
            </p>
          ) : null}
        </div>

        {/* Description */}
        <div>
          <label className={fieldLabelClass} htmlFor="description">Description</label>
          <Controller
            name="description"
            control={control}
            render={({ field }) => (
              <textarea
                id="description"
                {...field}
                placeholder="Describe your strategy..."
                rows={3}
                className="premium-input min-h-32 px-4 py-3 text-sm"
              />
            )}
          />
        </div>

        <AIStrategyAdvisor
          strategy={strategyForAdvisor}
          recentBacktests={recentBacktests}
          onApplyParams={handleApplyAdvisorParams}
        />

        {/* Initial Investment Amount */}
        <div>
          <label htmlFor="initial_amount" className={fieldLabelClass}>
            Initial Investment Amount (USD) <span className="text-red-400">*</span>
          </label>
          <Controller
            name="initial_amount"
            control={control}
            rules={{
              required: 'Initial investment amount is required',
              max: { value: 1000000, message: 'Maximum investment is $1,000,000' },
            }}
            render={({ field }) => (
              <div className="flex items-center gap-3">
                <span className="text-sm font-semibold text-slate-400">$</span>
                <input
                  id="initial_amount"
                  {...field}
                  type="number"
                  max="1000000"
                  step="1"
                  placeholder="300"
                  className={`flex-1 ${compactInputClass}`}
                />
              </div>
            )}
          />
          <p className={helperTextClass}>
            Total capital allocated to this strategy for live trading
          </p>
          {errors.initial_amount && (
            <p className="mt-1 text-red-400 text-sm">{errors.initial_amount.message}</p>
          )}
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          <div>
            <label className={fieldLabelClass} htmlFor="runtime_network">Runtime Network</label>
            <Controller
              name="runtime_network"
              control={control}
              render={({ field }) => (
                <select id="runtime_network" {...field} className={`${compactInputClass} pr-10`}>
                  <option value="testnet">dYdX Testnet</option>
                  <option value="mainnet">dYdX Mainnet</option>
                </select>
              )}
            />
            <p className={helperTextClass}>
              Strategy runtime startup will use the stored key for this network via the backend.
            </p>
          </div>
          <div>
            <label className={fieldLabelClass} htmlFor="runtime_subaccount">Runtime Subaccount</label>
            <Controller
              name="runtime_subaccount"
              control={control}
              rules={{
                min: { value: 0, message: 'Subaccount must be 0 or higher' },
              }}
              render={({ field }) => (
                <input id="runtime_subaccount"
                  {...field}
                  type="number"
                  min="0"
                  step="1"
                  value={field.value ?? 0}
                  onChange={(event) => field.onChange(Number(event.target.value))}
                  className={compactInputClass}
                />
              )}
            />
            <p className={helperTextClass}>
              Use a dedicated dYdX subaccount to isolate live collateral for this strategy.
            </p>
            {errors.runtime_subaccount && (
              <p className="mt-1 text-red-400 text-sm">{errors.runtime_subaccount.message}</p>
            )}
          </div>
        </div>

        <div>
          <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <label htmlFor="selected_markets" className={fieldLabelClass}>dYdX Market Universe</label>
              <p className={helperTextClass}>
                Choose 2-150 markets to constrain live pair discovery and strategy backtests.
              </p>
            </div>
            <Controller
              name="selected_markets"
              control={control}
              render={({ field }) => {
                const value = Array.isArray(field.value) ? field.value : [];
                return (
                  <div className="flex w-full flex-wrap items-center justify-end gap-2 rounded-xl border border-slate-800/80 bg-slate-950/40 p-2 shadow-inner shadow-black/20">
                    <label className="flex h-10 items-center gap-2 rounded-lg border border-slate-700/80 bg-slate-950/70 px-3 text-xs font-semibold text-slate-300">
                      <span>Auto select</span>
                      <input
                        id="selected_markets"
                        type="number"
                        min={2}
                        max={MAX_SELECTED_MARKETS}
                        value={autoMarketLimit}
                        onChange={(event) => {
                          const nextValue = Number(event.target.value);
                          setAutoMarketLimit(
                            Math.min(
                              MAX_SELECTED_MARKETS,
                              Math.max(
                                2,
                                Number.isFinite(nextValue)
                                  ? Math.round(nextValue)
                                  : DEFAULT_AUTO_SELECTED_MARKETS
                              )
                            )
                          );
                        }}
                        className="h-7 w-14 rounded-md border border-slate-700 bg-slate-900 px-2 text-right text-xs text-cyan-100 outline-none focus:border-cyan-500"
                        aria-label="Markets to auto select"
                      />
                      <button
                        type="button"
                        onClick={() => setAutoMarketLimit(DEFAULT_AUTO_SELECTED_MARKETS)}
                        className="rounded border border-slate-700 bg-slate-900 px-1.5 py-0.5 text-[10px] font-semibold text-slate-300 transition hover:border-cyan-500/60 hover:text-cyan-100"
                        aria-label="Reset auto-select market limit to default"
                      >
                        Reset 35
                      </button>
                    </label>
                    <select
                      value={aiMarketProvider}
                      onChange={(event) =>
                        setAIMarketProvider(event.target.value as AIMarketProvider)
                      }
                      disabled={aiProviderStatusLoading || availableAIProviders.length === 0}
                      className={marketToolbarSelectClass}
                      aria-label="AI market filter provider"
                    >
                      {availableAIProviders.map((provider) => (
                        <option key={provider} value={provider}>
                          {getAIProviderLabel(provider)}
                        </option>
                      ))}
                    </select>
                    <select
                      value={aiMarketObjective}
                      onChange={(event) =>
                        setAIMarketObjective(event.target.value as AIMarketObjective)
                      }
                      className={marketToolbarSelectClass}
                      aria-label="AI market ranking objective"
                    >
                      <option value="balanced">Strategy-aware</option>
                      <option value="volume">Highest volume</option>
                      <option value="tradeable">Most tradeable</option>
                      <option value="future_gainers">Possible future gainers</option>
                      <option value="volatility">Volatility</option>
                      <option value="cointegration">Cointegration fit</option>
                    </select>
                    <button
                      type="button"
                      onClick={() => void applyMarketPreset('ai', field.onChange, value)}
                      disabled={
                        availableMarkets.length === 0 ||
                        marketFilterLoading !== null ||
                        availableAIProviders.length === 0
                      }
                      className="inline-flex h-10 items-center gap-2 rounded-lg border border-cyan-500/50 bg-cyan-500/10 px-3 text-xs font-semibold text-cyan-100 transition hover:border-cyan-300 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <Sparkles className="h-3.5 w-3.5" />
                      {marketFilterLoading === 'ai' ? 'Thinking…' : 'AI Pick'}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        const limit = Math.min(availableMarkets.length, MAX_SELECTED_MARKETS);
                        field.onChange(availableMarkets.slice(0, limit));
                        if (availableMarkets.length > MAX_SELECTED_MARKETS) {
                          setMarketFilterError(
                            `Selected the maximum ${MAX_SELECTED_MARKETS} markets supported by this strategy.`
                          );
                        } else {
                          setMarketFilterError(null);
                        }
                      }}
                      disabled={
                        availableMarkets.length === 0 ||
                        value.length >= Math.min(availableMarkets.length, MAX_SELECTED_MARKETS)
                      }
                      className={marketToolbarButtonClass}
                    >
                      <CheckSquare className="h-3.5 w-3.5" />
                      Select all
                    </button>
                    <button
                      type="button"
                      onClick={() => void applyMarketPreset('top20', field.onChange, value)}
                      disabled={availableMarkets.length === 0}
                      className={marketToolbarButtonClass}
                    >
                      <ListChecks className="h-3.5 w-3.5" />
                      Top by Count
                    </button>
                    <button
                      type="button"
                      onClick={() => void applyMarketPreset('popular', field.onChange, value)}
                      disabled={availableMarkets.length === 0 || marketFilterLoading !== null}
                      className={marketToolbarButtonClass}
                    >
                      <Star className="h-3.5 w-3.5" />
                      {marketFilterLoading === 'popular' ? 'Loading…' : 'Most Popular'}
                    </button>
                    <button
                      type="button"
                      onClick={() => void applyMarketPreset('profitable', field.onChange, value)}
                      disabled={availableMarkets.length === 0 || marketFilterLoading !== null}
                      className={marketToolbarButtonClass}
                    >
                      <Trophy className="h-3.5 w-3.5" />
                      {marketFilterLoading === 'profitable' ? 'Loading…' : 'Most Profitable'}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        field.onChange([]);
                        setMarketFilterError(null);
                      }}
                      disabled={value.length === 0}
                      className={marketToolbarButtonClass}
                    >
                      <X className="h-3.5 w-3.5" />
                      Clear
                    </button>
                    {marketRankingFreshnessLabel ? (
                      <button
                        type="button"
                        onClick={() => void forceRefreshRankings()}
                        disabled={rankingRefreshing || marketFilterLoading !== null}
                        title="Click to force-refresh historical market ranking data"
                        className={`inline-flex h-10 items-center gap-1.5 rounded-lg border px-2.5 text-[11px] font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${
                          marketRankingFreshnessLabel.isFresh
                            ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200 hover:border-emerald-400/60 hover:bg-emerald-500/20'
                            : 'border-amber-500/40 bg-amber-500/10 text-amber-200 hover:border-amber-400/60 hover:bg-amber-500/20'
                        }`}
                      >
                        <RefreshCw
                          className={`h-3 w-3 shrink-0 ${rankingRefreshing ? 'animate-spin' : ''}`}
                        />
                        {rankingRefreshing ? 'Refreshing…' : marketRankingFreshnessLabel.text}
                      </button>
                    ) : null}
                  </div>
                );
              }}
            />
          </div>

          {marketFilterError && <p className="mb-3 text-xs text-amber-300">{marketFilterError}</p>}
          {!aiProviderStatusLoading && availableAIProviders.length === 0 && (
            <p className="mb-3 text-xs text-amber-300">
              AI provider filtering is unavailable (no active provider credentials). Configure one
              in Settings → AI Filters.
            </p>
          )}

          <Controller
            name="selected_markets"
            control={control}
            render={({ field }) => {
              const value = Array.isArray(field.value) ? field.value : [];
              const toggleMarket = (market: string) => {
                if (value.includes(market)) {
                  field.onChange(value.filter((item) => item !== market));
                  return;
                }
                if (value.length >= MAX_SELECTED_MARKETS) {
                  return;
                }
                field.onChange([...value, market]);
              };

              const normalizedQuery = marketSearchQuery.trim().toLowerCase();
              const filteredMarkets = availableMarkets.filter((market) => {
                if (normalizedQuery.length > 0 && !market.toLowerCase().includes(normalizedQuery)) {
                  return false;
                }
                if (marketSelectionView === 'selected') {
                  return value.includes(market);
                }
                if (marketSelectionView === 'unselected') {
                  return !value.includes(market);
                }
                return true;
              });

              return (
                <div className="rounded-xl border border-slate-800/80 bg-slate-950/45 p-3 shadow-inner shadow-black/20">
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs font-semibold uppercase text-slate-500">
                      Market list
                    </span>
                    <span className="rounded-full border border-slate-800 bg-slate-900/80 px-2.5 py-1 text-xs text-slate-400">
                      {value.length} selected
                    </span>
                  </div>
                  <div className="mb-3 grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto_auto]">
                    <input
                      type="text"
                      value={marketSearchQuery}
                      onChange={(event) => setMarketSearchQuery(event.target.value)}
                      placeholder="Filter markets (e.g. BTC, ETH)"
                      className="h-9 rounded-md border border-slate-700 bg-slate-900 px-3 text-xs text-slate-200 outline-none transition focus:border-cyan-500"
                      aria-label="Filter market list"
                    />
                    <select
                      value={marketSelectionView}
                      onChange={(event) =>
                        setMarketSelectionView(event.target.value as MarketSelectionView)
                      }
                      className="h-9 rounded-md border border-slate-700 bg-slate-900 px-2 text-xs text-slate-300 outline-none transition focus:border-cyan-500"
                      aria-label="Market list selection filter"
                    >
                      <option value="all">All</option>
                      <option value="selected">Selected only</option>
                      <option value="unselected">Unselected only</option>
                    </select>
                    <button
                      type="button"
                      onClick={() => {
                        setMarketSearchQuery('');
                        setMarketSelectionView('all');
                      }}
                      className="h-9 rounded-md border border-slate-700 bg-slate-900 px-2 text-xs font-semibold text-slate-300 transition hover:border-cyan-500/60 hover:text-cyan-100"
                    >
                      Reset filters
                    </button>
                  </div>
                  {marketsLoading ? (
                    <p className="text-sm text-slate-400">Loading dYdX markets...</p>
                  ) : marketsError ? (
                    <p className="text-sm text-amber-300">{marketsError}</p>
                  ) : filteredMarkets.length === 0 ? (
                    <p className="text-sm text-slate-400">
                      No markets match the current filter. Try clearing the search or selection
                      filter.
                    </p>
                  ) : (
                    <div className="grid max-h-52 grid-cols-2 gap-2 overflow-y-auto pr-1 sm:grid-cols-3 lg:grid-cols-4">
                      {filteredMarkets.map((market) => {
                        const checked = value.includes(market);
                        const disabled = !checked && value.length >= MAX_SELECTED_MARKETS;
                        return (
                          <label
                            key={market}
                            className={`flex items-center gap-2 rounded-lg border px-2.5 py-2 text-xs transition ${
                              checked
                                ? 'border-cyan-500 bg-cyan-500/10 text-cyan-100'
                                : 'border-slate-800 text-slate-300 hover:border-slate-600'
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
              );
            }}
          />

          <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-slate-500">
            <span>
              Selected markets: <span className={inlineValueClass}>{selectedMarkets.length}</span> /{' '}
              {MAX_SELECTED_MARKETS}
            </span>
            <span>
              Candidate pairs:{' '}
              <span className={inlineValueClass}>{Math.max(0, candidatePairCount)}</span>
            </span>
            <span>
              Live tradable pairs cap:{' '}
              <span className={inlineValueClass}>
                {Math.max(1, Number(formValues.max_positions || 1))}
              </span>
            </span>
            {candidatePairCount > 0 ? (
              <button
                type="button"
                onClick={() => setShowPairPreview((value) => !value)}
                className="text-cyan-300 transition hover:text-cyan-100"
              >
                {showPairPreview ? 'Hide preview' : 'Preview pairs'}
              </button>
            ) : null}
          </div>

          {showPairPreview && selectedPairPreview.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {selectedPairPreview.map((pair) => (
                <span
                  key={pair}
                  className="rounded border border-cyan-500/40 bg-cyan-500/10 px-2 py-1 text-xs text-cyan-100"
                >
                  {pair}
                </span>
              ))}
              {candidatePairCount > selectedPairPreview.length ? (
                <span className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-400">
                  +{candidatePairCount - selectedPairPreview.length} more
                </span>
              ) : null}
            </div>
          )}
        </div>

        {/* Divider */}
        <div className={dividerClass}></div>

        {/* Parameters Section */}
        <div>
          <h2 className={sectionTitleClass}>Trading Parameters</h2>

          {/* Z-Score Threshold */}
          <div className="mb-6">
            <div className="flex justify-between items-center mb-2">
              <label htmlFor="zscore_threshold" className="text-sm font-semibold text-slate-200">
                Z-Score Threshold <span className="text-red-400">*</span>
              </label>
              <span className={inlineValueClass}>{formValues.zscore_threshold}</span>
            </div>
            <Controller
              name="zscore_threshold"
              control={control}
              rules={{
                required: 'Z-score threshold is required',
                min: { value: 0.5, message: 'Must be at least 0.5' },
                max: { value: 5.0, message: 'Must not exceed 5.0' },
              }}
              render={({ field }) => (
                <input id="zscore_threshold"
                  {...field}
                  type="range"
                  min="0.5"
                  max="5.0"
                  step="0.1"
                  className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                />
              )}
            />
            <p className={helperTextClass}>Range: 0.5 - 5.0 (lower = more frequent trades)</p>
            {errors.zscore_threshold && (
              <p className="mt-1 text-red-400 text-sm">{errors.zscore_threshold.message}</p>
            )}
          </div>

          {/* Stats Window */}
          <div className="mb-6">
            <div className="flex justify-between items-center mb-2">
              <label htmlFor="stats_window" className="text-sm font-semibold text-slate-200">
                Stats Window (hours) <span className="text-red-400">*</span>
              </label>
              <span className={inlineValueClass}>{formValues.stats_window}</span>
            </div>
            <Controller
              name="stats_window"
              control={control}
              rules={{
                required: 'Stats window is required',
                min: { value: 8, message: 'Must be at least 8' },
                max: { value: 120, message: 'Must not exceed 120' },
              }}
              render={({ field }) => (
                <input id="stats_window"
                  {...field}
                  type="range"
                  min="8"
                  max="120"
                  step="1"
                  className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                />
              )}
            />
            <p className={helperTextClass}>
              Range: 8 - 120 hours (rolling window for cointegration)
            </p>
            {errors.stats_window && (
              <p className="mt-1 text-red-400 text-sm">{errors.stats_window.message}</p>
            )}
          </div>

          {/* Max Half-Life */}
          <div className="mb-6">
            <div className="flex justify-between items-center mb-2">
              <label htmlFor="max_half_life" className="text-sm font-semibold text-slate-200">
                Max Half-Life (hours) <span className="text-red-400">*</span>
              </label>
              <span className={inlineValueClass}>{formValues.max_half_life}</span>
            </div>
            <Controller
              name="max_half_life"
              control={control}
              rules={{
                required: 'Max half-life is required',
                min: { value: 1, message: 'Must be at least 1' },
                max: { value: 72, message: 'Must not exceed 72' },
              }}
              render={({ field }) => (
                <input id="max_half_life"
                  {...field}
                  type="range"
                  min="1"
                  max="72"
                  step="0.5"
                  className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                />
              )}
            />
            <p className={helperTextClass}>Range: 1 - 72 hours (maximum mean reversion time)</p>
            {errors.max_half_life && (
              <p className="mt-1 text-red-400 text-sm">{errors.max_half_life.message}</p>
            )}
          </div>
        </div>

        {/* Divider */}
        <div className={dividerClass}></div>

        {/* Preset Buttons */}
        <div>
          <p className="mb-3 block text-sm font-semibold text-slate-200">Quick Presets</p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <button
              type="button"
              onClick={() => applyPreset('conservative')}
              className="rounded-lg border border-slate-700/80 bg-slate-900/70 px-4 py-2.5 text-sm font-medium text-white transition hover:border-cyan-500/35 hover:bg-slate-900"
            >
              🛡️ Conservative
            </button>
            <button
              type="button"
              onClick={() => applyPreset('balanced')}
              className="rounded-lg border border-slate-700/80 bg-slate-900/70 px-4 py-2.5 text-sm font-medium text-white transition hover:border-cyan-500/35 hover:bg-slate-900"
            >
              ⚖️ Balanced
            </button>
            <button
              type="button"
              onClick={() => applyPreset('aggressive')}
              className="rounded-lg border border-slate-700/80 bg-slate-900/70 px-4 py-2.5 text-sm font-medium text-white transition hover:border-cyan-500/35 hover:bg-slate-900"
            >
              ⚡ Aggressive
            </button>
          </div>
        </div>

        {/* Divider */}
        <div className={dividerClass}></div>

        {/* Advanced Settings Section */}
        <div>
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex w-full items-center justify-between rounded-lg border border-slate-700/80 bg-slate-900/70 px-4 py-3 text-white font-medium transition hover:border-cyan-500/35 hover:bg-slate-900"
          >
            <span>⚙️ Advanced Settings</span>
            <span className="text-lg">{showAdvanced ? '▼' : '▶'}</span>
          </button>

          {showAdvanced && (
            <div className="workspace-card mt-4 space-y-4 px-4 py-4">
              {/* Risk Management Parameters */}
              <div>
                <h3 className="mb-3 text-sm font-semibold text-slate-200">Risk Management</h3>
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  {/* Max Positions */}
                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <label htmlFor="max_positions" className="text-sm font-semibold text-slate-200">Max Positions</label>
                      <span className="text-sm text-cyan-300">{formValues.max_positions}</span>
                    </div>
                    <Controller
                      name="max_positions"
                      control={control}
                      render={({ field }) => (
                        <input
                          {...field}
                          type="range"
                          min="1"
                          max="50"
                          step="1"
                          className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                        />
                      )}
                    />
                    <p className="mt-1 text-xs leading-5 text-slate-500">
                      Maximum concurrently tradable pairs for this strategy.
                    </p>
                  </div>

                  {/* Max Drawdown % */}
                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <label htmlFor="max_drawdown_pct" className="text-sm font-semibold text-slate-200">Max Drawdown %</label>
                      <span className="text-sm text-cyan-300">{formValues.max_drawdown_pct}%</span>
                    </div>
                    <Controller
                      name="max_drawdown_pct"
                      control={control}
                      render={({ field }) => (
                        <input
                          {...field}
                          type="range"
                          min="5"
                          max="50"
                          step="0.5"
                          className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                        />
                      )}
                    />
                  </div>

                  {/* Stop Loss % */}
                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <label htmlFor="stop_loss_pct" className="text-sm font-semibold text-slate-200">Stop Loss %</label>
                      <span className="text-sm text-cyan-300">{formValues.stop_loss_pct}%</span>
                    </div>
                    <Controller
                      name="stop_loss_pct"
                      control={control}
                      render={({ field }) => (
                        <input
                          {...field}
                          type="range"
                          min="0.5"
                          max="10"
                          step="0.1"
                          className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                        />
                      )}
                    />
                  </div>

                  {/* Take Profit % */}
                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <label htmlFor="take_profit_pct" className="text-sm font-semibold text-slate-200">Take Profit %</label>
                      <span className="text-sm text-cyan-300">{formValues.take_profit_pct}%</span>
                    </div>
                    <Controller
                      name="take_profit_pct"
                      control={control}
                      render={({ field }) => (
                        <input
                          {...field}
                          type="range"
                          min="1"
                          max="20"
                          step="0.1"
                          className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                        />
                      )}
                    />
                  </div>

                  {/* Trailing Stop % */}
                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <label htmlFor="trailing_stop_pct" className="text-sm font-semibold text-slate-200">
                        Trailing Stop %
                      </label>
                      <span className="text-sm text-cyan-300">{formValues.trailing_stop_pct}%</span>
                    </div>
                    <Controller
                      name="trailing_stop_pct"
                      control={control}
                      render={({ field }) => (
                        <input
                          {...field}
                          type="range"
                          min="0.1"
                          max="5"
                          step="0.1"
                          className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                        />
                      )}
                    />
                  </div>
                </div>
              </div>

              {/* Trading Parameters */}
              <div className="border-t border-slate-800/80 pt-4">
                <h3 className="mb-3 text-sm font-semibold text-slate-200">Trading Parameters</h3>
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  {/* Amount Per Trade */}
                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <label htmlFor="usd_per_trade" className="text-sm font-semibold text-slate-200">
                        Amount Per Trade ($)
                      </label>
                      <span className="text-sm text-cyan-300">${formValues.usd_per_trade}</span>
                    </div>
                    <Controller
                      name="usd_per_trade"
                      control={control}
                      render={({ field }) => (
                        <input
                          {...field}
                          type="number"
                          min="1"
                          max="1000"
                          step="1"
                          className="premium-input px-3 py-2 text-sm"
                        />
                      )}
                    />
                    <p className="mt-1 text-xs leading-5 text-slate-500">
                      Capital per individual trade position
                    </p>
                  </div>

                  {/* Rebalance Interval */}
                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <label htmlFor="rebalance_interval_hours" className="text-sm font-semibold text-slate-200">
                        Rebalance (hours)
                      </label>
                      <span className="text-sm text-cyan-300">
                        {formValues.rebalance_interval_hours}h
                      </span>
                    </div>
                    <Controller
                      name="rebalance_interval_hours"
                      control={control}
                      render={({ field }) => (
                        <input
                          {...field}
                          type="range"
                          min="1"
                          max="168"
                          step="1"
                          className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                        />
                      )}
                    />
                  </div>

                  {/* Position Timeout */}
                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <label htmlFor="position_timeout_hours" className="text-sm font-semibold text-slate-200">
                        Position Timeout (hours)
                      </label>
                      <span className="text-sm text-cyan-300">
                        {formValues.position_timeout_hours}h
                      </span>
                    </div>
                    <Controller
                      name="position_timeout_hours"
                      control={control}
                      render={({ field }) => (
                        <input
                          {...field}
                          type="range"
                          min="6"
                          max="720"
                          step="6"
                          className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                        />
                      )}
                    />
                  </div>

                  {/* Max History Days */}
                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <label htmlFor="max_history_days" className="text-sm font-semibold text-slate-200">
                        Max History Days
                      </label>
                      <span className="text-sm text-cyan-300">
                        {formValues.max_history_days ?? 90}
                      </span>
                    </div>
                    <Controller
                      name="max_history_days"
                      control={control}
                      rules={{
                        min: { value: 30, message: 'Must be at least 30 days' },
                        max: { value: 365, message: 'Must not exceed 365 days' },
                      }}
                      render={({ field }) => (
                        <input
                          {...field}
                          type="number"
                          min="30"
                          max="365"
                          step="1"
                          className="premium-input px-3 py-2 text-sm"
                        />
                      )}
                    />
                    <p className="mt-1 text-xs leading-5 text-slate-500">
                      Default is 90 days of historical lookback.
                    </p>
                    {errors.max_history_days && (
                      <p className="mt-1 text-red-400 text-sm">{errors.max_history_days.message}</p>
                    )}
                  </div>

                  {/* Transaction Fee */}
                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <label htmlFor="transaction_fee" className="text-sm font-semibold text-slate-200">
                        Transaction Fee
                      </label>
                      <span className="text-sm text-cyan-300">
                        {Number(formValues.transaction_fee ?? 0.0005).toFixed(4)}
                      </span>
                    </div>
                    <Controller
                      name="transaction_fee"
                      control={control}
                      render={({ field }) => (
                        <input
                          {...field}
                          type="number"
                          min="0.0001"
                          max="0.01"
                          step="0.0001"
                          placeholder="0.0005"
                          className="premium-input px-3 py-2 text-sm"
                          onChange={(e) => field.onChange(parseFloat(e.target.value))}
                        />
                      )}
                    />
                    <p className="mt-1 text-xs leading-5 text-slate-500">
                      dYdX maker fee (typically 0.0005 = 0.05%)
                    </p>
                  </div>

                  {/* Slippage */}
                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <label htmlFor="slippage" className="text-sm font-semibold text-slate-200">Slippage</label>
                      <span className="text-sm text-cyan-300">
                        {Number(formValues.slippage ?? 0.001).toFixed(4)}
                      </span>
                    </div>
                    <Controller
                      name="slippage"
                      control={control}
                      render={({ field }) => (
                        <input
                          {...field}
                          type="number"
                          min="0.0001"
                          max="0.1"
                          step="0.0001"
                          placeholder="0.001"
                          className="premium-input px-3 py-2 text-sm"
                          onChange={(e) => field.onChange(parseFloat(e.target.value))}
                        />
                      )}
                    />
                    <p className="mt-1 text-xs leading-5 text-slate-500">
                      Estimated price slippage (typically 0.001 = 0.1%)
                    </p>
                  </div>
                </div>
              </div>

              {/* Behavior Toggles */}
              <div className="border-t border-slate-800/80 pt-4">
                <h3 className="mb-3 text-sm font-semibold text-slate-200">Behavior Settings</h3>
                <div className="space-y-3">
                  <div className="flex items-center space-x-2">
                    <Controller
                      name="find_cointegrated_pairs"
                      control={control}
                      render={({ field: { value, onChange } }) => (
                        <input
                          type="checkbox"
                          checked={Boolean(value)}
                          onChange={(e) => onChange(e.target.checked)}
                          className="w-4 h-4 rounded bg-slate-700 border-slate-600 text-blue-500"
                        />
                      )}
                    />
                    <label htmlFor="manage_exits" className="text-sm text-slate-300">Find Cointegrated Pairs</label>
                  </div>

                  <div className="flex items-center space-x-2">
                    <Controller
                      name="manage_exits"
                      control={control}
                      render={({ field: { value, onChange } }) => (
                        <input
                          type="checkbox"
                          checked={Boolean(value)}
                          onChange={(e) => onChange(e.target.checked)}
                          className="w-4 h-4 rounded bg-slate-700 border-slate-600 text-blue-500"
                        />
                      )}
                    />
                    <label htmlFor="place_trades" className="text-sm text-slate-300">Manage Exits</label>
                  </div>

                  <div className="flex items-center space-x-2">
                    <Controller
                      name="place_trades"
                      control={control}
                      render={({ field: { value, onChange } }) => (
                        <input
                          type="checkbox"
                          checked={Boolean(value)}
                          onChange={(e) => onChange(e.target.checked)}
                          className="w-4 h-4 rounded bg-slate-700 border-slate-600 text-blue-500"
                        />
                      )}
                    />
                    <label htmlFor="close_at_zscore_cross" className="text-sm text-slate-300">Place Trades</label>
                  </div>

                  <div className="flex items-center space-x-2">
                    <Controller
                      name="close_at_zscore_cross"
                      control={control}
                      render={({ field: { value, onChange } }) => (
                        <input
                          type="checkbox"
                          checked={Boolean(value)}
                          onChange={(e) => onChange(e.target.checked)}
                          className="w-4 h-4 rounded bg-slate-700 border-slate-600 text-blue-500"
                        />
                      )}
                    />
                    <label htmlFor="abort_all_positions" className="text-sm text-slate-300">Close at Z-Score Cross</label>
                  </div>

                  <div className="flex items-center space-x-2">
                    <Controller
                      name="abort_all_positions"
                      control={control}
                      render={({ field: { value, onChange } }) => (
                        <input
                          id="abort_all_positions"
                          type="checkbox"
                          checked={Boolean(value)}
                          onChange={(e) => onChange(e.target.checked)}
                          className="w-4 h-4 rounded bg-slate-700 border-slate-600 text-blue-500"
                        />
                      )}
                    />
                    <label className="text-sm text-slate-300" htmlFor="abort_all_positions">
                      Abort All Positions on Startup
                    </label>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Divider */}
        <div className={dividerClass}></div>

        {/* Is Public Toggle */}
        <div className="flex items-center space-x-3">
          <Controller
            name="is_public"
            control={control}
            render={({ field: { value, onChange } }) => (
              <input
                id="is_public"
                type="checkbox"
                checked={Boolean(value)}
                onChange={(e) => onChange(e.target.checked)}
                className="w-4 h-4 rounded bg-slate-700 border-slate-600 text-blue-500 focus:ring-2 focus:ring-blue-500"
              />
            )}
          />
          <label className="text-sm font-semibold text-slate-200" htmlFor="is_public">
            Make this strategy public (other users can view it)
          </label>
        </div>

        {/* Form Actions */}
        <div className="flex flex-col gap-4 pt-6 sm:flex-row">
          <button
            type="submit"
            disabled={loading}
            className="premium-button flex-1 items-center justify-center gap-2 rounded-lg bg-blue-600 px-6 py-3 text-white transition hover:bg-blue-700 disabled:bg-blue-600/50"
          >
            {loading ? (
              <>
                <span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                {isEditMode ? 'Updating...' : 'Creating...'}
              </>
            ) : (
              <>{isEditMode ? '✏️ Update Strategy' : '✨ Create Strategy'}</>
            )}
          </button>
          <button
            type="button"
            onClick={() => navigate('/strategies')}
            disabled={loading}
            className="flex-1 rounded-lg border border-slate-700/80 bg-slate-900/70 px-6 py-3 font-medium text-white transition hover:border-cyan-500/35 hover:bg-slate-900 disabled:opacity-60"
          >
            Cancel
          </button>
        </div>
      </form>

      {/* Help Text */}
      <div className="workspace-card mt-8 px-4 py-4">
        <h3 className="mb-2 text-sm font-semibold text-slate-200">📚 Parameter Guide</h3>
        <ul className="space-y-1 text-xs leading-6 text-slate-400">
          <li>
            <strong>Z-Score Threshold:</strong> Entry trigger. Lower = more trades, higher = more
            selective
          </li>
          <li>
            <strong>Stats Window:</strong> Historical period for cointegration analysis (rolling 21
            hours = ~24 candles at 1h)
          </li>
          <li>
            <strong>Max Half-Life:</strong> Maximum time for pair to mean-revert. Filters out
            slow-moving pairs
          </li>
        </ul>
      </div>
    </PageContainer>
  );
}
