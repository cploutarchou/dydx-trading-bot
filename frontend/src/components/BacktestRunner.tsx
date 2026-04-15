import { Play } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import { useStrategyStore } from '../store/strategies';

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
  const { strategies, fetchStrategies } = useStrategyStore();
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

  const runBacktestMutation = useMutation({
    mutationFn: (payload: ApiBacktestRequest) => api.runBacktest(payload),
  });

  // Fetch strategies on mount
  useEffect(() => {
    void fetchStrategies();
  }, [fetchStrategies]);

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

  const handleStrategyChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const id = e.target.value ? parseInt(e.target.value) : null;
    setSelectedStrategyId(id);

    if (id && useStrategy) {
      const strategy = strategies.find((s) => s.id === id);
      if (strategy) {
        setFormData((prev) => ({
          ...prev,
          strategy_id: id,
          initial_balance: strategy.starting_balance || strategy.initial_amount || prev.initial_balance,
          benchmark_symbol: strategy.benchmark_symbol || prev.benchmark_symbol,
          trading_parameters: {
            ...prev.trading_parameters,
            resolution: strategy.candle_resolution || strategy.resolution,
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
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    try {
      if (formData.start_date > formData.end_date) {
        setError('Start date must be before end date');
        return;
      }

      const tp = formData.trading_parameters;
      const cleanedData = {
        start_date: formData.start_date,
        end_date: formData.end_date,
        name: formData.name || 'ui-backtest',
        initial_balance: Number(formData.initial_balance),
        max_pairs: Number(formData.max_pairs),
        benchmark_symbol: formData.benchmark_symbol,
        pair_selection_mode: tp.pair_selection_mode || formData.pair_selection_mode || 'liquidity',
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
          ...(tp.benchmark_symbol !== undefined && {
            benchmark_symbol: tp.benchmark_symbol,
          }),
          ...(tp.max_history_days !== undefined && {
            max_history_days: Number(tp.max_history_days),
          }),
          ...(tp.pair_selection_mode !== undefined && {
            pair_selection_mode: tp.pair_selection_mode,
          }),
        },
        ...(useStrategy && selectedStrategyId && { strategy_id: selectedStrategyId }),
      } satisfies BacktestRunRequest;
      setLoading(true);
      const result = await runBacktestMutation.mutateAsync(cleanedData as ApiBacktestRequest);
      const runId = extractRunId(result);

      if (onBacktestComplete) {
        onBacktestComplete();
      }

      if (runId) {
        navigate(`/backtest/${runId}`);
      } else {
        setError('Backtest started but no run ID was returned by the API');
      }
    } catch (err: unknown) {
      console.error('❌ BacktestRunner: Error:', err);
      setError(getErrorMessage(err, 'Failed to start backtest'));
    } finally {
      setLoading(false);
    }
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
          Tune the run, keep risk assumptions explicit, and send the job through the backend
          control plane.
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-700 bg-red-900/35 p-4 text-sm text-red-200">
          {error}
        </div>
      )}

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
                  Strategy parameters loaded below — you can override them before running.
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
            <label className={labelClass}>
              Number of Markets (0 = All)
            </label>
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
            <label className={labelClass}>
              Pair Selection Mode
            </label>
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
          <div>
            <label className={labelClass}>
              Z-Score Threshold
            </label>
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
            <label className={labelClass}>
              Stats Window (days)
            </label>
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
            <label className={labelClass}>
              Starting Balance
            </label>
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
            <label className={labelClass}>
              Candle Resolution
            </label>
            <select
              name="resolution"
              value={formData.trading_parameters.resolution || '1HOUR'}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  trading_parameters: {
                    ...prev.trading_parameters,
                    resolution: e.target.value,
                  },
                }))
              }
              className={inputClass}
            >
              <option value="15MINS">15 Minutes</option>
              <option value="30MINS">30 Minutes</option>
              <option value="1HOUR">1 Hour</option>
              <option value="4HOUR">4 Hours</option>
              <option value="1DAY">1 Day</option>
            </select>
          </div>
          <div>
            <label className={labelClass}>
              Transaction Fee
            </label>
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
            <label className={labelClass}>
              Benchmark Symbol
            </label>
            <input
              type="text"
              name="benchmark_symbol"
              value={formData.benchmark_symbol || formData.trading_parameters.benchmark_symbol || 'BTC-USD'}
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
            <label className={labelClass}>
              Risk-Free Rate
            </label>
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
            <label className={labelClass}>
              Max History Days
            </label>
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
