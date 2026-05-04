import { useMutation, useQueryClient } from '@tanstack/react-query';
import { BrainCircuit, KeyRound, Loader2, ShieldCheck, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import api, { type AIMarketProvider } from '../api';
import {
    getAIProviderLabel,
    getAvailabilityBadge,
    useAIProviderAvailability,
} from '../features/ai/providerAvailability';
import { useAuthStore } from '../store/auth';
import { useToastStore } from './ErrorBoundary';

const providers: Array<{ id: AIMarketProvider; label: string; description: string }> = [
  {
    id: 'openai',
    label: 'OpenAI',
    description: 'General-purpose market reasoning and strategy-aware ranking.',
  },
  {
    id: 'deepseek',
    label: 'DeepSeek',
    description: 'DeepSeek V4 market ranking with cost-efficient flash routing by default.',
  },
  {
    id: 'claude',
    label: 'Claude',
    description: 'Long-context market rationale and conservative ranking.',
  },
];

export function AIMarketSettings() {
  const user = useAuthStore((state) => state.user);
  const isAdmin = Boolean(user?.is_admin);
  const [provider, setProvider] = useState<AIMarketProvider>('deepseek');
  const [apiKey, setApiKey] = useState('');
  const [label, setLabel] = useState('Personal AI market filter key');
  const [sharedApiKey, setSharedApiKey] = useState('');
  const [sharedLabel, setSharedLabel] = useState('Shared AI market key');
  const queryClient = useQueryClient();
  const successToast = useToastStore((state) => state.success);
  const errorToast = useToastStore((state) => state.error);

  const statusQuery = useAIProviderAvailability();

  const selectedStatus = useMemo(
    () => statusQuery.providerStatuses.find((item) => item.provider === provider),
    [provider, statusQuery.providerStatuses]
  );

  const saveMutation = useMutation({
    mutationFn: async () => {
      const response = await api.saveAIMarketKey({ provider, api_key: apiKey, label });
      return response.data;
    },
    onSuccess: () => {
      setApiKey('');
      successToast('AI key saved', `${providerLabel(provider)} is ready for market selection.`);
      void queryClient.invalidateQueries({ queryKey: ['ai-market-filters'] });
    },
    onError: (error: unknown) => {
      errorToast('Failed to save AI key', error instanceof Error ? error.message : 'Unknown error');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      const response = await api.deleteAIMarketKey(provider);
      return response.data;
    },
    onSuccess: () => {
      successToast('AI key removed', `${providerLabel(provider)} personal key was removed.`);
      void queryClient.invalidateQueries({ queryKey: ['ai-market-filters'] });
    },
    onError: (error: unknown) => {
      errorToast(
        'Failed to remove AI key',
        error instanceof Error ? error.message : 'Unknown error'
      );
    },
  });

  const saveSharedMutation = useMutation({
    mutationFn: async () => {
      const response = await api.saveAIMarketSharedKey({
        provider,
        api_key: sharedApiKey,
        label: sharedLabel,
      });
      return response.data;
    },
    onSuccess: () => {
      setSharedApiKey('');
      successToast(
        'Shared AI key saved',
        `${getAIProviderLabel(provider)} is now globally available.`
      );
      void queryClient.invalidateQueries({ queryKey: ['ai-market-filters'] });
    },
    onError: (error: unknown) => {
      errorToast(
        'Failed to save shared AI key',
        error instanceof Error ? error.message : 'Unknown error'
      );
    },
  });

  const deleteSharedMutation = useMutation({
    mutationFn: async () => {
      const response = await api.deleteAIMarketSharedKey(provider);
      return response.data;
    },
    onSuccess: () => {
      successToast(
        'Shared AI key removed',
        `${getAIProviderLabel(provider)} shared key was removed.`
      );
      void queryClient.invalidateQueries({ queryKey: ['ai-market-filters'] });
    },
    onError: (error: unknown) => {
      errorToast(
        'Failed to remove shared AI key',
        error instanceof Error ? error.message : 'Unknown error'
      );
    },
  });

  return (
    <div className="premium-panel p-6">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">AI Market Filters</h2>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">
            Enable AI-assisted dYdX pair discovery for strategy setup. Requests stay backend-proxied
            so provider keys never leave the API service.
          </p>
        </div>
        <div className="inline-flex items-center gap-2 rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-cyan-300">
          <BrainCircuit className="h-3.5 w-3.5" />
          Optional
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        {providers.map((item) => {
          const status = statusQuery.data?.providers.find((entry) => entry.provider === item.id);
          const active = provider === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setProvider(item.id)}
              className={`rounded-xl border p-4 text-left transition ${
                active
                  ? 'border-cyan-500/50 bg-cyan-500/10'
                  : 'border-slate-700 bg-slate-900/45 hover:border-slate-600'
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-white">{item.label}</p>
                {(() => {
                  const badge = getAvailabilityBadge(status);
                  return (
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${
                        badge.tone === 'success'
                          ? 'bg-emerald-500/15 text-emerald-300'
                          : badge.tone === 'warning'
                            ? 'bg-amber-500/15 text-amber-300'
                            : 'bg-slate-700/70 text-slate-400'
                      }`}
                    >
                      {badge.label}
                    </span>
                  );
                })()}
              </div>
              <p className="mt-2 text-xs leading-5 text-slate-400">{item.description}</p>
              <p className="mt-3 text-[11px] text-slate-500">Model: {status?.model ?? 'default'}</p>
              {status?.unavailable_reason && (
                <p className="mt-2 text-[11px] text-amber-300">{status.unavailable_reason}</p>
              )}
            </button>
          );
        })}
      </div>

      {statusQuery.isLoading ? (
        <div className="mt-5 flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-900/50 px-4 py-3 text-sm text-slate-300">
          <Loader2 className="h-4 w-4 animate-spin" />
          Checking AI provider availability...
        </div>
      ) : (
        <div className="mt-6 grid gap-6 xl:grid-cols-[1.1fr,0.9fr]">
          <div className="rounded-2xl border border-slate-700/60 bg-slate-900/45 p-5">
            <h3 className="text-lg font-semibold text-white">
              {selectedStatus?.user_key_available ? 'Update personal key' : 'Save personal key'}
            </h3>
            <p className="mt-1 text-sm text-slate-400">
              Personal keys override shared backend keys for your account.
            </p>

            {selectedStatus?.user_key_available && (
              <div className="mt-4 rounded-xl border border-slate-700 bg-slate-950/60 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                  Current saved key
                </p>
                <p className="mt-2 max-w-full overflow-hidden break-all whitespace-normal font-mono text-sm text-slate-200">
                  {selectedStatus.user_key_masked || 'Masked key on file'}
                </p>
              </div>
            )}

            <div className="mt-5 space-y-4">
              <div>
                <label
                  className="mb-2 block text-sm font-medium text-slate-200"
                  htmlFor="ai-key-label"
                >
                  Label
                </label>
                <input
                  id="ai-key-label"
                  value={label}
                  onChange={(event) => setLabel(event.target.value)}
                  className="premium-input"
                  placeholder="Personal AI market filter key"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-200" htmlFor="ai-key">
                  API key or token
                </label>
                <input
                  id="ai-key"
                  type="password"
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  className="premium-input"
                  placeholder={`Paste your ${providerLabel(provider)} key`}
                />
              </div>
              <button
                type="button"
                disabled={saveMutation.isPending || apiKey.trim().length === 0}
                onClick={() => saveMutation.mutate()}
                className="inline-flex items-center gap-2 rounded-xl bg-cyan-500 px-4 py-2.5 text-sm font-semibold text-slate-900 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-300"
              >
                {saveMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <KeyRound className="h-4 w-4" />
                )}
                Save {providerLabel(provider)} key
              </button>
            </div>

            {isAdmin && (
              <div className="mt-6 rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <h4 className="text-sm font-semibold text-cyan-200">Shared key (admin only)</h4>
                  <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-cyan-300">
                    Admin only
                  </span>
                </div>
                <p className="text-xs text-slate-400">
                  Shared keys are available to all authenticated users unless a user has a personal
                  override.
                </p>
                <div className="mt-3 space-y-3">
                  <input
                    className="premium-input"
                    onChange={(event) => setSharedLabel(event.target.value)}
                    placeholder="Shared AI market key"
                  />
                  <input
                    type="password"
                    className="premium-input"
                    onChange={(event) => setSharedApiKey(event.target.value)}
                    placeholder={`Paste shared ${providerLabel(provider)} key`}
                  />
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={saveSharedMutation.isPending || sharedApiKey.trim().length === 0}
                      onClick={() => saveSharedMutation.mutate()}
                      className="inline-flex items-center gap-2 rounded-xl bg-cyan-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-cyan-600 disabled:cursor-not-allowed disabled:bg-slate-700"
                    >
                      {saveSharedMutation.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <KeyRound className="h-4 w-4" />
                      )}
                      Save shared key
                    </button>

                    <button
                      type="button"
                      disabled={
                        deleteSharedMutation.isPending || !selectedStatus?.shared_key_available
                      }
                      onClick={() => deleteSharedMutation.mutate()}
                      className="inline-flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm font-semibold text-red-200 transition hover:bg-red-500/20 disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-800 disabled:text-slate-500"
                    >
                      {deleteSharedMutation.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4" />
                      )}
                      Remove shared key
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-slate-700/60 bg-slate-900/45 p-5">
            <h3 className="text-lg font-semibold text-white">Runtime behavior</h3>
            <ul className="mt-4 space-y-3 text-sm text-slate-300">
              <li className="flex gap-2">
                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300" />
                dYdX market data is fetched by the backend before the AI provider ranks symbols.
              </li>
              <li>Unavailable providers are blocked at API level (disabled or not configured).</li>
              {!isAdmin && <li>Shared provider key management is admin only.</li>}
              <li>
                Shared env keys supported: OPENAI_API_KEY, DEEPSEEK_API_KEY, ANTHROPIC_API_KEY.
              </li>
            </ul>

            <button
              type="button"
              disabled={deleteMutation.isPending || !selectedStatus?.user_key_available}
              onClick={() => deleteMutation.mutate()}
              className="mt-6 inline-flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm font-semibold text-red-200 transition hover:bg-red-500/20 disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-800 disabled:text-slate-500"
            >
              {deleteMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4" />
              )}
              Remove personal key
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function providerLabel(provider: AIMarketProvider): string {
  switch (provider) {
    case 'deepseek':
      return 'DeepSeek';
    case 'claude':
      return 'Claude';
    default:
      return 'OpenAI';
  }
}
