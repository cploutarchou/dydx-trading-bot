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
  resolution?: string;
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

const buildStrategyPayload = (data: Partial<Strategy>) => ({
  name: data.name || 'Untitled Strategy',
  description: data.description,
  zscore_threshold: data.zscore_threshold,
  max_half_life: data.max_half_life,
  usd_per_trade: data.usd_per_trade,
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
        } catch (error: any) {
          set({ error: error.message || 'Failed to fetch strategies' });
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
        } catch (error: any) {
          set({ error: error.message || 'Failed to create strategy' });
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
        } catch (error: any) {
          set({ error: error.message || 'Failed to update strategy' });
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
        } catch (error: any) {
          set({ error: error.message || 'Failed to delete strategy' });
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
        } catch (error: any) {
          set({ error: error.message || 'Failed to duplicate strategy' });
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
        } catch (error: any) {
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
