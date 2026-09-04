import { BrainCircuit, ChevronDown, ChevronUp, Loader, RefreshCw, Sparkles } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import api, {
    type AIBacktestSummary,
    type AIMarketProvider,
    type AISuggestParamsRequest,
    toAIBacktestSummary,
} from '../api';
import { getAIProviderDisplayName, useAIProviderAvailability } from '../features/ai/providerAvailability';
import type { Strategy } from '../store/strategies';

interface Props {
  strategy: Strategy;
  lastError?: string;
  recentBacktests?: AIBacktestSummary[];
  defaultProvider?: AIMarketProvider;
  onApplyParams?: (
    params: Partial<Strategy>
  ) => Promise<Array<keyof Strategy> | void> | Array<keyof Strategy> | void;
}

interface ParsedSuggestion {
  key: keyof Strategy;
  value: number | string | boolean;
  raw: string;
}

interface PendingApplyPreview {
  items: ParsedSuggestion[];
  patch: Partial<Strategy>;
}

const suggestionCountOptions = [3, 5, 6, 8] as const;
const SUGGESTION_COUNT_PREFERENCE_KEY = 'ai-advisor-max-suggestions';

const loadPreferredSuggestionCount = (): number => {
  if (typeof window === 'undefined') {
    return 8;
  }

  const stored = Number(window.localStorage.getItem(SUGGESTION_COUNT_PREFERENCE_KEY));
  if (suggestionCountOptions.includes(stored as (typeof suggestionCountOptions)[number])) {
    return stored;
  }

  return 8;
};

