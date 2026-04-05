import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import { KeyRound, Loader2, Newspaper, ShieldCheck, Trash2 } from 'lucide-react';
import { useState } from 'react';
import api from '../api';
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

export function CoinDeskNewsSettings() {
  const [apiKey, setApiKey] = useState('');
  const [label, setLabel] = useState('Shared newsroom key');
  const queryClient = useQueryClient();
  const successToast = useToastStore((state) => state.success);
  const errorToast = useToastStore((state) => state.error);

  const configQuery = useQuery({
    queryKey: ['news', 'coindesk', 'config'],
    queryFn: async () => {
      const response = await api.getCoinDeskNewsConfig();
      return response.data;
    },
    staleTime: 30_000,
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      const response = await api.saveCoinDeskNewsConfig({ api_key: apiKey, label });
      return response.data;
    },
    onSuccess: () => {
      setApiKey('');
      successToast('CoinDesk key saved', 'The shared newsroom configuration is active for all users.');
      void queryClient.invalidateQueries({ queryKey: ['news', 'coindesk'] });
    },
    onError: (error: unknown) => {
      errorToast('Failed to save CoinDesk key', getMutationErrorMessage(error));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      const response = await api.deleteCoinDeskNewsConfig();
      return response.data;
    },
    onSuccess: () => {
      successToast('CoinDesk key removed', 'The shared configuration has been cleared.');
      void queryClient.invalidateQueries({ queryKey: ['news', 'coindesk'] });
    },
    onError: (error: unknown) => {
      errorToast('Failed to delete CoinDesk key', getMutationErrorMessage(error));
    },
  });

  const config = configQuery.data;

  return (
    <div className="premium-panel">
      <div className="flex items-start gap-3">
        <div className="premium-icon-wrap text-cyan-300">
          <Newspaper className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-2xl font-semibold text-white">CoinDesk News</h2>
          <p className="mt-1 text-sm text-slate-400">
            Manage the shared backend credential for CoinDesk news. All authenticated users can read the feed, but only admins can configure it.
          </p>
        </div>
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-3">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="mb-2 flex items-center gap-2 text-slate-200">
            <ShieldCheck className="h-4 w-4 text-emerald-300" />
            Shared key
          </div>
          <p className="text-lg font-semibold text-white">
            {config?.shared_key_present ? 'Configured' : 'Not configured'}
          </p>
          <p className="mt-1 text-xs text-slate-500">Stored on the backend only.</p>
        </div>

        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="mb-2 flex items-center gap-2 text-slate-200">
            <Newspaper className="h-4 w-4 text-cyan-300" />
            Source
          </div>
          <p className="text-lg font-semibold text-white">{config?.source ?? 'coindesk_rss'}</p>
          <p className="mt-1 text-xs text-slate-500 break-all">{config?.feed_url}</p>
        </div>

        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
          <div className="mb-2 flex items-center gap-2 text-slate-200">
            <KeyRound className="h-4 w-4 text-amber-300" />
            Visibility
          </div>
          <p className="text-lg font-semibold text-white">Shared to all users</p>
          <p className="mt-1 text-xs text-slate-500">The frontend never handles the provider key directly.</p>
        </div>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.05fr,0.95fr]">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-5">
          <h3 className="text-lg font-semibold text-white">{config?.shared_key_present ? 'Update shared API key' : 'Save shared API key'}</h3>
          <div className="mt-5 space-y-4">
            {config?.shared_key_present && (
              <div className="rounded-xl border border-slate-700 bg-slate-950/60 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Current shared key</p>
                <p className="mt-2 font-mono text-sm text-slate-200">{config.shared_key_masked || 'Masked key on file'}</p>
                {config.shared_key_label && (
                  <p className="mt-1 text-xs text-slate-500">Label: {config.shared_key_label}</p>
                )}
              </div>
            )}
            <div>
              <label htmlFor="coindesk-key-label" className="mb-2 block text-sm font-medium text-slate-200">
                Label
              </label>
              <input
                id="coindesk-key-label"
                value={label}
                onChange={(event) => setLabel(event.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-500/60"
              />
            </div>
            <div>
              <label htmlFor="coindesk-key" className="mb-2 block text-sm font-medium text-slate-200">
                API key
              </label>
              <input
                id="coindesk-key"
                type="password"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-500/60"
                placeholder={config?.shared_key_present ? 'Paste a new CoinDesk API key to replace the current one' : 'Paste your CoinDesk API key'}
              />
            </div>
            <button
              type="button"
              disabled={saveMutation.isPending || apiKey.trim().length === 0}
              onClick={() => saveMutation.mutate()}
              className="inline-flex items-center gap-2 rounded-xl bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:bg-slate-700"
            >
              {saveMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}
              {config?.shared_key_present ? 'Update shared key' : 'Save shared key'}
            </button>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-5">
          <h3 className="text-lg font-semibold text-white">Operational notes</h3>
          <ul className="mt-4 space-y-3 text-sm text-slate-300">
            <li>All users read the same backend-served CoinDesk news feed.</li>
            <li>The shared key is optional for the current feed path but stored now so premium/private CoinDesk endpoints can be introduced without frontend changes.</li>
            <li>Feed responses are cached server-side to keep the UI fast and reduce unnecessary upstream traffic.</li>
          </ul>
          <button
            type="button"
            disabled={deleteMutation.isPending || !config?.shared_key_present}
            onClick={() => deleteMutation.mutate()}
            className="mt-6 inline-flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm font-semibold text-red-200 transition hover:bg-red-500/20 disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-800 disabled:text-slate-500"
          >
            {deleteMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
            Remove shared key
          </button>
        </div>
      </div>
    </div>
  );
}
