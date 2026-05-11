import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import { Activity, Loader2, Save, ShieldCheck, SlidersHorizontal } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import api, { type ArbitrageRuntimeSettings as RuntimeSettings } from '../api';
import { useToastStore } from './ErrorBoundary';

const getMutationErrorMessage = (error: unknown): string => {
  if (error instanceof AxiosError) {
    const data = error.response?.data as Record<string, unknown> | undefined;
    if (typeof data?.error === 'string' && data.error.length > 0) return data.error;
    if (typeof data?.message === 'string' && data.message.length > 0) return data.message;
    return error.message;
  }
  return error instanceof Error ? error.message : 'Unknown error';
};

const DEFAULT_SETTINGS: RuntimeSettings = {
  arbitrage_improvements_enabled: false,
  pair_priority_engine_enabled: false,
  polymarket_signals_enabled: false,
  defillama_signals_enabled: false,
  news_signals_enabled: false,
  auto_execution_changes_enabled: false,
  pair_priority_max_pairs: 0,
  pair_priority_stale_seconds: 86400,
};

const TOGGLE_FIELDS: Array<{ key: keyof RuntimeSettings; label: string; description: string }> = [
  {
    key: 'arbitrage_improvements_enabled',
    label: 'Efficiency improvements',
    description: 'Cache and de-duplicate repeated market-data calls in the live scan path.',
  },
  {
    key: 'pair_priority_engine_enabled',
    label: 'Pair priority engine',
    description: 'Rank stored cointegrated pairs before live scanning.',
  },
  {
    key: 'polymarket_signals_enabled',
    label: 'Polymarket signals',
    description: 'Reserved for narrative signals that only affect pair priority.',
  },
  {
    key: 'defillama_signals_enabled',
    label: 'DefiLlama signals',
    description: 'Reserved for liquidity context that only affects pair priority.',
  },
  {
    key: 'news_signals_enabled',
    label: 'News signals',
    description: 'Reserved for classified news signals that only affect pair priority.',
  },
  {
    key: 'auto_execution_changes_enabled',
    label: 'Execution behavior changes',
    description: 'Keep off unless execution-safety changes have been tested on testnet.',
  },
];