export function AIStrategyAdvisor({
  strategy,
  lastError = '',
  recentBacktests = [],
  defaultProvider = 'deepseek',
  onApplyParams,
}: Props) {
  const [provider, setProvider] = useState<AIMarketProvider>(defaultProvider);
  const [loading, setLoading] = useState(false);
  const [content, setContent] = useState<string | null>(null);
  const [maxSuggestions, setMaxSuggestions] = useState<number>(loadPreferredSuggestionCount);
  const [usedAI, setUsedAI] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [applyLoading, setApplyLoading] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);
  const [pendingApplyPreview, setPendingApplyPreview] = useState<PendingApplyPreview | null>(null);
  const [appliedKeys, setAppliedKeys] = useState<Set<keyof Strategy>>(new Set());
  const {
    availableProviders,
    statusMap,
    isLoading: providerStatusLoading,
  } = useAIProviderAvailability();

  useEffect(() => {
    if (availableProviders.length === 0) {
      return;
    }

    if (!availableProviders.includes(provider)) {
      setProvider((availableProviders[0] ?? availableProviders[0]!));
    }
  }, [availableProviders, provider]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    window.localStorage.setItem(SUGGESTION_COUNT_PREFERENCE_KEY, String(maxSuggestions));
  }, [maxSuggestions]);

  useEffect(() => {
    if (!pendingApplyPreview) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        if (!applyLoading) {
          setPendingApplyPreview(null);
        }
        return;
      }

      if (event.key === 'Enter') {
        const target = event.target as HTMLElement | null;
        const tagName = target?.tagName?.toLowerCase();
        const isEditableTarget =
          tagName === 'input' ||
          tagName === 'textarea' ||
          tagName === 'select' ||
          target?.isContentEditable;

        if (!isEditableTarget && !applyLoading) {
          event.preventDefault();
          void confirmApplySuggestions();
        }
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [pendingApplyPreview, applyLoading]);

  const editableKeys = useMemo(
    () =>
      new Set<keyof Strategy>([
        'zscore_threshold',
        'stats_window',
        'max_half_life',
        'usd_per_trade',
        'usd_min_collateral',
        'max_positions',
        'max_drawdown_pct',
        'stop_loss_pct',
        'take_profit_pct',
        'trailing_stop_pct',
        'rebalance_interval_hours',
        'position_timeout_hours',
        'transaction_fee',
        'slippage',
        'max_history_days',
        'risk_free_rate',
        'resolution',
        'candle_resolution',
      ]),
    []
  );

  const normalizeSuggestionKey = (rawKey: string): keyof Strategy | null => {
    const normalized = rawKey
      .trim()
      .toLowerCase()
      .replace(/[\s-]+/g, '_');
    const aliasMap: Record<string, keyof Strategy> = {
      zscore: 'zscore_threshold',
      z_score_threshold: 'zscore_threshold',
      zscore_threshold: 'zscore_threshold',
      stats_window: 'stats_window',
      max_half_life: 'max_half_life',
      usd_per_trade: 'usd_per_trade',
      usd_min_collateral: 'usd_min_collateral',
      max_positions: 'max_positions',
      max_drawdown: 'max_drawdown_pct',
      max_drawdown_pct: 'max_drawdown_pct',
      stop_loss: 'stop_loss_pct',
      stop_loss_pct: 'stop_loss_pct',
      take_profit: 'take_profit_pct',
      take_profit_pct: 'take_profit_pct',
      trailing_stop: 'trailing_stop_pct',
      trailing_stop_pct: 'trailing_stop_pct',
      rebalance_interval: 'rebalance_interval_hours',
      rebalance_interval_hours: 'rebalance_interval_hours',
      position_timeout: 'position_timeout_hours',
      position_timeout_hours: 'position_timeout_hours',
      transaction_fee: 'transaction_fee',
      slippage: 'slippage',
      max_history_days: 'max_history_days',
      risk_free_rate: 'risk_free_rate',
      resolution: 'resolution',
      candle_resolution: 'candle_resolution',
    };
    const resolved = aliasMap[normalized] ?? (normalized as keyof Strategy);
    return editableKeys.has(resolved) ? resolved : null;
  };

  const parseSuggestedValue = (rawValue: string): number | string | boolean => {
    const cleaned = rawValue
      .trim()
      .replace(/[),.;]+$/, '')
      .replace(/^['"`]+|['"`]+$/g, '');
    if (/^(true|false)$/i.test(cleaned)) return cleaned.toLowerCase() === 'true';
    if (/%$/.test(cleaned)) {
      const n = Number.parseFloat(cleaned.replace('%', ''));
      return Number.isFinite(n) ? n : cleaned;
    }
    const num = Number.parseFloat(cleaned);
    if (Number.isFinite(num) && /^[-+]?\d*\.?\d+$/.test(cleaned)) return num;
    return cleaned;
  };

  const parsedSuggestions = useMemo<ParsedSuggestion[]>(() => {
    if (!content) return [];
    const lines = content
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean);

    const parsed: ParsedSuggestion[] = [];
    const seen = new Set<keyof Strategy>();

    for (const line of lines) {
      const keyMatch = line.match(/([a-zA-Z_][a-zA-Z0-9_ -]*)["'`*]*\s*[:-]/);
      const valueMatch = line.match(/suggested\s*([-+]?[^\s,;)]*%?)/i);
      if (!keyMatch || !valueMatch) continue;

      const key = normalizeSuggestionKey(keyMatch[1] ?? '');
      if (!key || seen.has(key)) continue;

      parsed.push({
        key,
        value: parseSuggestedValue(valueMatch[1] ?? ''),
        raw: line,
      });
      seen.add(key);
    }

    return parsed;
  }, [content]);

  const pendingSuggestions = useMemo(
    () => parsedSuggestions.filter((s) => !appliedKeys.has(s.key)),
    [parsedSuggestions, appliedKeys]
  );

  const applyAllSuggestions = async () => {
    if (!onApplyParams || pendingSuggestions.length === 0) return;
    const patch: Partial<Strategy> = {};
    pendingSuggestions.forEach((suggestion) => {
      patch[suggestion.key] = suggestion.value as never;
    });
    setPendingApplyPreview({
      items: pendingSuggestions,
      patch,
    });
  };

  const queueSingleSuggestion = (suggestion: ParsedSuggestion) => {
    const patch: Partial<Strategy> = {
      [suggestion.key]: suggestion.value,
    };
    setPendingApplyPreview({
      items: [suggestion],
      patch,
    });
  };

  const confirmApplySuggestions = async () => {
    if (!onApplyParams || !pendingApplyPreview) return;
    setApplyError(null);
    setApplyLoading(true);
    try {
      const applyResult = await onApplyParams(pendingApplyPreview.patch);
      const requestedKeys = pendingApplyPreview.items.map((i) => i.key);
      const acknowledgedKeys = Array.isArray(applyResult)
        ? applyResult.filter((key): key is keyof Strategy => requestedKeys.includes(key))
        : requestedKeys;

      if (acknowledgedKeys.length === 0) {
        throw new Error('No suggestions were applied to editable strategy fields.');
      }

      setAppliedKeys((prev) => {
        const next = new Set(prev);
        acknowledgedKeys.forEach((k) => next.add(k));
        return next;
      });
      setPendingApplyPreview(null);
    } catch (err) {
      setApplyError(err instanceof Error ? err.message : 'Failed to apply suggestions');
    } finally {
      setApplyLoading(false);
    }
  };

  const runSuggest = async () => {
    setLoading(true);
    setError(null);
    setContent(null);
    setCollapsed(false);
    setAppliedKeys(new Set());

    let hydratedRecentBacktests = recentBacktests;
    const strategyId = Number(strategy.id);
    if (hydratedRecentBacktests.length === 0 && Number.isFinite(strategyId) && strategyId > 0) {
      try {
        const response = await api.listBacktestsByStrategy(strategyId, 5);
        const items = Array.isArray(response.data?.backtests) ? response.data.backtests : [];
        hydratedRecentBacktests = items
          .map((b) => toAIBacktestSummary(b))
          .filter((summary): summary is AIBacktestSummary => summary !== null);
      } catch {
        hydratedRecentBacktests = recentBacktests;
      }
    }

    // Build a compact current-params map from known Strategy fields
    const currentParams: Record<string, unknown> = {
      category: strategy.category,
      runtime_strategy: strategy.runtime_strategy,
      runtime_network: strategy.runtime_network,
      runtime_subaccount: strategy.runtime_subaccount,
      pair_selection_mode: strategy.pair_selection_mode,
      selected_markets: strategy.selected_markets,
      zscore_threshold: strategy.zscore_threshold,
      stats_window: strategy.stats_window,
      max_half_life: strategy.max_half_life,
      usd_per_trade: strategy.usd_per_trade,
      usd_min_collateral: strategy.usd_min_collateral,
      max_positions: strategy.max_positions,
      max_drawdown_pct: strategy.max_drawdown_pct,
      stop_loss_pct: strategy.stop_loss_pct,
      take_profit_pct: strategy.take_profit_pct,
      trailing_stop_pct: strategy.trailing_stop_pct,
      rebalance_interval_hours: strategy.rebalance_interval_hours,
      position_timeout_hours: strategy.position_timeout_hours,
      transaction_fee: strategy.transaction_fee,
      slippage: strategy.slippage,
      max_history_days: strategy.max_history_days,
      risk_free_rate: strategy.risk_free_rate,
      resolution: strategy.resolution,
      candle_resolution: strategy.candle_resolution,
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
      recent_backtests: hydratedRecentBacktests,
      max_suggestions: maxSuggestions,
    };

    try {
      const resp = await api.suggestStrategyParams(req);
      const data = resp.data;
      if (!data) {
        throw new Error('AI suggestion response did not include content');
      }
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
              {getAIProviderDisplayName(statusMap[provider])}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2.5">
          <select
            value={maxSuggestions}
            onChange={(e) => setMaxSuggestions(Number(e.target.value))}
            disabled={loading}
            className="rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none disabled:opacity-50"
            title="How many AI suggestions to request"
          >
            {suggestionCountOptions.map((count) => (
              <option key={count} value={count}>
                {count} suggestions
              </option>
            ))}
          </select>

          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value as AIMarketProvider)}
            disabled={loading || providerStatusLoading || availableProviders.length === 0}
            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-200 focus:outline-none disabled:opacity-50"
          >
            {availableProviders.map((p, index) => (
              <option key={p} value={p}>
                {getAIProviderDisplayName(statusMap[p]) || `Provider ${index + 1}`}
              </option>
            ))}
          </select>

          <button
            onClick={runSuggest}
            disabled={loading || availableProviders.length === 0}
            className="flex min-h-9 items-center gap-1.5 rounded-lg bg-emerald-700 px-3.5 py-2 text-xs font-medium text-white transition hover:bg-emerald-600 disabled:opacity-50"
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
              aria-label={collapsed ? 'Expand AI parameter suggestions' : 'Collapse AI parameter suggestions'}
              className="rounded-md p-2 text-slate-400 hover:text-slate-200"
            >
              {collapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
            </button>
          )}
        </div>
      </div>

      {/* Idle hint */}
      {!content && !loading && !error && (
        <p className="mt-3 text-xs text-slate-500">
          Get up to {maxSuggestions} specific, numbered parameter adjustments for{' '}
          <span className="text-slate-300">{strategy.name}</span> based on its current config
          {recentBacktests.length > 0 ? ` and ${recentBacktests.length} recent backtest(s)` : ''}.
          You can apply all at once or one-by-one.
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
          <Loader className="h-4 w-4 animate-spin text-emerald-400" />
          Analysing strategy parameters…
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

          {parsedSuggestions.length > 0 && onApplyParams && (
            <div className="rounded-lg border border-emerald-700/40 bg-emerald-950/20 px-3 py-2">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs font-medium text-emerald-200">
                  {pendingSuggestions.length > 0
                    ? `${pendingSuggestions.length} suggestion${pendingSuggestions.length === 1 ? '' : 's'} pending`
                    : `All ${parsedSuggestions.length} suggestion${parsedSuggestions.length === 1 ? '' : 's'} applied ✓`}
                </p>
                <p className="text-[11px] text-emerald-300/80">
                  Apply all or use individual Apply buttons below.
                </p>
                {pendingSuggestions.length > 0 && (
                  <button
                    onClick={() => void applyAllSuggestions()}
                    disabled={applyLoading}
                    className="rounded-md border border-emerald-500/40 bg-emerald-600/20 px-3 py-1.5 text-[11px] font-semibold text-emerald-100 transition hover:bg-emerald-600/35 disabled:opacity-50"
                  >
                    Review & Apply All
                  </button>
                )}
              </div>
              <div className="space-y-2">
                {pendingSuggestions.map((item) => (
                  <div
                    key={item.key}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-emerald-700/40 bg-slate-900/60 px-3 py-2 text-[11px] text-emerald-100"
                  >
                    <span>
                      {String(item.key)} → {String(item.value)}
                    </span>
                    <button
                      onClick={() => queueSingleSuggestion(item)}
                      disabled={applyLoading}
                      className="min-h-8 rounded border border-emerald-500/40 bg-emerald-700/20 px-2.5 py-1 text-[10px] font-semibold text-emerald-100 transition hover:bg-emerald-700/35 disabled:opacity-50"
                    >
                      Apply
                    </button>
                  </div>
                ))}
              </div>
              {applyError && <p className="mt-2 text-xs text-red-300">{applyError}</p>}
            </div>
          )}

          {!usedAI && (
            <p className="text-xs text-slate-500">
              No AI key configured — add a provider key in Settings → AI Providers.
            </p>
          )}
        </div>
      )}

      {pendingApplyPreview &&
        typeof document !== 'undefined' &&
        createPortal(
          <div className="fixed inset-0 z-60 flex items-center justify-center bg-black/60 p-4">
            <div className="w-full max-w-xl rounded-2xl border border-emerald-700/40 bg-slate-900 shadow-2xl">
              <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
                <h3 className="text-sm font-semibold text-emerald-200">
                  Confirm AI parameter updates
                </h3>
                <button
                  onClick={() => setPendingApplyPreview(null)}
                  disabled={applyLoading}
                  className="rounded-md border border-slate-700 px-2.5 py-1.5 text-xs text-slate-300 transition hover:border-slate-500 hover:text-white disabled:opacity-50"
                >
                  Close
                </button>
              </div>

              <div className="space-y-2 px-5 py-4">
                {pendingApplyPreview.items.map((item) => (
                  <div
                    key={`preview-${item.key}`}
                    className="rounded-lg border border-slate-700 bg-slate-950/70 px-3 py-2"
                  >
                    <p className="text-[11px] uppercase tracking-wide text-slate-400">
                      {String(item.key)}
                    </p>
                    <p className="mt-1 text-xs text-slate-300">
                      <span className="text-slate-500">Current:</span>{' '}
                      {String(strategy[item.key] ?? '—')}
                    </p>
                    <p className="text-xs text-emerald-200">
                      <span className="text-emerald-400">Suggested:</span> {String(item.value)}
                    </p>
                  </div>
                ))}
                {applyError && <p className="text-xs text-red-300">{applyError}</p>}
              </div>

              <div className="flex flex-col items-stretch gap-2.5 border-t border-slate-800 px-5 py-4 sm:flex-row sm:items-center sm:justify-end sm:gap-3 sm:px-6 sm:py-5">
                <span className="rounded-full border border-emerald-700/40 bg-emerald-950/30 px-2.5 py-1 text-center text-[11px] font-semibold text-emerald-200 sm:mr-auto sm:text-left">
                  {pendingApplyPreview.items.length} field
                  {pendingApplyPreview.items.length === 1 ? '' : 's'} pending
                </span>
                <button
                  onClick={() => setPendingApplyPreview(null)}
                  disabled={applyLoading}
                  className="min-h-9 w-full rounded-lg border border-slate-700 px-4 py-2 text-xs text-slate-200 transition hover:border-slate-500 disabled:opacity-50 sm:w-auto"
                >
                  Cancel (Esc)
                </button>
                <button
                  onClick={() => void confirmApplySuggestions()}
                  disabled={applyLoading}
                  className="min-h-9 w-full rounded-lg border border-emerald-500/40 bg-emerald-600/20 px-4 py-2 text-xs font-semibold text-emerald-100 transition hover:bg-emerald-600/35 disabled:opacity-50 sm:w-auto"
                >
                  {applyLoading ? 'Applying...' : 'Confirm Apply (Enter)'}
                </button>
              </div>
            </div>
          </div>,
          document.body
        )}
    </div>
  );
}
