import { BrainCircuit, ChevronDown, ChevronUp, Loader, RefreshCw, Sparkles } from 'lucide-react';
import { useEffect, useMemo, useState, useCallback } from 'react';
import { createPortal } from 'react-dom';
import api, {
  type AIMarketProvider,
  type AIParamSuggestion,
  type AISuggestParamsRequest,
  type AISuggestParamsResponse,
} from '../api';
import {
  AISuggestionRiskBadges,
  EvidenceSummaryChips,
  formatAIParamValue,
} from '../features/ai/evidenceSummary';
import {
  getAIProviderDisplayName,
  getAIProviderLabel,
  useAIProviderAvailability,
} from '../features/ai/providerAvailability';
import type { Strategy } from '../store/strategies';

interface Props {
  strategy: Strategy;
  defaultProvider?: AIMarketProvider;
  onApplyParams?: (
    params: Partial<Strategy>
  ) => Promise<Array<keyof Strategy> | void> | Array<keyof Strategy> | void;
}

type SuggestionValue = number | string | boolean;

interface ParsedSuggestion {
  key: keyof Strategy;
  value: SuggestionValue;
  label: string;
  unit: string;
  /** Read by the server from the strategy; undefined for regex-parsed lines. */
  current?: SuggestionValue | null;
  rationale: string;
  evidence: string;
  risk?: AIParamSuggestion['risk'];
  backtestOnly?: boolean;
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

function normalizeSuggestionKey(
  rawKey: string,
  editableKeys: ReadonlySet<keyof Strategy>
): keyof Strategy | null {
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
    close_at_zscore_cross: 'close_at_zscore_cross',
  };
  const resolved = aliasMap[normalized] ?? (normalized as keyof Strategy);
  return editableKeys.has(resolved) ? resolved : null;
}

const isSuggestionValue = (value: unknown): value is SuggestionValue =>
  (typeof value === 'number' && Number.isFinite(value)) ||
  typeof value === 'string' ||
  typeof value === 'boolean';