export function ArbitrageRuntimeSettings() {
  const queryClient = useQueryClient();
  const successToast = useToastStore((state) => state.success);
  const errorToast = useToastStore((state) => state.error);
  const [draft, setDraft] = useState<RuntimeSettings>(DEFAULT_SETTINGS);

  const settingsQuery = useQuery({
    queryKey: ['settings', 'arbitrage-runtime'],
    queryFn: async () => api.getArbitrageRuntimeSettings(),
    staleTime: 15_000,
  });

  useEffect(() => {
    const loaded = settingsQuery.data?.data;
    if (loaded) {
      setDraft({ ...DEFAULT_SETTINGS, ...loaded });
    }
  }, [settingsQuery.data]);

  const savedSettings = useMemo(
    () => ({ ...DEFAULT_SETTINGS, ...(settingsQuery.data?.data || {}) }),
    [settingsQuery.data]
  );

  const hasChanges = JSON.stringify(draft) !== JSON.stringify(savedSettings);
  const syncStatus = settingsQuery.data?.bot_sync_status || 'unknown';

  const saveMutation = useMutation({
    mutationFn: async () => api.updateArbitrageRuntimeSettings(draft),
    onSuccess: (response) => {
      setDraft({ ...DEFAULT_SETTINGS, ...response.data });
      successToast(
        response.bot_sync_status === 'synced' ? 'Arbitrage settings synced' : 'Arbitrage settings saved',
        response.bot_sync_status === 'synced'
          ? 'The bot runtime accepted the updated feature flags.'
          : 'The database was updated; sync will complete when the bot API is reachable.'
      );
      void queryClient.invalidateQueries({ queryKey: ['settings', 'arbitrage-runtime'] });
      void queryClient.invalidateQueries({ queryKey: ['arbitrage'] });
    },
    onError: (error: unknown) => {
      errorToast('Failed to save arbitrage settings', getMutationErrorMessage(error));
    },
  });

  const setBoolean = (key: keyof RuntimeSettings, value: boolean) => {
    setDraft((current) => ({ ...current, [key]: value }));
  };

  const setNumber = (key: keyof RuntimeSettings, value: string) => {
    const parsed = Number(value);
    setDraft((current) => ({ ...current, [key]: Number.isFinite(parsed) ? Math.max(0, parsed) : 0 }));
  };

  return (
    <div className="premium-panel">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="premium-icon-wrap text-cyan-300">
            <SlidersHorizontal className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-2xl font-semibold text-white">Arbitrage Runtime</h2>
            <p className="mt-1 text-sm text-slate-400">
              DB-backed feature controls for scan efficiency, pair priority, and future signal inputs.
            </p>
          </div>
        </div>
        <span className="operator-status-pill" data-tone={syncStatus === 'synced' ? 'positive' : 'warning'}>
          {syncStatus === 'synced' ? 'Bot synced' : 'DB saved'}
        </span>
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-3">
        <div className="rounded-lg border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="mb-2 flex items-center gap-2 text-slate-200">
            <ShieldCheck className="h-4 w-4 text-emerald-300" />
            Execution safety
          </div>
          <p className="text-lg font-semibold text-white">
            {draft.auto_execution_changes_enabled ? 'Explicitly enabled' : 'Default protected'}
          </p>
          <p className="mt-1 text-xs text-slate-500">Trading behavior remains unchanged while off.</p>
        </div>
        <div className="rounded-lg border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="mb-2 flex items-center gap-2 text-slate-200">
            <Activity className="h-4 w-4 text-cyan-300" />
            Pair cap
          </div>
          <p className="text-lg font-semibold text-white">{draft.pair_priority_max_pairs || 'All'}</p>
          <p className="mt-1 text-xs text-slate-500">A zero cap preserves the full pair universe.</p>
        </div>
        <div className="rounded-lg border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="mb-2 flex items-center gap-2 text-slate-200">
            <SlidersHorizontal className="h-4 w-4 text-amber-300" />
            Stale window
          </div>
          <p className="text-lg font-semibold text-white">{draft.pair_priority_stale_seconds}s</p>
          <p className="mt-1 text-xs text-slate-500">Used by pair-priority scoring only.</p>
        </div>
      </div>

      <div className="mt-6 grid gap-3">
        {TOGGLE_FIELDS.map((field) => (
          <label
            key={field.key}
            className="flex items-center justify-between gap-4 rounded-lg border border-slate-700/60 bg-slate-950/35 p-4"
          >
            <span>
              <span className="block text-sm font-semibold text-slate-100">{field.label}</span>
              <span className="mt-1 block text-xs text-slate-500">{field.description}</span>
            </span>
            <input
              type="checkbox"
              checked={Boolean(draft[field.key])}
              onChange={(event) => setBoolean(field.key, event.target.checked)}
              className="h-5 w-5 rounded border-slate-600 bg-slate-900 text-cyan-500 focus:ring-cyan-500"
            />
          </label>
        ))}
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <label className="block">
          <span className="text-sm font-semibold text-slate-200">Pair priority max pairs</span>
          <input
            type="number"
            min={0}
            value={draft.pair_priority_max_pairs}
            onChange={(event) => setNumber('pair_priority_max_pairs', event.target.value)}
            className="premium-input mt-2"
          />
        </label>
        <label className="block">
          <span className="text-sm font-semibold text-slate-200">Pair stale seconds</span>
          <input
            type="number"
            min={0}
            value={draft.pair_priority_stale_seconds}
            onChange={(event) => setNumber('pair_priority_stale_seconds', event.target.value)}
            className="premium-input mt-2"
          />
        </label>
      </div>

      <div className="mt-6 flex flex-wrap items-center justify-end gap-3 border-t border-slate-700/60 pt-4">
        <button
          type="button"
          onClick={() => setDraft(savedSettings)}
          disabled={!hasChanges || saveMutation.isPending}
          className="premium-button premium-button-secondary disabled:opacity-50"
        >
          Discard
        </button>
        <button
          type="button"
          onClick={() => saveMutation.mutate()}
          disabled={!hasChanges || saveMutation.isPending}
          className="premium-button inline-flex items-center gap-2 disabled:opacity-50"
        >
          {saveMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Save and sync
        </button>
      </div>
    </div>
  );
}
