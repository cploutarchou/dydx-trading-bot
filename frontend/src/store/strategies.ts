/**
 * Zustand store for strategy state management
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import api from '../api';

export interface Strategy {
  id: number;
  name: string;
  category?: string;
  description?: string;
  is_public?: boolean;
  user_id?: number;
  runtime_strategy?: string;
  resolution?: string;
  candle_resolution?: string;
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
  transaction_fee?: number;
  slippage?: number;
  starting_balance?: number;
  max_history_days?: number;
  benchmark_symbol?: string;
  risk_free_rate?: number;
  initial_amount?: number;
  pair_selection_mode?: 'liquidity' | 'volatility' | 'cointegration' | 'input';
  created_at?: string;
  updated_at?: string;
}

interface StrategyStore {
  strategies: Strategy[];
  selectedStrategy: Strategy | null;
  loading: boolean;
  error: string | null;
  fetchStrategies: () => Promise<void>;
  selectStrategy: (strategy: Strategy) => void;
  clearSelectedStrategy: () => void;
  createStrategy: (data: Partial<Strategy>) => Promise<Strategy>;
  updateStrategy: (id: number, data: Partial<Strategy>) => Promise<Strategy>;
  deleteStrategy: (id: number) => Promise<void>;
  duplicateStrategy: (strategy: Strategy) => Promise<Strategy>;
  getPublicStrategies: () => Promise<Strategy[]>;
}

const toStrategy = (value: unknown): Strategy => value as Strategy;

const getErrorMessage = (error: unknown, fallback: string): string =>
  error instanceof Error ? error.message : fallback;

const buildStrategyPayload = (data: Partial<Strategy>) => ({
  name: data.name || 'Untitled Strategy',
  category: data.category,
  description: data.description,
  is_public: data.is_public,
  user_id: data.user_id,
  runtime_strategy: data.runtime_strategy,
  resolution: data.resolution,
  candle_resolution: data.candle_resolution ?? data.resolution,
  zscore_threshold: data.zscore_threshold,
  stats_window: data.stats_window,
  max_half_life: data.max_half_life,
  usd_per_trade: data.usd_per_trade,
  usd_min_collateral: data.usd_min_collateral,
  close_at_zscore_cross: data.close_at_zscore_cross,
  find_cointegrated_pairs: data.find_cointegrated_pairs,
  manage_exits: data.manage_exits,
  place_trades: data.place_trades,
  abort_all_positions: data.abort_all_positions,
  max_positions: data.max_positions,
  max_drawdown_pct: data.max_drawdown_pct,
  stop_loss_pct: data.stop_loss_pct,
  take_profit_pct: data.take_profit_pct,
  trailing_stop_pct: data.trailing_stop_pct,
  rebalance_interval_hours: data.rebalance_interval_hours,
  position_timeout_hours: data.position_timeout_hours,
  transaction_fee: data.transaction_fee,
  slippage: data.slippage,
  starting_balance: data.starting_balance,
  max_history_days: data.max_history_days,
  benchmark_symbol: data.benchmark_symbol,
  risk_free_rate: data.risk_free_rate,
  initial_amount: data.initial_amount,
  pair_selection_mode: data.pair_selection_mode,
});

export const useStrategyStore = create<StrategyStore>()(
  persist(
    (set) => ({
      strategies: [],
      selectedStrategy: null,
      loading: false,
      error: null,

      fetchStrategies: async () => {
        set({ loading: true, error: null });
        try {
          const response = await api.listStrategies(0, 100);
          const strategies = Array.isArray(response.data?.strategies)
            ? response.data.strategies.map(toStrategy)
            : [];
          set({ strategies });
        } catch (error: unknown) {
          set({ error: getErrorMessage(error, 'Failed to fetch strategies') });
        } finally {
          set({ loading: false });
        }
      },

      selectStrategy: (strategy: Strategy) => {
        set({ selectedStrategy: strategy });
      },

      clearSelectedStrategy: () => {
        set({ selectedStrategy: null });
      },

      createStrategy: async (data: Partial<Strategy>) => {
        set({ loading: true, error: null });
        try {
          const response = await api.createStrategy(buildStrategyPayload(data));
          const newStrategy = toStrategy(response.data);
          set((state) => ({
            strategies: [...state.strategies, newStrategy],
          }));
          return newStrategy;
        } catch (error: unknown) {
          set({ error: getErrorMessage(error, 'Failed to create strategy') });
          throw error;
        } finally {
          set({ loading: false });
        }
      },

      updateStrategy: async (id: number, data: Partial<Strategy>) => {
        set({ loading: true, error: null });
        try {
          const response = await api.updateStrategy(id, buildStrategyPayload(data));
          const updatedStrategy = toStrategy(response.data);
          set((state) => ({
            strategies: state.strategies.map((s) => (s.id === id ? updatedStrategy : s)),
            selectedStrategy:
              state.selectedStrategy?.id === id ? updatedStrategy : state.selectedStrategy,
          }));
          return updatedStrategy;
        } catch (error: unknown) {
          set({ error: getErrorMessage(error, 'Failed to update strategy') });
          throw error;
        } finally {
          set({ loading: false });
        }
      },

      deleteStrategy: async (id: number) => {
        set({ loading: true, error: null });
        try {
          await api.deleteStrategy(id);
          set((state) => ({
            strategies: state.strategies.filter((s) => s.id !== id),
            selectedStrategy: state.selectedStrategy?.id === id ? null : state.selectedStrategy,
          }));
        } catch (error: unknown) {
          set({ error: getErrorMessage(error, 'Failed to delete strategy') });
          throw error;
        } finally {
          set({ loading: false });
        }
      },

      duplicateStrategy: async (strategy: Strategy) => {
        set({ loading: true, error: null });
        try {
          const response = await api.createStrategy(
            buildStrategyPayload({
              ...strategy,
              name: `${strategy.name} (copy)`,
            })
          );
          const newStrategy = toStrategy(response.data);
          set((state) => ({
            strategies: [...state.strategies, newStrategy],
          }));
          return newStrategy;
        } catch (error: unknown) {
          set({ error: getErrorMessage(error, 'Failed to duplicate strategy') });
          throw error;
        } finally {
          set({ loading: false });
        }
      },

      getPublicStrategies: async () => {
        try {
          const response = await api.getPublicStrategies();
          const strategies = Array.isArray(response.data?.strategies)
            ? response.data.strategies.map(toStrategy)
            : [];
          return strategies;
        } catch (error: unknown) {
          console.error('Failed to fetch public strategies:', error);
          return [];
        }
      },
    }),
    {
      name: 'strategy-store',
      partialize: (state) => ({
        selectedStrategy: state.selectedStrategy,
      }),
    }
  )
);
