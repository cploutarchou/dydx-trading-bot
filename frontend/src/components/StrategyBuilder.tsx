import { useEffect, useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import api from '../api';
import { PageContainer } from './PageContainer';

interface StrategyFormData {
  name: string;
  category: string;
  description: string;
  is_public: boolean;
  runtime_network: 'testnet' | 'mainnet';
  runtime_subaccount: number;
  resolution: string; // 1MIN, 5MINS, 15MINS, 1HOUR, 4HOURS, 1DAY
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

export default function StrategyBuilder() {
  const navigate = useNavigate();
  const location = useLocation();
  const { id: strategyId } = useParams<{ id?: string }>();
  const isEditMode = !!strategyId;

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [loadingExisting, setLoadingExisting] = useState(isEditMode);
  const [showAdvanced, setShowAdvanced] = useState(false);

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
      transaction_fee: 0.0005,
      slippage: 0.001,
    },
  });

  const formValues = watch();
  const fieldLabelClass = 'mb-2 block text-sm font-semibold text-slate-200';
  const helperTextClass = 'mt-2 text-xs leading-5 text-slate-500';
  const inlineValueClass = 'font-semibold text-cyan-300';
  const compactInputClass = 'premium-input px-4 py-2.5 text-sm';
  const sectionTitleClass = 'mb-4 text-lg font-semibold text-white';
  const dividerClass = 'my-2 border-t border-slate-800/80';

  // Load existing strategy if in edit mode
  useEffect(() => {
    if (isEditMode && strategyId) {
      loadStrategy(parseInt(strategyId, 10));
    }
  }, [isEditMode, strategyId]);

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
        const resolution = response.data.resolution || response.data.candle_resolution || '1HOUR';

        reset({
          ...strategyData,
          resolution,
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
      const cleanedData = {
        ...data,
        runtime_network: data.runtime_network,
        runtime_subaccount: Number(data.runtime_subaccount),
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
        initial_amount: initialAmount,
        transaction_fee: data.transaction_fee ? Number(data.transaction_fee) : 0.0005,
        slippage: data.slippage ? Number(data.slippage) : 0.001,
      };

      if (isEditMode && strategyId) {
        // Update existing strategy
        const response = await api.updateStrategy(parseInt(strategyId, 10), cleanedData);
        if (response.success) {
          setSuccessMessage(`Strategy "${cleanedData.name}" updated successfully!`);
          setTimeout(() => {
            navigate('/strategies');
          }, 1500);
        } else {
          setError(response.message || 'Failed to update strategy');
        }
      } else {
        // Create new strategy
        const response = await api.createStrategy(cleanedData);
        if (response.success) {
          setSuccessMessage(`Strategy "${cleanedData.name}" created successfully!`);
          reset();
          setTimeout(() => {
            navigate('/strategies');
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
        <h1 className="mb-2 text-3xl font-bold text-white">
          {isEditMode ? 'Edit Strategy' : 'Create New Strategy'}
        </h1>
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
          <label className={fieldLabelClass}>
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
          <label className={fieldLabelClass}>
            Category <span className="text-red-400">*</span>
          </label>
          <Controller
            name="category"
            control={control}
            render={({ field }) => (
              <select {...field} className={`${compactInputClass} pr-10`}>
                <option value="pairs_trading">Pairs Trading (Cointegration)</option>
                <option value="momentum">Momentum</option>
                <option value="mean_reversion">Mean Reversion</option>
              </select>
            )}
          />
        </div>

        {/* Candle Resolution */}
        <div>
          <label className={fieldLabelClass}>
            Candle Resolution <span className="text-red-400">*</span>
          </label>
          <Controller
            name="resolution"
            control={control}
            rules={{
              required: 'Candle resolution is required',
            }}
            render={({ field }) => (
              <select {...field} className={`${compactInputClass} pr-10`}>
                <option value="1MIN">1 Minute 🐢 (Very Slow - ~900K candles/90d)</option>
                <option value="5MINS">5 Minutes 🐌 (Slow - ~180K candles/90d)</option>
                <option value="15MINS">15 Minutes 🚶 (Moderate - ~60K candles/90d)</option>
                <option value="1HOUR">1 Hour ✅ (Recommended - ~2,160 candles/90d)</option>
                <option value="4HOURS">4 Hours ⚡ (Fast - ~540 candles/90d)</option>
                <option value="1DAY">1 Day ⚡⚡ (Very Fast - ~90 candles/90d)</option>
              </select>
            )}
          />
          <p className={helperTextClass}>
            Timeframe for candle data (1HOUR recommended for stable backtests)
          </p>
          {formValues.resolution === '1MIN' || formValues.resolution === '5MINS' ? (
            <p className="mt-3 rounded-lg border border-yellow-400/30 bg-yellow-400/10 px-3 py-2 text-xs leading-5 text-yellow-400">
              ⚠️ High-frequency resolutions significantly increase backtest time. Consider using
              1HOUR or higher for faster results.
            </p>
          ) : null}
        </div>

        {/* Description */}
        <div>
          <label className={fieldLabelClass}>Description</label>
          <Controller
            name="description"
            control={control}
            render={({ field }) => (
              <textarea
                {...field}
                placeholder="Describe your strategy..."
                rows={3}
                className="premium-input min-h-32 px-4 py-3 text-sm"
              />
            )}
          />
        </div>

        {/* Initial Investment Amount */}
        <div>
          <label className={fieldLabelClass}>
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
            <label className={fieldLabelClass}>Runtime Network</label>
            <Controller
              name="runtime_network"
              control={control}
              render={({ field }) => (
                <select {...field} className={`${compactInputClass} pr-10`}>
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
            <label className={fieldLabelClass}>Runtime Subaccount</label>
            <Controller
              name="runtime_subaccount"
              control={control}
              rules={{
                min: { value: 0, message: 'Subaccount must be 0 or higher' },
              }}
              render={({ field }) => (
                <input
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

        {/* Divider */}
        <div className={dividerClass}></div>

        {/* Parameters Section */}
        <div>
          <h2 className={sectionTitleClass}>Trading Parameters</h2>

          {/* Z-Score Threshold */}
          <div className="mb-6">
            <div className="flex justify-between items-center mb-2">
              <label className="text-sm font-semibold text-slate-200">
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
                <input
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
              <label className="text-sm font-semibold text-slate-200">
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
                <input
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
              <label className="text-sm font-semibold text-slate-200">
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
                <input
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
          <label className="mb-3 block text-sm font-semibold text-slate-200">Quick Presets</label>
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
                      <label className="text-sm font-semibold text-slate-200">Max Positions</label>
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
                          max="20"
                          step="1"
                          className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                        />
                      )}
                    />
                  </div>

                  {/* Max Drawdown % */}
                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <label className="text-sm font-semibold text-slate-200">Max Drawdown %</label>
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
                      <label className="text-sm font-semibold text-slate-200">Stop Loss %</label>
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
                      <label className="text-sm font-semibold text-slate-200">Take Profit %</label>
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
                      <label className="text-sm font-semibold text-slate-200">
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
                      <label className="text-sm font-semibold text-slate-200">
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
                      <label className="text-sm font-semibold text-slate-200">
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
                      <label className="text-sm font-semibold text-slate-200">
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

                  {/* Transaction Fee */}
                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <label className="text-sm font-semibold text-slate-200">
                        Transaction Fee
                      </label>
                      <span className="text-sm text-cyan-300">
                        {(formValues.transaction_fee || 0.0005).toFixed(4)}
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
                      <label className="text-sm font-semibold text-slate-200">Slippage</label>
                      <span className="text-sm text-cyan-300">
                        {(formValues.slippage || 0.001).toFixed(4)}
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
                    <label className="text-sm text-slate-300">Find Cointegrated Pairs</label>
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
                    <label className="text-sm text-slate-300">Manage Exits</label>
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
                    <label className="text-sm text-slate-300">Place Trades</label>
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
                    <label className="text-sm text-slate-300">Close at Z-Score Cross</label>
                  </div>

                  <div className="flex items-center space-x-2">
                    <Controller
                      name="abort_all_positions"
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
                    <label className="text-sm text-slate-300">Abort All Positions on Startup</label>
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
                type="checkbox"
                checked={Boolean(value)}
                onChange={(e) => onChange(e.target.checked)}
                className="w-4 h-4 rounded bg-slate-700 border-slate-600 text-blue-500 focus:ring-2 focus:ring-blue-500"
              />
            )}
          />
          <label className="text-sm font-semibold text-slate-200">
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
