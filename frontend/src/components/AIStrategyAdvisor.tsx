import { BrainCircuit, ChevronDown, ChevronUp, Loader, RefreshCw, Sparkles } from 'lucide-react';
import { useState } from 'react';
import api, {
    type AIBacktestSummary,
    type AIMarketProvider,
    type AISuggestParamsRequest,
} from '../api';
import type { Strategy } from '../store/strategies';

interface Props {
  strategy: Strategy;
  lastError?: string;
  recentBacktests?: AIBacktestSummary[];
  defaultProvider?: AIMarketProvider;
}

const PROVIDERS: { value: AIMarketProvider; label: string }[] = [
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'claude', label: 'Claude' },
];

export function AIStrategyAdvisor({
  strategy,
  lastError = '',
  recentBacktests = [],
  defaultProvider = 'deepseek',
}: Props) {
  const [provider, setProvider] = useState<AIMarketProvider>(defaultProvider);
  const [loading, setLoading] = useState(false);
  const [content, setContent] = useState<string | null>(null);
  const [usedAI, setUsedAI] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);

  const runSuggest = async () => {
    setLoading(true);
    setError(null);
    setContent(null);
    setCollapsed(false);

    // Build a compact current-params map from known Strategy fields
    const currentParams: Record<string, unknown> = {
      zscore_threshold: strategy.zscore_threshold,
      usd_per_trade: strategy.usd_per_trade,
      max_half_life: strategy.max_half_life,
      min_half_life: strategy.min_half_life,
      stop_loss_pct: strategy.stop_loss_pct,
      take_profit_pct: strategy.take_profit_pct,
      leverage: strategy.leverage,
      candle_resolution: strategy.candle_resolution,
      market_1: strategy.market_1,
      market_2: strategy.market_2,
    };
    // Remove undefined
    Object.keys(currentParams).forEach(
      (k) => currentParams[k] === undefined && delete currentParams[k]
    );

    const req: AISuggestParamsRequest = {
      provider,
      strategy_name: strategy.name,
      current_params: currentParams,
      last_error: lastError,
      recent_backtests: recentBacktests,
    };

    try {
      const resp = await api.suggestStrategyParams(req);
      const data = resp?.data ?? (resp as unknown as typeof resp.data);
      setContent(data.content);
      setUsedAI(data.used_ai);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'AI suggestion failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-2xl border border-emerald-800/40 bg-emerald-950/15 p-4 sm:p-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <BrainCircuit className="h-4 w-4 text-emerald-400" />
          <span className="text-sm font-semibold text-emerald-200">AI Parameter Advisor</span>
          {content && usedAI && (
            <span className="rounded-full bg-emerald-900/60 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-emerald-300">
              {provider}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
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

          <button
            onClick={runSuggest}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-lg bg-emerald-700 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-emerald-600 disabled:opacity-50"
          >
            {loading ? (
              <Loader className="h-3.5 w-3.5 animate-spin" />
            ) : content ? (
              <RefreshCw className="h-3.5 w-3.5" />
            ) : (
              <Sparkles className="h-3.5 w-3.5" />
            )}
            {content ? 'Refresh' : 'Suggest Parameters'}
          </button>

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

      {/* Idle hint */}
      {!content && !loading && !error && (
        <p className="mt-3 text-xs text-slate-500">
          Get 3 specific, numbered parameter adjustments for{' '}
          <span className="text-slate-300">{strategy.name}</span> based on its current config
          {recentBacktests.length > 0 ? ` and ${recentBacktests.length} recent backtest(s)` : ''}.
        </p>
      )}

      {loading && (
        <div className="mt-4 flex items-center gap-3 text-sm text-slate-400">
          <Loader className="h-4 w-4 animate-spin text-emerald-400" />
          Analysing strategy with {PROVIDERS.find((p) => p.value === provider)?.label ?? provider}…
        </div>
      )}

      {error && (
        <div className="mt-3 rounded-lg border border-red-700/40 bg-red-950/30 px-3 py-2 text-xs text-red-300">
          {error}
        </div>
      )}

      {content && !collapsed && (
        <div className="mt-4 space-y-3">
          <p className="whitespace-pre-line text-sm leading-relaxed text-slate-300">{content}</p>
          {!usedAI && (
            <p className="text-xs text-slate-500">
              No AI key configured — add a provider key in Settings → AI Providers.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
