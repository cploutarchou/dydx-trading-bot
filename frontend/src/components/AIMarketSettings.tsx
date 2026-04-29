import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { BrainCircuit, KeyRound, Loader2, ShieldCheck, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import api, { type AIMarketProvider } from '../api';
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
    description: 'Cost-efficient OpenAI-compatible reasoning for market filters.',
  },
  {
    id: 'claude',
    label: 'Claude',
    description: 'Long-context market rationale and conservative ranking.',
  },
];

export function AIMarketSettings() {
  const [provider, setProvider] = useState<AIMarketProvider>('openai');
  const [apiKey, setApiKey] = useState('');
  const [label, setLabel] = useState('Personal AI market filter key');
  const queryClient = useQueryClient();
  const successToast = useToastStore((state) => state.success);
  const errorToast = useToastStore((state) => state.error);

  const statusQuery = useQuery({
    queryKey: ['ai-market-filters', 'status'],
    queryFn: async () => {
      const response = await api.getAIMarketStatus();
      return response.data;
    },
    staleTime: 30_000,
  });

  const selectedStatus = useMemo(
    () => statusQuery.data?.providers.find((item) => item.provider === provider),
    [provider, statusQuery.data?.providers]
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
      errorToast('Failed to remove AI key', error instanceof Error ? error.message : 'Unknown error');
    },
  });

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800 p-6 shadow">
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
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${
                    status?.enabled
                      ? 'bg-emerald-500/15 text-emerald-300'
                      : 'bg-slate-700/70 text-slate-400'
                  }`}
                >
                  {status?.enabled ? status.active_key_source : 'off'}
                </span>
              </div>
              <p className="mt-2 text-xs leading-5 text-slate-400">{item.description}</p>
              <p className="mt-3 text-[11px] text-slate-500">Model: {status?.model ?? 'default'}</p>
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
              Personal keys override shared backend environment keys for your account.
            </p>

            {selectedStatus?.user_key_available && (
              <div className="mt-4 rounded-xl border border-slate-700 bg-slate-950/60 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                  Current saved key
                </p>
                <p className="mt-2 font-mono text-sm text-slate-200">
                  {selectedStatus.user_key_masked || 'Masked key on file'}
                </p>
              </div>
            )}

            <div className="mt-5 space-y-4">
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-200" htmlFor="ai-key-label">
                  Label
                </label>
                <input
                  id="ai-key-label"
                  value={label}
                  onChange={(event) => setLabel(event.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-500/60"
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
                  className="w-full rounded-xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-500/60"
                  placeholder={`Paste your ${providerLabel(provider)} key`}
                />
              </div>
              <button
                type="button"
                disabled={saveMutation.isPending || apiKey.trim().length === 0}
                onClick={() => saveMutation.mutate()}
                className="inline-flex items-center gap-2 rounded-xl bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:bg-slate-700"
              >
                {saveMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <KeyRound className="h-4 w-4" />
                )}
                Save {providerLabel(provider)} key
              </button>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-700/60 bg-slate-900/45 p-5">
            <h3 className="text-lg font-semibold text-white">Runtime behavior</h3>
            <ul className="mt-4 space-y-3 text-sm text-slate-300">
              <li className="flex gap-2">
                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300" />
                dYdX market data is fetched by the backend before the AI provider ranks symbols.
              </li>
              <li>When no key is configured, market selection falls back to deterministic top markets.</li>
              <li>Shared env keys supported: OPENAI_API_KEY, DEEPSEEK_API_KEY, ANTHROPIC_API_KEY.</li>
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
