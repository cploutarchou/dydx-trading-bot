import { BrainCircuit, Loader, RefreshCw, Sparkles } from 'lucide-react';
import { useState } from 'react';
import api, { type AIMarketProvider, type AIRuntimeDigestRequest } from '../api';
import {
  getAIProviderDisplayName,
  useAIProviderAvailability,
} from '../features/ai/providerAvailability';

interface Props {
  runningBots: number;
  totalBots: number;
  openPositions: number;
  totalPnlUsd: number;
  activePairs: number;
  errorCount: number;
  network: string;
  defaultProvider?: AIMarketProvider;
}

export function AIRuntimeDigest({
  runningBots,
  totalBots,
  openPositions,
  totalPnlUsd,
  activePairs,
  errorCount,
  network,
  defaultProvider = 'deepseek',
}: Props) {
  const [provider, setProvider] = useState<AIMarketProvider>(defaultProvider);
  const [loading, setLoading] = useState(false);
  const [content, setContent] = useState<string | null>(null);
  const [usedAI, setUsedAI] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const {
    availableProviders,
    statusMap,
    isLoading: providerStatusLoading,
  } = useAIProviderAvailability();

  // The selection is only a preference: when it is not available (also on
  // the first render with a cached status), the first available provider is
  // used. Derived during render, so no effect and no stale request.
  const effectiveProvider: AIMarketProvider = availableProviders.includes(provider)
    ? provider
    : (availableProviders[0] ?? provider);

  const run = async () => {
    setLoading(true);
    setError(null);
    setContent(null);

    const req: AIRuntimeDigestRequest = {
      provider: effectiveProvider,
      running_bots: runningBots,
      total_bots: totalBots,
      open_positions: openPositions,
      total_pnl_usd: totalPnlUsd,
      active_pairs: activePairs,
      error_count: errorCount,
      network,
    };

    try {
      const resp = await api.getRuntimeDigest(req);
      const data = resp.data;
      if (!data) {
        throw new Error('AI digest response did not include content');
      }
      setContent(data.content);
      setUsedAI(data.used_ai);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'AI digest failed');
    } finally {
      setLoading(false);
    }
  };

  // Determine verdict tone from content keywords
  const tone = content
    ? /caution|warn|error|degraded|risk|issue/i.test(content)
      ? 'warning'
      : /healthy|nominal|stable|good|strong/i.test(content)
        ? 'healthy'
        : 'neutral'
    : 'neutral';

  const borderColor =
    tone === 'healthy'
      ? 'border-cyan-800/40'
      : tone === 'warning'
        ? 'border-amber-700/40'
        : 'border-slate-700/50';
  const bgColor =
    tone === 'healthy'
      ? 'bg-cyan-950/15'
      : tone === 'warning'
        ? 'bg-amber-950/15'
        : 'bg-slate-900/40';

  return (
    <div className={`rounded-2xl border ${borderColor} ${bgColor} p-4 sm:p-5`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <BrainCircuit className="h-4 w-4 text-cyan-400" />
          <span className="text-sm font-semibold text-cyan-200">AI Runtime Digest</span>
          {content && usedAI && (
            <span className="rounded-full bg-cyan-900/60 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-cyan-300">
              {getAIProviderDisplayName(statusMap[effectiveProvider])}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <select
            value={effectiveProvider}
            onChange={(e) => setProvider(e.target.value as AIMarketProvider)}
            disabled={loading || providerStatusLoading || availableProviders.length === 0}
            aria-label="AI provider for runtime digest"
            className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200 focus:outline-none disabled:opacity-50"
          >
            {availableProviders.map((p) => (
              <option key={p} value={p}>
                {getAIProviderDisplayName(statusMap[p])}
              </option>
            ))}
          </select>

          <button
            onClick={run}
            disabled={loading || availableProviders.length === 0}
            className="flex items-center gap-1.5 rounded-lg bg-cyan-700 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-cyan-600 disabled:opacity-50"
          >
            {loading ? (
              <Loader className="h-3.5 w-3.5 animate-spin" />
            ) : content ? (
              <RefreshCw className="h-3.5 w-3.5" />
            ) : (
              <Sparkles className="h-3.5 w-3.5" />
            )}
            {content ? 'Refresh' : 'Get Digest'}
          </button>
        </div>
      </div>

      {!content && !loading && !error && (
        <p className="mt-3 text-xs text-slate-500">
          Get a 2-sentence AI health verdict and recommended action for the current{' '}
          <span className="text-slate-300">{network}</span> runtime state.
        </p>
      )}

      {!providerStatusLoading && availableProviders.length === 0 && (
        <div className="mt-3 rounded-lg border border-amber-700/40 bg-amber-950/30 px-3 py-2 text-xs text-amber-200">
          Assistant features are unavailable for this account right now. Ask an admin to enable at
          least one AI provider in Settings.
        </div>
      )}

      {loading && (
        <div className="mt-4 flex items-center gap-3 text-sm text-slate-400">
          <Loader className="h-4 w-4 animate-spin text-cyan-400" />
          Generating runtime digest…
        </div>
      )}

      {error && (
        <div className="mt-3 rounded-lg border border-red-700/40 bg-red-950/30 px-3 py-2 text-xs text-red-300">
          {error}
        </div>
      )}

      {content && (
        <div className="mt-3">
          <p className="text-sm leading-relaxed text-slate-200">{content}</p>
          {!usedAI && (
            <p className="mt-2 text-xs text-slate-500">
              No AI key configured — an admin can add a provider key in Settings → AI Filters.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
