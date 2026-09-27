import { BrainCircuit, ChevronDown, ChevronUp, Loader, RefreshCw, Sparkles } from 'lucide-react';
import { useState } from 'react';
import api, {
  type AIBacktestExplainRequest,
  type AIBacktestExplainResponse,
  type AIMarketProvider,
} from '../api';
import { EvidenceSummaryChips } from '../features/ai/evidenceSummary';
import {
  getAIProviderDisplayName,
  getAIProviderLabel,
  useAIProviderAvailability,
} from '../features/ai/providerAvailability';

interface Props {
  /** The backtest run to explain; the server builds the evidence from its stored results. */
  runId: string;
  /** Default provider preference shown in selector */
  defaultProvider?: AIMarketProvider;
}

export function AIBacktestExplainer({ runId, defaultProvider = 'deepseek' }: Props) {
  const [provider, setProvider] = useState<AIMarketProvider>(defaultProvider);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AIBacktestExplainResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const {
    availableProviders,
    unavailableProviders,
    statusMap,
    isLoading: providerStatusLoading,
  } = useAIProviderAvailability();

  // Repair an unavailable provider selection when the availability list
  // changes — adjusted during render instead of a cascading effect render.
  const [prevAvailableProviders, setPrevAvailableProviders] = useState(availableProviders);
  if (availableProviders !== prevAvailableProviders) {
    setPrevAvailableProviders(availableProviders);
    const firstProvider = availableProviders[0];
    if (availableProviders.length > 0 && !availableProviders.includes(provider) && firstProvider) {
      setProvider(firstProvider);
    }
  }

  const hasRun = runId.trim().length > 0;

  const runExplain = async () => {
    if (!hasRun) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setCollapsed(false);

    const req: AIBacktestExplainRequest = {
      provider,
      run_id: runId,
    };

    try {
      const resp = await api.explainBacktest(req);
      const data = resp.data;
      if (!data || typeof data.content !== 'string') {
        throw new Error('AI explanation response did not include content');
      }
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'AI explanation failed');
    } finally {
      setLoading(false);
    }
  };

  const content = result?.content ?? null;
  const usedAI = result?.used_ai === true;
  const providerNotConfigured = statusMap[provider]?.availability_status === 'not_configured';

  // Split into narrative + improvements if the AI used the "Improvements:" separator
  const narrativePart = content?.split(/\nImprovements:/i)[0]?.trim() ?? '';
  const improvementsPart = content?.includes('Improvements:')
    ? content.split(/\nImprovements:/i)[1]?.trim()
    : null;

  return (
    <div className="rounded-2xl border border-violet-800/40 bg-violet-950/20 p-4 sm:p-5">
      {/* Header row */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <BrainCircuit className="h-4 w-4 text-violet-400" />
          <span className="text-sm font-semibold text-violet-200">AI Backtest Explainer</span>
          {result && usedAI && (
            <span className="rounded-full bg-violet-900/60 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-violet-300">
              {result.model
                ? `${getAIProviderLabel(result.provider) || result.provider} (${result.model})`
                : getAIProviderDisplayName(statusMap[result.provider] ?? statusMap[provider])}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Provider selector */}
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value as AIMarketProvider)}
            disabled={loading || providerStatusLoading || availableProviders.length === 0}
            aria-label="AI provider for backtest explanation"
            className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200 focus:outline-none disabled:opacity-50"
          >
            {availableProviders.map((p) => (
              <option key={p} value={p}>
                {getAIProviderDisplayName(statusMap[p])}
              </option>
            ))}
          </select>

          {/* Explain / refresh button */}
          <button
            onClick={runExplain}
            disabled={loading || availableProviders.length === 0 || !hasRun}
            className="flex items-center gap-1.5 rounded-lg bg-violet-700 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-violet-600 disabled:opacity-50"
          >
            {loading ? (
              <Loader className="h-3.5 w-3.5 animate-spin" />
            ) : result ? (
              <RefreshCw className="h-3.5 w-3.5" />
            ) : (
              <Sparkles className="h-3.5 w-3.5" />
            )}
            {result ? 'Regenerate' : 'Explain with AI'}
          </button>

          {/* Collapse toggle */}
          {result && (
            <button
              onClick={() => setCollapsed((v) => !v)}
              aria-label={
                collapsed ? 'Expand AI backtest explanation' : 'Collapse AI backtest explanation'
              }
              className="rounded p-1 text-slate-400 hover:text-slate-200"
            >
              {collapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
            </button>
          )}
        </div>
      </div>

      {/* Body */}
      {!result && !loading && !error && (
        <p className="mt-3 text-xs text-slate-500">
          Click <span className="text-violet-300">Explain with AI</span> to get a plain-language
          reading of this run&apos;s stored trades and metrics plus 3 actionable improvements.
        </p>
      )}

      {!providerStatusLoading && availableProviders.length === 0 && (
        <div className="mt-3 rounded-lg border border-amber-700/40 bg-amber-950/30 px-3 py-2 text-xs text-amber-200">
          No AI providers are currently available for your account.{' '}
          {unavailableProviders
            .map(
              (item) =>
                `${getAIProviderLabel(item)}: ${statusMap[item]?.unavailable_reason || 'Not configured'}`
            )
            .join(' · ')}
        </div>
      )}

      {loading && (
        <div className="mt-4 flex items-center gap-3 text-sm text-slate-400">
          <Loader className="h-4 w-4 animate-spin text-violet-400" />
          Analysing this run with {getAIProviderLabel(provider)}… This can take a couple of minutes.
        </div>
      )}

      {error && (
        <div className="mt-3 rounded-lg border border-red-700/40 bg-red-950/30 px-3 py-2 text-xs text-red-300">
          {error}
        </div>
      )}

      {result && !collapsed && (
        <div className="mt-4 space-y-4">
          <EvidenceSummaryChips summary={result.evidence_summary ?? null} showNotes />

          {/* Narrative */}
          {narrativePart && (
            <p className="whitespace-pre-line text-sm leading-relaxed text-slate-300">
              {narrativePart}
            </p>
          )}

          {/* Improvements */}
          {improvementsPart && (
            <div className="rounded-xl border border-violet-800/30 bg-violet-950/30 p-3">
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-violet-400">
                Suggested Improvements
              </p>
              <p className="whitespace-pre-line text-xs text-slate-300">{improvementsPart}</p>
            </div>
          )}

          {!usedAI && providerNotConfigured && (
            <p className="text-xs text-slate-500">
              No key is configured for {getAIProviderLabel(provider)} — add one in Settings → AI
              Filters to enable live analysis.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
