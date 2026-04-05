import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { DatabaseZap, KeyRound, Loader2, ShieldCheck, Trash2 } from 'lucide-react';
import { useState } from 'react';
import api from '../api';
import { useToastStore } from './ErrorBoundary';

export function CodexSettings() {
  const [apiKey, setApiKey] = useState('');
  const [label, setLabel] = useState('Personal free plan');
  const queryClient = useQueryClient();
  const successToast = useToastStore((state) => state.success);
  const errorToast = useToastStore((state) => state.error);

  const statusQuery = useQuery({
    queryKey: ['codex', 'status'],
    queryFn: async () => {
      const response = await api.getCodexStatus();
      return response.data;
    },
    staleTime: 30_000,
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      const response = await api.saveCodexKey({ api_key: apiKey, label });
      return response.data;
    },
    onSuccess: () => {
      setApiKey('');
      successToast('Codex.io key saved', 'Your personal market-intel key is now active.');
      void queryClient.invalidateQueries({ queryKey: ['codex'] });
    },
    onError: (error: unknown) => {
      errorToast('Failed to save Codex.io key', error instanceof Error ? error.message : 'Unknown error');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      const response = await api.deleteCodexKey();
      return response.data;
    },
    onSuccess: () => {
      successToast('Codex.io key removed', 'The app has reverted to the shared fallback key if available.');
      void queryClient.invalidateQueries({ queryKey: ['codex'] });
    },
    onError: (error: unknown) => {
      errorToast('Failed to delete Codex.io key', error instanceof Error ? error.message : 'Unknown error');
    },
  });

  const status = statusQuery.data;

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800 p-6 shadow">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white">Codex.io</h2>
          <p className="mt-1 text-sm text-slate-400">
            Manage your personal Codex.io market-intel key. The browser never sends requests directly to Codex.io.
          </p>
        </div>
        <div className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-cyan-300">
          Free Plan
        </div>
      </div>

      {statusQuery.isLoading ? (
        <div className="flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-900/50 px-4 py-3 text-sm text-slate-300">
          <Loader2 className="h-4 w-4 animate-spin" />
          Checking Codex.io availability...
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div className="rounded-xl border border-slate-700 bg-slate-900/50 p-4">
            <div className="mb-2 flex items-center gap-2 text-slate-200">
              <DatabaseZap className="h-4 w-4 text-blue-300" />
              Active source
            </div>
            <p className="text-lg font-semibold text-white">
              {status?.active_key_source === 'user'
                ? 'Your key'
                : status?.active_key_source === 'shared'
                  ? 'Shared fallback'
                  : 'Unavailable'}
            </p>
            <p className="mt-1 text-xs text-slate-400">{status?.message}</p>
          </div>

          <div className="rounded-xl border border-slate-700 bg-slate-900/50 p-4">
            <div className="mb-2 flex items-center gap-2 text-slate-200">
              <ShieldCheck className="h-4 w-4 text-emerald-300" />
              Plan limits
            </div>
            <p className="text-lg font-semibold text-white">
              {status?.capabilities?.requests_per_second ?? 5} req/sec
            </p>
            <p className="mt-1 text-xs text-slate-400">
              {status?.capabilities?.monthly_requests ?? 10000} requests/month, query-only, no webhooks or websockets
            </p>
          </div>

          <div className="rounded-xl border border-slate-700 bg-slate-900/50 p-4">
            <div className="mb-2 flex items-center gap-2 text-slate-200">
              <KeyRound className="h-4 w-4 text-amber-300" />
              Key availability
            </div>
            <p className="text-lg font-semibold text-white">
              {status?.user_key_available ? 'Personal key saved' : 'No personal key'}
            </p>
            <p className="mt-1 text-xs text-slate-400">
              Shared fallback: {status?.shared_key_available ? 'available' : 'not configured'}
            </p>
          </div>
        </div>
      )}

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[1.1fr,0.9fr]">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/45 p-5">
          <h3 className="text-lg font-semibold text-white">Save personal API key</h3>
          <p className="mt-1 text-sm text-slate-400">
            Your personal key overrides the shared backend key for your account only.
          </p>

          <div className="mt-5 space-y-4">
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-200" htmlFor="codex-label">
                Label
              </label>
              <input
                id="codex-label"
                value={label}
                onChange={(event) => setLabel(event.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none transition focus:border-blue-500/60"
                placeholder="Personal free plan"
              />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-200" htmlFor="codex-key">
                API key
              </label>
              <input
                id="codex-key"
                type="password"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none transition focus:border-blue-500/60"
                placeholder="Paste your Codex.io API key"
              />
            </div>
            <button
              type="button"
              disabled={saveMutation.isPending || apiKey.trim().length === 0}
              onClick={() => saveMutation.mutate()}
              className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-slate-700"
            >
              {saveMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}
              Save Codex.io key
            </button>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/45 p-5">
          <h3 className="text-lg font-semibold text-white">How this behaves in production</h3>
          <ul className="mt-4 space-y-3 text-sm text-slate-300">
            <li>All Codex.io requests are proxied through the backend so your key stays out of the browser.</li>
            <li>When your personal key exists, it overrides the shared backend fallback for your account.</li>
            <li>Market data stays cached and throttled server-side to respect the free-plan limits.</li>
          </ul>

          <button
            type="button"
            disabled={deleteMutation.isPending || !status?.user_key_available}
            onClick={() => deleteMutation.mutate()}
            className="mt-6 inline-flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm font-semibold text-red-200 transition hover:bg-red-500/20 disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-800 disabled:text-slate-500"
          >
            {deleteMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
            Remove personal key
          </button>
        </div>
      </div>
    </div>
  );
}
