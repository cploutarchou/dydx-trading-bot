import { BrainCircuit, ChevronDown, ChevronUp, Loader, RefreshCw, Sparkles } from 'lucide-react';
import { useState } from 'react';
import api, { type AIBacktestExplainRequest, type AIMarketProvider } from '../api';

interface Props {
  winRate: number;
  totalPnlUsd: number;
  sharpeRatio: number;
  maxDrawdownPct: number;
  totalTrades: number;
  profitFactor: number;
  markets: string[];
  startDate: string;
  endDate: string;
  /** Default provider preference shown in selector */
  defaultProvider?: AIMarketProvider;
}

const PROVIDERS: { value: AIMarketProvider; label: string }[] = [
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'claude', label: 'Claude' },
];

export function AIBacktestExplainer({
  winRate,
  totalPnlUsd,
  sharpeRatio,
  maxDrawdownPct,
  totalTrades,
  profitFactor,
  markets,
  startDate,
  endDate,
  defaultProvider = 'deepseek',
}: Props) {
  const [provider, setProvider] = useState<AIMarketProvider>(defaultProvider);
  const [loading, setLoading] = useState(false);
  const [content, setContent] = useState<string | null>(null);
  const [usedAI, setUsedAI] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);

  const runExplain = async () => {
    setLoading(true);
    setError(null);
    setContent(null);
    setCollapsed(false);

    const req: AIBacktestExplainRequest = {
      provider,
      win_rate: winRate,
      total_pnl_usd: totalPnlUsd,
      sharpe_ratio: sharpeRatio,
      max_drawdown_pct: maxDrawdownPct,
      total_trades: totalTrades,
      profit_factor: profitFactor ?? 0,
      markets,
      start_date: startDate ?? '',
      end_date: endDate ?? '',
    };

    try {
      const resp = await api.explainBacktest(req);
      const data = resp?.data ?? (resp as unknown as typeof resp.data);
      setContent(data.content);
      setUsedAI(data.used_ai);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'AI explanation failed');
    } finally {
      setLoading(false);
    }
  };

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
          {content && usedAI && (
            <span className="rounded-full bg-violet-900/60 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-violet-300">
              {provider}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Provider selector */}
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value as AIMarketProvider)}
            disabled={loading}
            className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200 focus:outline-none disabled:opacity-50"
          >
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>

          {/* Explain / refresh button */}
          <button
            onClick={runExplain}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-lg bg-violet-700 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-violet-600 disabled:opacity-50"
          >
            {loading ? (
              <Loader className="h-3.5 w-3.5 animate-spin" />
            ) : content ? (
              <RefreshCw className="h-3.5 w-3.5" />
            ) : (
              <Sparkles className="h-3.5 w-3.5" />
            )}
            {content ? 'Regenerate' : 'Explain with AI'}
          </button>

          {/* Collapse toggle */}
          {content && (
            <button
              onClick={() => setCollapsed((v) => !v)}
              className="rounded p-1 text-slate-400 hover:text-slate-200"
            >
              {collapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
            </button>
          )}
        </div>
      </div>

      {/* Body */}
      {!content && !loading && !error && (
        <p className="mt-3 text-xs text-slate-500">
          Click <span className="text-violet-300">Explain with AI</span> to get a plain-language
          analysis of these backtest results plus 3 actionable improvements.
        </p>
      )}

      {loading && (
        <div className="mt-4 flex items-center gap-3 text-sm text-slate-400">
          <Loader className="h-4 w-4 animate-spin text-violet-400" />
          Analysing results with {PROVIDERS.find((p) => p.value === provider)?.label ?? provider}…
        </div>
      )}

      {error && (
        <div className="mt-3 rounded-lg border border-red-700/40 bg-red-950/30 px-3 py-2 text-xs text-red-300">
          {error}
        </div>
      )}

      {content && !collapsed && (
        <div className="mt-4 space-y-4">
          {/* Narrative */}
          {narrativePart && (
            <p className="text-sm leading-relaxed text-slate-300">{narrativePart}</p>
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

          {!usedAI && (
            <p className="text-xs text-slate-500">
              No AI key configured — add a provider key in Settings → AI Providers to enable live
              analysis.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