export function AIStrategyAdvisor({
  strategy,
  defaultProvider = 'deepseek',
  onApplyParams,
}: Props) {
  const [selectedProvider, setSelectedProvider] = useState<AIMarketProvider>(defaultProvider);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AISuggestParamsResponse | null>(null);
  const [maxSuggestions, setMaxSuggestions] = useState<number>(loadPreferredSuggestionCount);
  const [error, setError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [applyLoading, setApplyLoading] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);
  const [pendingApplyPreview, setPendingApplyPreview] = useState<PendingApplyPreview | null>(null);
  const [appliedKeys, setAppliedKeys] = useState<Set<keyof Strategy>>(new Set());
  // Keys the parent did not apply: this page has no field for them.
  const [unavailableKeys, setUnavailableKeys] = useState<Set<keyof Strategy>>(new Set());
  const {
    availableProviders,
    statusMap,
    isLoading: providerStatusLoading,
  } = useAIProviderAvailability();

  // An unavailable selection (the default before the status is known, or a
  // key removed since) falls back to the first available provider. Derived at
  // render, so it also holds when the status is already cached on mount.
  const fallbackProvider = availableProviders[0];
  const provider =
    fallbackProvider !== undefined && !availableProviders.includes(selectedProvider)
      ? fallbackProvider
      : selectedProvider;

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    window.localStorage.setItem(SUGGESTION_COUNT_PREFERENCE_KEY, String(maxSuggestions));
  }, [maxSuggestions]);

  const confirmApplySuggestions = useCallback(async () => {
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

      // Keys the parent left out have no field on this page: they leave the
      // pending list marked as such instead of waiting for another apply.
      const unacknowledgedKeys = requestedKeys.filter((key) => !acknowledgedKeys.includes(key));

      setAppliedKeys((prev) => {
        const next = new Set(prev);
        acknowledgedKeys.forEach((k) => next.add(k));
        return next;
      });
      if (unacknowledgedKeys.length > 0) {
        setUnavailableKeys((prev) => {
          const next = new Set(prev);
          unacknowledgedKeys.forEach((k) => next.add(k));
          return next;
        });
      }
      setPendingApplyPreview(null);
    } catch (err) {
      setApplyError(err instanceof Error ? err.message : 'Failed to apply suggestions');
    } finally {
      setApplyLoading(false);
    }
  }, [onApplyParams, pendingApplyPreview]);

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
  }, [pendingApplyPreview, applyLoading, confirmApplySuggestions]);

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
        'close_at_zscore_cross',
      ]),
    []
  );

  const parseSuggestedValue = (rawValue: string): SuggestionValue => {
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

  // Typed suggestions from the server; null when the response has none.
  const structuredSuggestions = useMemo<AIParamSuggestion[] | null>(
    () => (result && Array.isArray(result.suggestions) ? result.suggestions : null),
    [result]
  );

  const parsedSuggestions = useMemo<ParsedSuggestion[]>(() => {
    if (!result) return [];
    const parsed: ParsedSuggestion[] = [];
    const seen = new Set<keyof Strategy>();

    if (structuredSuggestions) {
      for (const suggestion of structuredSuggestions) {
        const key = normalizeSuggestionKey(String(suggestion.parameter ?? ''), editableKeys);
        if (!key || seen.has(key) || !isSuggestionValue(suggestion.suggested)) continue;
        parsed.push({
          key,
          value: suggestion.suggested,
          label: typeof suggestion.label === 'string' ? suggestion.label : '',
          unit: typeof suggestion.unit === 'string' ? suggestion.unit : '',
          current: isSuggestionValue(suggestion.current) ? suggestion.current : null,
          rationale: typeof suggestion.rationale === 'string' ? suggestion.rationale : '',
          evidence: typeof suggestion.evidence === 'string' ? suggestion.evidence : '',
          risk: suggestion.risk,
          backtestOnly: suggestion.backtest_only === true,
        });
        seen.add(key);
      }
      return parsed;
    }

    // Fallback for a reply without structured suggestions: read the numbered
    // "key: Current 'x' -> Suggested 'y'" lines.
    const lines = (result.content ?? '')
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean);

    for (const line of lines) {
      const keyMatch = line.match(/([a-zA-Z_][a-zA-Z0-9_ -]*)["'`*]*\s*[:-]/);
      const valueMatch = line.match(/suggested\s*([-+]?[^\s,;)]*%?)/i);
      if (!keyMatch || !valueMatch) continue;

      const key = normalizeSuggestionKey(keyMatch[1] ?? '', editableKeys);
      if (!key || seen.has(key)) continue;

      parsed.push({
        key,
        value: parseSuggestedValue(valueMatch[1] ?? ''),
        label: '',
        unit: '',
        rationale: '',
        evidence: '',
      });
      seen.add(key);
    }

    return parsed;
  }, [result, structuredSuggestions, editableKeys]);

  // Rows still listed: everything not applied, including the keys this page
  // cannot edit (they show a note in place of their Apply button).
  const openSuggestions = useMemo(
    () => parsedSuggestions.filter((s) => !appliedKeys.has(s.key)),
    [parsedSuggestions, appliedKeys]
  );
  const pendingSuggestions = useMemo(
    () => openSuggestions.filter((s) => !unavailableKeys.has(s.key)),
    [openSuggestions, unavailableKeys]
  );
  const unavailableCount = openSuggestions.length - pendingSuggestions.length;

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

  const strategyId = Number(strategy.id);
  // The evidence is built server-side from the saved strategy, so an unsaved
  // draft (StrategyBuilder create mode) has nothing to analyse yet.
  const isSavedStrategy = Number.isFinite(strategyId) && strategyId > 0;

  const runSuggest = async () => {
    if (!isSavedStrategy) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setCollapsed(false);
    setAppliedKeys(new Set());
    setUnavailableKeys(new Set());

    const req: AISuggestParamsRequest = {
      provider,
      strategy_id: strategyId,
      max_suggestions: maxSuggestions,
    };

    try {
      const resp = await api.suggestStrategyParams(req);
      const data = resp.data;
      if (!data || typeof data.content !== 'string') {
        throw new Error('AI suggestion response did not include content');
      }
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'AI suggestion failed');
    } finally {
      setLoading(false);
    }
  };

  const usedAI = result?.used_ai === true;
  const evidenceSummary = result?.evidence_summary ?? null;
  const dataGaps = Array.isArray(result?.data_gaps)
    ? result.data_gaps.filter((gap): gap is string => typeof gap === 'string' && gap.trim() !== '')
    : [];
  const dropped = Array.isArray(result?.dropped)
    ? result.dropped.filter((item) => item && typeof item === 'object')
    : [];
  const summaryText = typeof result?.summary === 'string' ? result.summary.trim() : '';
  // The rendered lines repeat the structured rows, so show them only when
  // there are no rows to show (regex fallback, unavailable analysis).
  const showContent = !structuredSuggestions || parsedSuggestions.length === 0;
  const providerNotConfigured = statusMap[provider]?.availability_status === 'not_configured';
  const displayLabel = (item: ParsedSuggestion) => item.label || String(item.key);
  const currentValueFor = (item: ParsedSuggestion): unknown =>
    item.current !== undefined && item.current !== null ? item.current : strategy[item.key];

  return (
    <div className="rounded-2xl border border-emerald-800/40 bg-emerald-950/15 p-4 sm:p-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <BrainCircuit className="h-4 w-4 text-emerald-400" />
          <span className="text-sm font-semibold text-emerald-200">AI Parameter Advisor</span>
          {result && usedAI && (
            <span className="rounded-full bg-emerald-900/60 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-emerald-300">
              {result.model
                ? `${getAIProviderLabel(result.provider) || result.provider} (${result.model})`
                : getAIProviderDisplayName(statusMap[result.provider] ?? statusMap[provider])}
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
            aria-label="How many AI suggestions to request"
          >
            {suggestionCountOptions.map((count) => (
              <option key={count} value={count}>
                {count} suggestions
              </option>
            ))}
          </select>

          <select
            value={provider}
            onChange={(e) => setSelectedProvider(e.target.value as AIMarketProvider)}
            disabled={loading || providerStatusLoading || availableProviders.length === 0}
            aria-label="AI provider for parameter suggestions"
            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-200 focus:outline-none disabled:opacity-50"
          >
            {availableProviders.map((p, index) => (
              <option key={p} value={p}>
                {getAIProviderDisplayName(statusMap[p]) || `Provider ${index + 1}`}
              </option>
            ))}
          </select>

          <button
            type="button"
            onClick={runSuggest}
            disabled={loading || availableProviders.length === 0 || !isSavedStrategy}
            className="flex min-h-9 items-center gap-1.5 rounded-lg bg-emerald-700 px-3.5 py-2 text-xs font-medium text-white transition hover:bg-emerald-600 disabled:opacity-50"
          >
            {loading ? (
              <Loader className="h-3.5 w-3.5 animate-spin" />
            ) : result ? (
              <RefreshCw className="h-3.5 w-3.5" />
            ) : (
              <Sparkles className="h-3.5 w-3.5" />
            )}
            {result ? 'Refresh' : 'Suggest Parameters'}
          </button>

          {result && (
            <button
              type="button"
              onClick={() => setCollapsed((v) => !v)}
              aria-label={
                collapsed ? 'Expand AI parameter suggestions' : 'Collapse AI parameter suggestions'
              }
              className="rounded-md p-2 text-slate-400 hover:text-slate-200"
            >
              {collapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
            </button>
          )}
        </div>
      </div>

      {!isSavedStrategy && (
        <p className="mt-3 text-xs text-slate-400">
          Save the strategy first to get suggestions based on its backtests.
        </p>
      )}

      {/* Idle hint */}
      {isSavedStrategy && !result && !loading && !error && (
        <p className="mt-3 text-xs text-slate-500">
          Get up to {maxSuggestions} specific, numbered parameter adjustments for{' '}
          <span className="text-slate-300">{strategy.name}</span>, based on its saved backtests and
          live trades. You can apply all at once or one-by-one.
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
          Analysing the backtests and live trades of {strategy.name}… This can take a couple of
          minutes.
        </div>
      )}

      {error && (
        <div className="mt-3 rounded-lg border border-red-700/40 bg-red-950/30 px-3 py-2 text-xs text-red-300">
          {error}
        </div>
      )}

      {result && !collapsed && (
        <div className="mt-4 space-y-3">
          <EvidenceSummaryChips summary={evidenceSummary} showNotes />

          {summaryText && (
            <p className="whitespace-pre-line text-sm leading-relaxed text-slate-200">
              {summaryText}
            </p>
          )}

          {showContent && (
            <p className="whitespace-pre-line text-sm leading-relaxed text-slate-300">
              {result.content}
            </p>
          )}

          {dataGaps.length > 0 && (
            <div className="rounded-lg border border-amber-700/30 bg-amber-950/20 px-3 py-2 text-xs text-amber-100/90">
              <p className="font-semibold text-amber-200">Data gaps</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-4">
                {dataGaps.map((gap, index) => (
                  <li key={`${index}-${gap}`} className="wrap-break-word">
                    {gap}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {parsedSuggestions.length > 0 && onApplyParams && (
            <div className="rounded-lg border border-emerald-700/40 bg-emerald-950/20 px-3 py-2">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs font-medium text-emerald-200">
                  {pendingSuggestions.length > 0
                    ? `${pendingSuggestions.length} suggestion${pendingSuggestions.length === 1 ? '' : 's'} pending`
                    : unavailableCount > 0
                      ? `${parsedSuggestions.length - unavailableCount} of ${parsedSuggestions.length} suggestions applied ✓`
                      : `All ${parsedSuggestions.length} suggestion${parsedSuggestions.length === 1 ? '' : 's'} applied ✓`}
                </p>
                <p className="text-[11px] text-emerald-300/80">
                  Apply all or use individual Apply buttons below.
                </p>
                {pendingSuggestions.length > 0 && (
                  <button
                    type="button"
                    onClick={() => void applyAllSuggestions()}
                    disabled={applyLoading}
                    className="rounded-md border border-emerald-500/40 bg-emerald-600/20 px-3 py-1.5 text-[11px] font-semibold text-emerald-100 transition hover:bg-emerald-600/35 disabled:opacity-50"
                  >
                    Review & Apply All
                  </button>
                )}
              </div>
              <ul className="space-y-2">
                {openSuggestions.map((item) => (
                  <li
                    key={item.key}
                    className="rounded-lg border border-emerald-700/40 bg-slate-900/60 px-3 py-2 text-[11px] text-emerald-100"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="font-medium text-slate-100">{displayLabel(item)}</span>
                          {item.label && (
                            <span className="font-mono text-[10px] text-slate-500">
                              {String(item.key)}
                            </span>
                          )}
                          <AISuggestionRiskBadges
                            risk={item.risk}
                            backtestOnly={item.backtestOnly}
                          />
                        </div>
                        <p className="mt-1 font-mono text-xs text-slate-300">
                          <span className="text-slate-400">
                            {formatAIParamValue(currentValueFor(item), item.unit)}
                          </span>
                          {' → '}
                          <span className="text-emerald-200">
                            {formatAIParamValue(item.value, item.unit)}
                          </span>
                        </p>
                        {item.evidence && (
                          <p className="mt-1 wrap-break-word text-[11px] leading-4 text-slate-400">
                            <span className="text-slate-500">Evidence: </span>
                            {item.evidence}
                          </p>
                        )}
                        {item.rationale && (
                          <p className="mt-1 wrap-break-word text-[11px] leading-4 text-slate-300">
                            {item.rationale}
                          </p>
                        )}
                      </div>
                      {unavailableKeys.has(item.key) ? (
                        <span className="rounded border border-slate-700 bg-slate-900/80 px-2.5 py-1 text-[10px] font-semibold text-slate-400">
                          Not editable on this page
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => queueSingleSuggestion(item)}
                          disabled={applyLoading}
                          aria-label={`Apply ${displayLabel(item)}`}
                          className="min-h-8 rounded border border-emerald-500/40 bg-emerald-700/20 px-2.5 py-1 text-[10px] font-semibold text-emerald-100 transition hover:bg-emerald-700/35 disabled:opacity-50"
                        >
                          Apply
                        </button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
              {applyError && <p className="mt-2 text-xs text-red-300">{applyError}</p>}
            </div>
          )}

          {dropped.length > 0 && (
            <div className="rounded-lg border border-slate-700/70 bg-slate-900/40 px-3 py-2 text-[11px] text-slate-400">
              <p className="font-semibold text-slate-300">Left out</p>
              <ul className="mt-1 space-y-0.5">
                {dropped.map((item, index) => (
                  <li key={`${index}-${String(item.parameter)}`} className="wrap-break-word">
                    <span className="font-mono">{String(item.parameter || 'unknown')}</span>
                    {`: ${String(item.reason ?? '')}`}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {!usedAI && providerNotConfigured && (
            <p className="text-xs text-slate-500">
              No key is configured for {getAIProviderLabel(provider)} — add one in Settings → AI
              Filters.
            </p>
          )}
        </div>
      )}

      {pendingApplyPreview &&
        typeof document !== 'undefined' &&
        createPortal(
          <div className="fixed inset-0 z-60 flex items-center justify-center bg-black/60 p-4">
            <div
              role="dialog"
              aria-modal="true"
              aria-label="Confirm AI parameter updates"
              className="w-full max-w-xl rounded-2xl border border-emerald-700/40 bg-slate-900 shadow-2xl"
            >
              <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
                <h3 className="text-sm font-semibold text-emerald-200">
                  Confirm AI parameter updates
                </h3>
                <button
                  type="button"
                  onClick={() => setPendingApplyPreview(null)}
                  disabled={applyLoading}
                  className="rounded-md border border-slate-700 px-2.5 py-1.5 text-xs text-slate-300 transition hover:border-slate-500 hover:text-white disabled:opacity-50"
                >
                  Close
                </button>
              </div>

              <div className="max-h-[60vh] space-y-2 overflow-y-auto px-5 py-4">
                {pendingApplyPreview.items.map((item) => (
                  <div
                    key={`preview-${item.key}`}
                    className="rounded-lg border border-slate-700 bg-slate-950/70 px-3 py-2"
                  >
                    <div className="flex flex-wrap items-center gap-1.5">
                      <p className="text-[11px] uppercase tracking-wide text-slate-400">
                        {displayLabel(item)}
                      </p>
                      {item.label && (
                        <span className="font-mono text-[10px] text-slate-500">
                          {String(item.key)}
                        </span>
                      )}
                      <AISuggestionRiskBadges risk={item.risk} backtestOnly={item.backtestOnly} />
                    </div>
                    <p className="mt-1 text-xs text-slate-300">
                      <span className="text-slate-500">Current:</span>{' '}
                      {formatAIParamValue(currentValueFor(item), item.unit)}
                    </p>
                    <p className="text-xs text-emerald-200">
                      <span className="text-emerald-400">Suggested:</span>{' '}
                      {formatAIParamValue(item.value, item.unit)}
                    </p>
                    {item.evidence && (
                      <p className="mt-1 wrap-break-word text-[11px] leading-4 text-slate-400">
                        <span className="text-slate-500">Evidence: </span>
                        {item.evidence}
                      </p>
                    )}
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
                  type="button"
                  onClick={() => setPendingApplyPreview(null)}
                  disabled={applyLoading}
                  className="min-h-9 w-full rounded-lg border border-slate-700 px-4 py-2 text-xs text-slate-200 transition hover:border-slate-500 disabled:opacity-50 sm:w-auto"
                >
                  Cancel (Esc)
                </button>
                <button
                  type="button"
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
