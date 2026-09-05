import {
  BrainCircuit,
  CircleHelp,
  Download,
  Loader,
  Search,
  Settings,
  Sparkles,
  Trash2,
  TrendingUp,
} from 'lucide-react';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import api, { type AIBacktestExplainRequest } from '../api';
import {
  getAIProviderDisplayName,
  useAIProviderAvailability,
} from '../features/ai/providerAvailability';
import { toCsvCell } from '../utils/csv';
import { PageContainer } from './PageContainer';

interface BacktestResult {
  run_id: string;
  total_return_pct: number;
  total_pnl: number;
  sharpe_ratio: number;
  win_rate: number;
  max_drawdown: number;
  num_trades: number;
  avg_trade_duration: number;
  start_date: string;
  end_date: string;
  created_at?: string;
  status?: string;
  is_from_cache?: boolean; // Indicates if result is from cached backtest
  cache_age_days?: number; // Number of days since cached result was created
}

const toNumber = (value: unknown, fallback = 0): number => {
  const num = Number(value);
  return Number.isFinite(num) ? num : fallback;
};

const toRecord = (value: unknown): Record<string, unknown> =>
  typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : {};

const getErrorMessage = (error: unknown, fallback: string): string =>
  error instanceof Error ? error.message : fallback;

const normalizeRun = (raw: unknown): BacktestResult => {
  const normalized = toRecord(raw);
  const totalPnl = toNumber(normalized.total_pnl, 0);
  const initialBalance = 1000;

  return {
    run_id: String(normalized.run_id || ''),
    total_return_pct:
      normalized.total_return_pct !== undefined
        ? toNumber(normalized.total_return_pct, 0)
        : (totalPnl / initialBalance) * 100,
    total_pnl: totalPnl,
    sharpe_ratio: toNumber(normalized.sharpe_ratio, 0),
    win_rate: toNumber(normalized.win_rate, 0),
    max_drawdown:
      normalized.max_drawdown !== undefined
        ? toNumber(normalized.max_drawdown, 0)
        : toNumber(normalized.max_drawdown_pct, 0),
    num_trades:
      normalized.num_trades !== undefined
        ? toNumber(normalized.num_trades, 0)
        : toNumber(normalized.total_trades, 0),
    avg_trade_duration: toNumber(normalized.avg_trade_duration, 0),
    start_date: String(normalized.start_date || ''),
    end_date: String(normalized.end_date || ''),
    created_at: typeof normalized.created_at === 'string' ? normalized.created_at : undefined,
    status: typeof normalized.status === 'string' ? normalized.status : undefined,
    is_from_cache: Boolean(normalized.is_from_cache),
    cache_age_days:
      normalized.cache_age_days !== undefined ? toNumber(normalized.cache_age_days, 0) : undefined,
  };
};

interface SelectedBacktest {
  run_id: string;
  data: BacktestResult;
}

interface ComparisonAggregate {
  avgWinRate: number;
  avgSharpe: number;
  avgReturnPct: number;
  avgPnl: number;
  avgDrawdown: number;
  totalTrades: number;
  dateStart: string;
  dateEnd: string;
}

interface MetricRaceDefinition {
  key: keyof BacktestResult;
  label: string;
  lowerIsBetter?: boolean;
  formatter: (value: number) => string;
}

interface WinnerSummaryItem {
  title: string;
  subtitle: string;
  runId: string;
  value: string;
  toneClass: string;
  pulseClass: string;
}

type SortOption = 'recent' | 'return' | 'sharpe' | 'pnl';

const ITEMS_PER_PAGE = 10;
const SHORTCUT_DISCOVERY_STORAGE_KEY = 'backtestComparatorShortcutDiscoverySeen';
const HIDE_SHORTCUT_TIPS_STORAGE_KEY = 'backtestComparatorHideShortcutTips';
const SHOW_UX_HINTS_STORAGE_KEY = 'backtestComparatorShowUxHints';
const HINT_DOT_POP_DURATION_MS = 300; // aligns with Tailwind duration-300 token

const METRIC_RACE_DEFINITIONS: MetricRaceDefinition[] = [
  {
    key: 'total_return_pct',
    label: 'Total Return',
    formatter: (value) => `${value.toFixed(2)}%`,
  },
  {
    key: 'total_pnl',
    label: 'Total PnL',
    formatter: (value) => `$${value.toFixed(2)}`,
  },
  {
    key: 'sharpe_ratio',
    label: 'Sharpe Ratio',
    formatter: (value) => value.toFixed(2),
  },
  {
    key: 'win_rate',
    label: 'Win Rate',
    formatter: (value) => `${value.toFixed(1)}%`,
  },
  {
    key: 'max_drawdown',
    label: 'Max Drawdown',
    lowerIsBetter: true,
    formatter: (value) => `${value.toFixed(1)}%`,
  },
  {
    key: 'num_trades',
    label: 'Number of Trades',
    formatter: (value) => value.toFixed(0),
  },
  {
    key: 'avg_trade_duration',
    label: 'Avg Trade Duration (hrs)',
    formatter: (value) => value.toFixed(1),
  },
];

export const BacktestComparator: React.FC = () => {
  const [backtests, setBacktests] = useState<BacktestResult[]>([]);
  const [selectedBacktests, setSelectedBacktests] = useState<SelectedBacktest[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState<SortOption>('recent');
  const [aiInsight, setAiInsight] = useState<string | null>(null);
  const [aiUsed, setAiUsed] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [pulsingWinners, setPulsingWinners] = useState<Record<string, boolean>>({});
  const [showShortcutToast, setShowShortcutToast] = useState(false);
  const [showUxHints, setShowUxHints] = useState(() => {
    try {
      const saved = window.localStorage.getItem(SHOW_UX_HINTS_STORAGE_KEY);
      if (saved === '1' || saved === '0') return saved === '1';
      // Backward compatibility with previous "hide shortcut tips" preference
      return window.localStorage.getItem(HIDE_SHORTCUT_TIPS_STORAGE_KEY) !== '1';
    } catch {
      return true;
    }
  });
  const [hintDotPop, setHintDotPop] = useState(false);
  const {
    availableProviders,
    statusMap,
    isLoading: providerStatusLoading,
  } = useAIProviderAvailability();
  const previousWinnerByTitleRef = useRef<Record<string, string>>({});
  const legendHelpChipRef = useRef<HTMLButtonElement | null>(null);
  const shortcutDiscoverySeenRef = useRef(false);
  const hintDotPopTimeoutRef = useRef<number | null>(null);

  // Fetch available backtests
  useEffect(() => {
    const fetchBacktests = async () => {
      setLoading(true);
      try {
        const response = await api.listBacktests(0, 50);
        const raw = toRecord(response);
        const rawData = toRecord(raw.data);
        const data = Array.isArray(raw?.backtests)
          ? raw.backtests
          : Array.isArray(rawData.backtests)
            ? rawData.backtests
            : Array.isArray(rawData.runs)
              ? rawData.runs
              : Array.isArray(raw?.runs)
                ? raw.runs
                : [];

        const normalized = data.map((entry) => normalizeRun(entry));
        // Sort by most recent first
        const sorted = [...normalized].sort((a, b) => {
          if (!a.created_at || !b.created_at) return 0;
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        });
        setBacktests(sorted);
      } catch (err: unknown) {
        setError(getErrorMessage(err, 'Failed to load backtests'));
        console.error('❌ BacktestComparator: Failed to load backtests:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchBacktests();
  }, []);

  const normalizedSearch = searchTerm.trim().toLowerCase();
  const aiProvider = availableProviders[0] ?? null;
  const aiProviderDisplayName = aiProvider
    ? getAIProviderDisplayName(statusMap[aiProvider])
    : 'AI unavailable';

  const filteredAndSortedBacktests = useMemo(() => {
    const filtered = backtests.filter((bt) => {
      if (!normalizedSearch) return true;
      return (
        bt.run_id.toLowerCase().includes(normalizedSearch) ||
        bt.start_date.toLowerCase().includes(normalizedSearch) ||
        bt.end_date.toLowerCase().includes(normalizedSearch)
      );
    });

    const sorted = [...filtered].sort((a, b) => {
      if (sortBy === 'return') return (b.total_return_pct ?? 0) - (a.total_return_pct ?? 0);
      if (sortBy === 'sharpe') return (b.sharpe_ratio ?? 0) - (a.sharpe_ratio ?? 0);
      if (sortBy === 'pnl') return (b.total_pnl ?? 0) - (a.total_pnl ?? 0);
      if (!a.created_at || !b.created_at) return 0;
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });

    return sorted;
  }, [backtests, normalizedSearch, sortBy]);

  // Pagination logic
  const totalPages = Math.max(1, Math.ceil(filteredAndSortedBacktests.length / ITEMS_PER_PAGE));
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const paginatedBacktests = useMemo(() => {
    const start = (safeCurrentPage - 1) * ITEMS_PER_PAGE;
    return filteredAndSortedBacktests.slice(start, start + ITEMS_PER_PAGE);
  }, [filteredAndSortedBacktests, safeCurrentPage]);

  // Toggle backtest selection
  const toggleBacktest = (backtest: BacktestResult) => {
    setSelectedBacktests((prev) => {
      const existing = prev.find((b) => b.run_id === backtest.run_id);
      if (existing) {
        return prev.filter((b) => b.run_id !== backtest.run_id);
      } else if (prev.length < 5) {
        return [...prev, { run_id: backtest.run_id, data: backtest }];
      }
      return prev;
    });
  };

  const handleNextPage = () => {
    if (currentPage < totalPages) {
      setCurrentPage(currentPage + 1);
    }
  };

  const handlePreviousPage = () => {
    if (currentPage > 1) {
      setCurrentPage(currentPage - 1);
    }
  };

  // Remove selected backtest
  const removeSelected = (run_id: string) => {
    setSelectedBacktests((prev) => prev.filter((b) => b.run_id !== run_id));
  };

  // Calculate delta between first and other backtests
  const getDelta = (metric: keyof BacktestResult, index: number) => {
    if (index === 0 || selectedBacktests.length === 0) return null;
    const baseline = selectedBacktests[0]!.data[metric] as number;
    const current = selectedBacktests[index]?.data[metric] as number | undefined;
    if (current === undefined) return null;
    const delta = current - baseline;
    const deltaPercent = Math.abs(baseline) > 0 ? (delta / Math.abs(baseline)) * 100 : 0;
    return { delta, deltaPercent };
  };

  // Export to CSV
  const exportToCSV = () => {
    const headers = [
      'Run ID',
      'Total Return %',
      'Total PnL',
      'Sharpe Ratio',
      'Win Rate',
      'Max Drawdown',
      'Num Trades',
      'Avg Trade Duration',
      'Start Date',
      'End Date',
    ];

    const rows = selectedBacktests.map((bt) => [
      bt.run_id || 'N/A',
      (bt.data.total_return_pct ?? 0).toFixed(2),
      (bt.data.total_pnl ?? 0).toFixed(2),
      (bt.data.sharpe_ratio ?? 0).toFixed(2),
      (bt.data.win_rate ?? 0).toFixed(2),
      (bt.data.max_drawdown ?? 0).toFixed(2),
      bt.data.num_trades ?? 0,
      (bt.data.avg_trade_duration ?? 0).toFixed(1),
      bt.data.start_date || 'N/A',
      bt.data.end_date || 'N/A',
    ]);

    const csv = [
      headers.map(toCsvCell).join(','),
      ...rows.map((row) => row.map(toCsvCell).join(',')),
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `backtest-comparison-${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  };

  // Get best/worst for highlighting
  const getBest = (metric: keyof BacktestResult) => {
    if (selectedBacktests.length === 0) return null;
    const metricValues = selectedBacktests.map((bt) => ({
      run_id: bt.run_id,
      value: bt.data[metric] as number,
    }));
    // Higher is better for most metrics (return, sharpe, win_rate)
    // Lower is better for drawdown
    if (metric === 'max_drawdown') {
      return metricValues.reduce((min, curr) => (curr.value < min.value ? curr : min)).run_id;
    }
    return metricValues.reduce((max, curr) => (curr.value > max.value ? curr : max)).run_id;
  };

  // Calculate how old a cached result is
  const getCacheAgeText = (createdAt?: string): string | null => {
    if (!createdAt) return null;
    const created = new Date(createdAt);
    const now = new Date();
    const diffMs = now.getTime() - created.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    const diffHours = Math.floor((diffMs % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));

    if (diffDays > 0) return `${diffDays}d ago`;
    if (diffHours > 0) return `${diffHours}h ago`;
    return 'Today';
  };

  const comparisonAggregate = useMemo<ComparisonAggregate | null>(() => {
    if (selectedBacktests.length === 0) return null;

    const total = selectedBacktests.length;
    const sum = selectedBacktests.reduce(
      (acc, item) => {
        acc.winRate += item.data.win_rate ?? 0;
        acc.sharpe += item.data.sharpe_ratio ?? 0;
        acc.returnPct += item.data.total_return_pct ?? 0;
        acc.pnl += item.data.total_pnl ?? 0;
        acc.drawdown += item.data.max_drawdown ?? 0;
        acc.trades += item.data.num_trades ?? 0;
        return acc;
      },
      { winRate: 0, sharpe: 0, returnPct: 0, pnl: 0, drawdown: 0, trades: 0 }
    );

    const sortedStarts = selectedBacktests
      .map((item) => item.data.start_date)
      .filter(Boolean)
      .sort();
    const sortedEnds = selectedBacktests
      .map((item) => item.data.end_date)
      .filter(Boolean)
      .sort();

    return {
      avgWinRate: sum.winRate / total,
      avgSharpe: sum.sharpe / total,
      avgReturnPct: sum.returnPct / total,
      avgPnl: sum.pnl / total,
      avgDrawdown: sum.drawdown / total,
      totalTrades: sum.trades,
      dateStart: sortedStarts[0] ?? '',
      dateEnd: sortedEnds[sortedEnds.length - 1] ?? '',
    };
  }, [selectedBacktests]);

  const autoSelectTopThree = () => {
    const topThree = filteredAndSortedBacktests.slice(0, 3);
    setSelectedBacktests(topThree.map((entry) => ({ run_id: entry.run_id, data: entry })));
  };

  const winnerSummary = useMemo<WinnerSummaryItem[]>(() => {
    if (selectedBacktests.length < 2) return [];

    const bestReturn = selectedBacktests.reduce((best, current) =>
      current.data.total_return_pct > best.data.total_return_pct ? current : best
    );

    const mostStable = selectedBacktests.reduce((best, current) =>
      current.data.max_drawdown < best.data.max_drawdown ? current : best
    );

    const bestRiskAdjusted = selectedBacktests
      .map((entry) => {
        const score =
          entry.data.sharpe_ratio * 100 -
          entry.data.max_drawdown +
          entry.data.win_rate * 0.35 +
          entry.data.total_return_pct * 0.2;
        return { entry, score };
      })
      .sort((a, b) => b.score - a.score)[0]?.entry;

    if (!bestRiskAdjusted) return [];

    return [
      {
        title: 'Best Absolute Return',
        subtitle: 'Highest total return',
        runId: bestReturn.run_id,
        value: `${bestReturn.data.total_return_pct.toFixed(2)}%`,
        toneClass: 'text-emerald-300 border-emerald-500/40 bg-emerald-900/15',
        pulseClass: 'ring-emerald-300/65 shadow-[0_0_32px_rgba(16,185,129,0.4)]',
      },
      {
        title: 'Best Risk-Adjusted',
        subtitle: 'Sharpe + drawdown + consistency',
        runId: bestRiskAdjusted.run_id,
        value: `${bestRiskAdjusted.data.sharpe_ratio.toFixed(2)} Sharpe`,
        toneClass: 'text-cyan-300 border-cyan-500/40 bg-cyan-900/15',
        pulseClass: 'ring-cyan-300/65 shadow-[0_0_32px_rgba(34,211,238,0.35)]',
      },
      {
        title: 'Most Stable Run',
        subtitle: 'Lowest max drawdown',
        runId: mostStable.run_id,
        value: `${mostStable.data.max_drawdown.toFixed(2)}% DD`,
        toneClass: 'text-violet-300 border-violet-500/40 bg-violet-900/15',
        pulseClass: 'ring-violet-300/65 shadow-[0_0_32px_rgba(167,139,250,0.38)]',
      },
    ];
  }, [selectedBacktests]);

  const winnerSummarySignature = useMemo(
    () => winnerSummary.map((item) => `${item.title}:${item.runId}:${item.value}`).join('|'),
    [winnerSummary]
  );

  const selectionSignature = useMemo(
    () => selectedBacktests.map((item) => item.run_id).join('|'),
    [selectedBacktests]
  );

  useEffect(() => {
    // Ref init from localStorage; refs are not render state, so syncing them
    // in an effect is the intended escape hatch.
    try {
      shortcutDiscoverySeenRef.current =
        window.localStorage.getItem(SHORTCUT_DISCOVERY_STORAGE_KEY) === '1';
    } catch {
      shortcutDiscoverySeenRef.current = false;
    }
  }, []);

  // Animation restart keys: consumed only as React keys, so a derived value
  // that changes with the underlying selection is equivalent to the old
  // effect-incremented counters — without the cascading render.
  const winnerAnimationKey = winnerSummarySignature;
  const raceAnimationKey = selectionSignature;

  const activePulsingWinners =
    winnerSummary.length === 0 ? ({} as Record<string, boolean>) : pulsingWinners;

  useEffect(() => {
    if (winnerSummary.length === 0) {
      previousWinnerByTitleRef.current = {};
      return;
    }

    const nextPrevious: Record<string, string> = {};
    const changedTitles: string[] = [];

    winnerSummary.forEach((item) => {
      const previousRunId = previousWinnerByTitleRef.current[item.title];
      nextPrevious[item.title] = item.runId;

      if (previousRunId && previousRunId !== item.runId) {
        changedTitles.push(item.title);
      }
    });

    previousWinnerByTitleRef.current = nextPrevious;

    if (changedTitles.length === 0) {
      return;
    }

    setPulsingWinners((prev) => {
      const next = { ...prev };
      changedTitles.forEach((title) => {
        next[title] = true;
      });
      return next;
    });

    const timeoutId = window.setTimeout(() => {
      setPulsingWinners((prev) => {
        const next = { ...prev };
        changedTitles.forEach((title) => {
          delete next[title];
        });
        return next;
      });
    }, 1400);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [winnerSummary]);

  useEffect(() => {
    const handleLegendHelpShortcut = (event: KeyboardEvent) => {
      const isQuestionShortcut = event.key === '?' || (event.key === '/' && event.shiftKey);
      if (!isQuestionShortcut) return;

      const target = event.target as HTMLElement | null;
      const isTypingElement =
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement ||
        Boolean(target?.isContentEditable);

      if (isTypingElement || selectedBacktests.length === 0) {
        return;
      }

      event.preventDefault();
      legendHelpChipRef.current?.focus();

      if (!shortcutDiscoverySeenRef.current && showUxHints) {
        shortcutDiscoverySeenRef.current = true;
        setShowShortcutToast(true);
        try {
          window.localStorage.setItem(SHORTCUT_DISCOVERY_STORAGE_KEY, '1');
        } catch {
          // Ignore storage access errors (e.g., privacy mode)
        }
      }
    };

    window.addEventListener('keydown', handleLegendHelpShortcut);
    return () => {
      window.removeEventListener('keydown', handleLegendHelpShortcut);
    };
  }, [selectedBacktests.length, showUxHints]);

  useEffect(() => {
    if (!showShortcutToast) return;

    const timeoutId = window.setTimeout(() => {
      setShowShortcutToast(false);
    }, 2500);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [showShortcutToast]);

  useEffect(() => {
    return () => {
      if (hintDotPopTimeoutRef.current !== null) {
        window.clearTimeout(hintDotPopTimeoutRef.current);
      }
    };
  }, []);

  const clearSelection = () => {
    setSelectedBacktests([]);
    setAiInsight(null);
    setAiError(null);
  };

  const toggleUxHints = () => {
    const nextShowUxHints = !showUxHints;
    setShowUxHints(nextShowUxHints);
    setHintDotPop(true);

    if (hintDotPopTimeoutRef.current !== null) {
      window.clearTimeout(hintDotPopTimeoutRef.current);
    }
    hintDotPopTimeoutRef.current = window.setTimeout(() => {
      setHintDotPop(false);
      hintDotPopTimeoutRef.current = null;
    }, HINT_DOT_POP_DURATION_MS);

    if (!nextShowUxHints) {
      setShowShortcutToast(false);
    }

    try {
      window.localStorage.setItem(SHOW_UX_HINTS_STORAGE_KEY, nextShowUxHints ? '1' : '0');
    } catch {
      // Ignore storage access errors
    }
  };

  const requestAIInsight = useCallback(async () => {
    if (!comparisonAggregate || selectedBacktests.length < 2) return;
    if (!aiProvider) {
      setAiInsight(null);
      setAiUsed(false);
      setAiError('No AI provider is available for this account. Add a provider key in Settings.');
      return;
    }

    setAiLoading(true);
    setAiError(null);

    const payload: AIBacktestExplainRequest = {
      provider: aiProvider,
      win_rate: comparisonAggregate.avgWinRate,
      total_pnl_usd: comparisonAggregate.avgPnl,
      sharpe_ratio: comparisonAggregate.avgSharpe,
      max_drawdown_pct: comparisonAggregate.avgDrawdown,
      total_trades: comparisonAggregate.totalTrades,
      profit_factor: Math.max(0.1, 1 + comparisonAggregate.avgReturnPct / 100),
      markets: selectedBacktests.map((item) => `run:${item.run_id.slice(0, 8)}`),
      start_date: comparisonAggregate.dateStart,
      end_date: comparisonAggregate.dateEnd,
    };

    try {
      const response = await api.explainBacktest(payload);
      const responseData =
        response?.data ??
        (response as unknown as { data?: { content?: string; used_ai?: boolean } })?.data;
      const content = typeof responseData?.content === 'string' ? responseData.content : '';
      setAiInsight(
        content || `${aiProviderDisplayName} returned no narrative. Try refreshing insights.`
      );
      setAiUsed(Boolean(responseData?.used_ai));
    } catch (err) {
      setAiError(getErrorMessage(err, 'Failed to generate AI insight'));
    } finally {
      setAiLoading(false);
    }
  }, [aiProvider, aiProviderDisplayName, comparisonAggregate, selectedBacktests]);

  // Stale insights from a previous selection are hidden at render time and
  // replaced on the next request — no synchronous clearing effect needed.
  const hasEnoughSelectionForAi = selectedBacktests.length >= 2;
  const effectiveAiInsight = hasEnoughSelectionForAi ? aiInsight : null;
  const effectiveAiError = hasEnoughSelectionForAi ? aiError : null;
  const effectiveAiUsed = hasEnoughSelectionForAi ? aiUsed : false;

  useEffect(() => {
    if (providerStatusLoading || selectedBacktests.length < 2) {
      return;
    }
    // Microtask keeps the loader's synchronous state reset out of the effect.
    void Promise.resolve().then(() => requestAIInsight());
  }, [providerStatusLoading, requestAIInsight, selectedBacktests.length]);

  return (
    <PageContainer size="wide" className="space-y-6 page-reveal">
      <section className="platform-hero p-5 sm:p-6 lg:p-7">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <p className="inline-flex items-center gap-2 rounded-full border border-cyan-400/30 bg-cyan-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-cyan-200">
              <Sparkles className="h-3.5 w-3.5" />
              AI-Enhanced Compare Lab
            </p>
            <h1 className="text-2xl font-bold text-white sm:text-3xl">Compare Backtests</h1>
            <p className="max-w-2xl text-sm text-slate-300">
              Scan, select, and compare up to 5 runs with instant metric deltas and automatic AI
              commentary to help you decide faster.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <div className="platform-stat-card min-w-30">
              <p className="text-[11px] uppercase tracking-wide text-slate-400">Total Runs</p>
              <p className="mt-1 text-lg font-semibold text-white">{backtests.length}</p>
            </div>
            <div className="platform-stat-card min-w-30">
              <p className="text-[11px] uppercase tracking-wide text-slate-400">Visible</p>
              <p className="mt-1 text-lg font-semibold text-cyan-300">
                {filteredAndSortedBacktests.length}
              </p>
            </div>
            <div className="platform-stat-card min-w-30">
              <p className="text-[11px] uppercase tracking-wide text-slate-400">Selected</p>
              <p className="mt-1 text-lg font-semibold text-emerald-300">
                {selectedBacktests.length} / 5
              </p>
            </div>
            <div className="platform-stat-card min-w-30">
              <p className="text-[11px] uppercase tracking-wide text-slate-400">AI Provider</p>
              <p className="mt-1 text-lg font-semibold text-violet-300">{aiProviderDisplayName}</p>
            </div>
          </div>
        </div>
      </section>

      {/* Backtest Selection - Card View */}
      <div className="platform-panel space-y-5">
        <div className="mb-6 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-2xl font-bold text-white">Select Runs</h2>
            <p className="text-sm text-gray-400 mt-1">
              Pick at least 2 runs (up to 5).
              {showUxHints ? ' Tip: use auto-pick for fast triage.' : ''}
            </p>
          </div>
          <div className="text-left md:text-right">
            <div className="text-sm text-gray-400">
              Showing {(currentPage - 1) * ITEMS_PER_PAGE + 1} -{' '}
              {Math.min(currentPage * ITEMS_PER_PAGE, filteredAndSortedBacktests.length)} of{' '}
              {filteredAndSortedBacktests.length}
            </div>
            <div className="text-sm font-semibold text-blue-400 mt-1">
              Selected: {selectedBacktests.length} / 5
            </div>
          </div>
        </div>

        <div className="grid gap-3 lg:grid-cols-[1fr_auto_auto_auto]">
          <label className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
            <input
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setCurrentPage(1);
              }}
              placeholder="Search by run ID or date..."
              className="w-full rounded-lg border border-slate-700 bg-slate-900/80 py-2.5 pl-9 pr-3 text-sm text-slate-100 placeholder:text-slate-500 focus:border-cyan-500 focus:outline-none"
            />
          </label>

          <select
            value={sortBy}
            onChange={(e) => {
              setSortBy(e.target.value as SortOption);
              setCurrentPage(1);
            }}
            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 focus:border-cyan-500 focus:outline-none"
          >
            <option value="recent">Sort: Most Recent</option>
            <option value="return">Sort: Highest Return</option>
            <option value="sharpe">Sort: Best Sharpe</option>
            <option value="pnl">Sort: Highest PnL</option>
          </select>

          <button
            onClick={autoSelectTopThree}
            className="platform-button platform-button-secondary"
          >
            <TrendingUp className="h-4 w-4" />
            Auto-pick Top 3
          </button>

          <button onClick={clearSelection} className="platform-button platform-button-secondary">
            Clear Selection
          </button>
        </div>

        {error && (
          <div className="mb-4 p-4 bg-red-900 border border-red-700 rounded text-red-200">
            {error}
          </div>
        )}

        {loading ? (
          <div className="text-center py-12">
            <div className="flex items-center justify-center gap-2 text-gray-400">
              <Loader className="h-4 w-4 animate-spin" /> Loading backtests...
            </div>
          </div>
        ) : filteredAndSortedBacktests.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-gray-400">No backtests match your search</div>
          </div>
        ) : (
          <>
            {/* Card Grid */}
            <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
              {paginatedBacktests.map((bt) => {
                const isSelected = selectedBacktests.some((s) => s.run_id === bt.run_id);
                const canSelectMore = selectedBacktests.length < 5;
                const isClickable = isSelected || canSelectMore;

                return (
                  <button
                    key={bt.run_id}
                    onClick={() => isClickable && toggleBacktest(bt)}
                    disabled={!isClickable}
                    className={`relative p-4 rounded-lg border-2 transition-all text-left ${
                      isSelected
                        ? 'bg-linear-to-br from-blue-900 to-cyan-900 border-cyan-400 shadow-xl shadow-cyan-500/20 scale-[1.01]'
                        : isClickable
                          ? 'bg-slate-800/90 border-slate-700 hover:border-cyan-600 hover:bg-slate-700/90 hover:-translate-y-0.5'
                          : 'bg-slate-700 border-slate-600 opacity-50 cursor-not-allowed'
                    }`}
                  >
                    {/* Selection Indicator */}
                    {isSelected && (
                      <div className="absolute top-2 right-2 w-5 h-5 bg-blue-500 rounded-full flex items-center justify-center">
                        <div className="w-2 h-2 bg-white rounded-full"></div>
                      </div>
                    )}

                    {/* Card Content */}
                    <div>
                      {/* Run ID */}
                      <div className="font-mono text-xs text-blue-300 mb-2">
                        {(bt.run_id || 'N/A').slice(0, 8)}
                      </div>

                      {/* Date Range + Cache Badge */}
                      <div className="mb-3">
                        <div className="text-xs text-gray-400 mb-2 line-clamp-2">
                          {(bt.start_date || 'N/A').split('T')[0]} to{' '}
                          {(bt.end_date || 'N/A').split('T')[0]}
                        </div>
                        {bt.is_from_cache && (
                          <div className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-orange-900 text-orange-200 border border-orange-700">
                            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z" />
                            </svg>
                            <span>
                              From cache {bt.created_at && `(${getCacheAgeText(bt.created_at)})`}
                            </span>
                          </div>
                        )}
                      </div>

                      {/* Key Metrics */}
                      <div className="space-y-2">
                        {/* Return */}
                        <div className="flex items-end justify-between">
                          <span className="text-xs text-gray-400">Return</span>
                          <span
                            className={`font-semibold text-sm ${
                              (bt.total_return_pct ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'
                            }`}
                          >
                            {(bt.total_return_pct ?? 0).toFixed(1)}%
                          </span>
                        </div>

                        {/* Sharpe */}
                        <div className="flex items-end justify-between">
                          <span className="text-xs text-gray-400">Sharpe</span>
                          <span
                            className={`font-semibold text-sm ${
                              (bt.sharpe_ratio ?? 0) >= 1 ? 'text-green-400' : 'text-yellow-400'
                            }`}
                          >
                            {(bt.sharpe_ratio ?? 0).toFixed(2)}
                          </span>
                        </div>

                        {/* Win Rate */}
                        <div className="flex items-end justify-between">
                          <span className="text-xs text-gray-400">Win Rate</span>
                          <span
                            className={`font-semibold text-sm ${
                              (bt.win_rate ?? 0) >= 50 ? 'text-green-400' : 'text-orange-400'
                            }`}
                          >
                            {(bt.win_rate ?? 0).toFixed(0)}%
                          </span>
                        </div>

                        {/* PnL */}
                        <div className="flex items-end justify-between">
                          <span className="text-xs text-gray-400">PnL</span>
                          <span
                            className={`font-semibold text-sm ${
                              (bt.total_pnl ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'
                            }`}
                          >
                            ${(bt.total_pnl ?? 0).toFixed(0)}
                          </span>
                        </div>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between gap-2 pt-4 border-t border-slate-600">
                <button
                  onClick={handlePreviousPage}
                  disabled={safeCurrentPage === 1}
                  className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  ← Previous
                </button>

                <div className="flex items-center gap-1 overflow-x-auto">
                  {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                    <button
                      key={page}
                      onClick={() => setCurrentPage(page)}
                      className={`px-3 py-1 rounded text-sm font-medium ${
                        currentPage === page
                          ? 'bg-cyan-600 text-white'
                          : 'text-gray-400 hover:text-white hover:bg-slate-700'
                      }`}
                    >
                      {page}
                    </button>
                  ))}
                </div>

                <button
                  onClick={handleNextPage}
                  disabled={safeCurrentPage === totalPages}
                  className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Next →
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {selectedBacktests.length >= 2 && comparisonAggregate && (
        <section className="platform-panel border-violet-500/30 bg-linear-to-br from-violet-950/30 via-slate-900/80 to-slate-900/80">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-violet-300">
                <BrainCircuit className="h-4 w-4" />
                AI Market Narrative
              </p>
              <p className="text-sm text-slate-300">
                Auto-generated comparative insight based on selected runs.
              </p>
            </div>
            <button
              onClick={() => void requestAIInsight()}
              disabled={aiLoading || providerStatusLoading || !aiProvider}
              className="platform-button bg-violet-600 text-white hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {aiLoading ? (
                <Loader className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              {aiLoading ? 'Refreshing insight...' : 'Refresh AI Insight'}
            </button>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="platform-stat-card border-violet-500/20">
              <p className="text-[11px] uppercase tracking-wide text-slate-400">Avg Return</p>
              <p
                className={`mt-1 text-lg font-semibold ${
                  comparisonAggregate.avgReturnPct >= 0 ? 'text-emerald-300' : 'text-red-300'
                }`}
              >
                {comparisonAggregate.avgReturnPct.toFixed(2)}%
              </p>
            </div>
            <div className="platform-stat-card border-violet-500/20">
              <p className="text-[11px] uppercase tracking-wide text-slate-400">Avg Sharpe</p>
              <p className="mt-1 text-lg font-semibold text-cyan-300">
                {comparisonAggregate.avgSharpe.toFixed(2)}
              </p>
            </div>
            <div className="platform-stat-card border-violet-500/20">
              <p className="text-[11px] uppercase tracking-wide text-slate-400">Total Trades</p>
              <p className="mt-1 text-lg font-semibold text-amber-300">
                {comparisonAggregate.totalTrades}
              </p>
            </div>
          </div>

          <div className="mt-4 rounded-xl border border-violet-500/30 bg-slate-950/50 p-4 text-sm leading-relaxed text-slate-200">
            {aiLoading && (
              <p className="text-slate-400">
                {aiProviderDisplayName} is analyzing the selected set...
              </p>
            )}
            {!aiLoading && aiError && <p className="text-red-300">{aiError}</p>}
            {!aiLoading && !effectiveAiError && effectiveAiInsight && (
              <p className="whitespace-pre-line">{effectiveAiInsight}</p>
            )}
            {!aiLoading && !effectiveAiError && !effectiveAiInsight && (
              <p className="text-slate-400">
                Select at least 2 runs to unlock AI comparative guidance.
              </p>
            )}
            {!aiLoading && !effectiveAiError && effectiveAiInsight && !effectiveAiUsed && (
              <p className="mt-3 text-xs text-slate-500">
                AI provider returned a fallback narrative; review provider configuration before
                relying on it.
              </p>
            )}
          </div>
        </section>
      )}

      {/* Comparison Metric Race */}
      {selectedBacktests.length > 0 && (
        <div className="platform-panel space-y-5">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-white">Metric Race</h3>
                <button
                  type="button"
                  onClick={toggleUxHints}
                  aria-pressed={showUxHints}
                  aria-label={showUxHints ? 'Disable UX hints' : 'Enable UX hints'}
                  className="inline-flex items-center gap-1.5 rounded-md border border-slate-700 bg-slate-900/70 px-2 py-1 text-[11px] text-slate-300 transition-all duration-200 hover:border-cyan-500/60 hover:text-cyan-300"
                >
                  <span
                    aria-hidden="true"
                    className={`h-1.5 w-1.5 rounded-full transition-all duration-200 ${
                      showUxHints
                        ? 'bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.75)]'
                        : 'bg-slate-500 shadow-none'
                    } ${hintDotPop ? 'scale-150 ring-2 ring-cyan-300/40' : 'scale-100'}`}
                  />
                  <Settings className="h-3.5 w-3.5" />
                  {showUxHints ? 'Hints on' : 'Hints off'}
                </button>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Card-based leaderboard view for faster pattern spotting and premium readability.
              </p>
              {showUxHints ? (
                <p className="mt-2 text-[11px] text-slate-500">
                  <span>
                    Tip: press{' '}
                    <kbd className="rounded border border-slate-600 bg-slate-800/70 px-1.5 py-0.5 text-slate-300">
                      ?
                    </kbd>{' '}
                    to preview winner formulas.
                  </span>
                </p>
              ) : (
                <p className="mt-2 text-[11px] text-slate-500">
                  UX hints are hidden. Use the settings toggle next to Metric Race to re-enable.
                </p>
              )}
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  ref={legendHelpChipRef}
                  type="button"
                  className="group relative inline-flex items-center gap-2 rounded-full border border-emerald-500/40 bg-emerald-900/20 px-3 py-1 text-[11px] font-medium text-emerald-200"
                  aria-label="Return Winner formula"
                  aria-keyshortcuts="?"
                >
                  <span className="h-2 w-2 rounded-full bg-emerald-300" />
                  Return Winner
                  <CircleHelp className="h-3 w-3 opacity-80" />
                  <span className="pointer-events-none absolute left-1/2 top-full z-20 mt-2 hidden w-64 -translate-x-1/2 rounded-lg border border-slate-700 bg-slate-950/95 px-3 py-2 text-left text-[11px] leading-relaxed text-slate-200 shadow-xl group-hover:block group-focus-visible:block">
                    Highest <strong className="text-emerald-300">Total Return %</strong> among
                    selected runs.
                  </span>
                </button>

                <button
                  type="button"
                  className="group relative inline-flex items-center gap-2 rounded-full border border-cyan-500/40 bg-cyan-900/20 px-3 py-1 text-[11px] font-medium text-cyan-200"
                  aria-label="Risk-Adjusted Winner formula"
                >
                  <span className="h-2 w-2 rounded-full bg-cyan-300" />
                  Risk-Adjusted Winner
                  <CircleHelp className="h-3 w-3 opacity-80" />
                  <span className="pointer-events-none absolute left-1/2 top-full z-20 mt-2 hidden w-72 -translate-x-1/2 rounded-lg border border-slate-700 bg-slate-950/95 px-3 py-2 text-left text-[11px] leading-relaxed text-slate-200 shadow-xl group-hover:block group-focus-visible:block">
                    Best composite score:
                    <br />
                    <strong className="text-cyan-300">
                      Sharpe×100 − Drawdown + WinRate×0.35 + Return×0.2
                    </strong>
                  </span>
                </button>

                <button
                  type="button"
                  className="group relative inline-flex items-center gap-2 rounded-full border border-violet-500/40 bg-violet-900/20 px-3 py-1 text-[11px] font-medium text-violet-200"
                  aria-label="Stability Winner formula"
                >
                  <span className="h-2 w-2 rounded-full bg-violet-300" />
                  Stability Winner
                  <CircleHelp className="h-3 w-3 opacity-80" />
                  <span className="pointer-events-none absolute left-1/2 top-full z-20 mt-2 hidden w-64 -translate-x-1/2 rounded-lg border border-slate-700 bg-slate-950/95 px-3 py-2 text-left text-[11px] leading-relaxed text-slate-200 shadow-xl group-hover:block group-focus-visible:block">
                    Lowest <strong className="text-violet-300">Max Drawdown %</strong> among
                    selected runs.
                  </span>
                </button>
              </div>
            </div>
            <button onClick={exportToCSV} className="platform-button platform-button-primary">
              <Download className="w-4 h-4" />
              Export CSV
            </button>
          </div>

          {winnerSummary.length > 0 && (
            <div key={winnerAnimationKey} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {winnerSummary.map((winner, index) => (
                <article
                  key={`${winner.title}-${winner.runId}`}
                  className={`rounded-xl border p-4 animate-fade-slide-up transition-all duration-300 ${winner.toneClass} ${
                    activePulsingWinners[winner.title]
                      ? `ring-2 animate-pulse ${winner.pulseClass}`
                      : ''
                  }`}
                  style={{ animationDelay: `${index * 70}ms` }}
                >
                  <p className="text-[11px] uppercase tracking-wide opacity-80">{winner.title}</p>
                  <p className="text-xs text-slate-300 mt-1">{winner.subtitle}</p>
                  <div className="mt-3 flex items-end justify-between gap-3">
                    <p className="font-mono text-xs text-slate-200">
                      run-{winner.runId.slice(0, 8)}
                    </p>
                    <p className="text-sm font-semibold">{winner.value}</p>
                  </div>
                </article>
              ))}
            </div>
          )}

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            {selectedBacktests.map((bt) => (
              <div key={bt.run_id} className="platform-stat-card border-slate-600/60">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-mono text-[11px] text-cyan-300">
                      run-{bt.run_id.slice(0, 8)}
                    </p>
                    <p className="text-[11px] text-slate-500 mt-1">
                      {(bt.data.start_date || 'N/A').split('T')[0]} →{' '}
                      {(bt.data.end_date || 'N/A').split('T')[0]}
                    </p>
                  </div>
                  <button
                    onClick={() => removeSelected(bt.run_id)}
                    className="text-gray-400 hover:text-red-400"
                    aria-label={`Remove ${bt.run_id}`}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div key={raceAnimationKey} className="grid gap-4 lg:grid-cols-2">
            {METRIC_RACE_DEFINITIONS.map((metric) => {
              const values = selectedBacktests.map((bt) => Number(bt.data[metric.key] ?? 0));
              const minValue = Math.min(...values);
              const maxValue = Math.max(...values);
              const range = maxValue - minValue;

              const raceRows = selectedBacktests
                .map((bt, idx) => {
                  const rawValue = Number(bt.data[metric.key] ?? 0);
                  const score =
                    range === 0
                      ? 1
                      : metric.lowerIsBetter
                        ? (maxValue - rawValue) / range
                        : (rawValue - minValue) / range;

                  return {
                    bt,
                    idx,
                    rawValue,
                    score,
                    isBest: getBest(metric.key) === bt.run_id,
                    delta: getDelta(metric.key, idx),
                  };
                })
                .sort((a, b) => b.score - a.score);

              return (
                <article
                  key={metric.key}
                  className="rounded-xl border border-slate-700/80 bg-slate-900/55 p-4 animate-fade-in"
                >
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <h4 className="text-sm font-semibold text-white">{metric.label}</h4>
                    <span className="text-[10px] uppercase tracking-wide text-slate-500">
                      {metric.lowerIsBetter ? 'Lower is better' : 'Higher is better'}
                    </span>
                  </div>

                  <div className="space-y-3">
                    {raceRows.map((row, rank) => {
                      const barWidth = Math.max(18, Math.round(row.score * 100));
                      const deltaTone =
                        row.delta && metric.lowerIsBetter
                          ? row.delta.delta <= 0
                            ? 'text-emerald-400'
                            : 'text-red-400'
                          : row.delta
                            ? row.delta.delta >= 0
                              ? 'text-emerald-400'
                              : 'text-red-400'
                            : 'text-slate-500';

                      return (
                        <div
                          key={`${metric.key}-${row.bt.run_id}`}
                          className={`rounded-lg border p-3 transition-all duration-300 hover:-translate-y-0.5 ${
                            row.isBest
                              ? 'border-emerald-500/60 bg-emerald-900/10'
                              : 'border-slate-700/70 bg-slate-900/40'
                          }`}
                          style={{ animationDelay: `${rank * 45}ms` }}
                        >
                          <div className="mb-2 flex items-center justify-between gap-2">
                            <div className="flex items-center gap-2">
                              <span className="text-[11px] font-semibold text-slate-400">
                                #{rank + 1}
                              </span>
                              <span className="font-mono text-xs text-cyan-300">
                                run-{row.bt.run_id.slice(0, 8)}
                              </span>
                            </div>
                            <span
                              className={`text-sm font-semibold ${
                                row.isBest ? 'text-emerald-300' : 'text-slate-200'
                              }`}
                            >
                              {metric.formatter(row.rawValue)}
                            </span>
                          </div>

                          <div className="h-2 rounded-full bg-slate-800 overflow-hidden">
                            <div
                              className={`h-full rounded-full transition-all duration-500 ${
                                row.isBest
                                  ? 'bg-linear-to-r from-emerald-500 to-cyan-400'
                                  : 'bg-linear-to-r from-cyan-600 to-blue-500'
                              }`}
                              style={{ width: `${barWidth}%`, transitionDelay: `${rank * 45}ms` }}
                            />
                          </div>

                          {row.delta && (
                            <p className={`mt-2 text-xs ${deltaTone}`}>
                              vs baseline: {row.delta.delta >= 0 ? '+' : ''}
                              {metric.key === 'total_pnl' ? '$' : ''}
                              {row.delta.delta.toFixed(metric.key === 'num_trades' ? 0 : 2)}
                              {metric.key === 'total_return_pct' ||
                              metric.key === 'win_rate' ||
                              metric.key === 'max_drawdown'
                                ? '%'
                                : ''}
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      )}

      {selectedBacktests.length === 0 && !loading && (
        <div className="text-center py-12 text-gray-400">
          Select at least 2 backtests to compare and unlock AI insight
        </div>
      )}

      {showShortcutToast && showUxHints && (
        <div className="pointer-events-none fixed bottom-5 right-5 z-40 animate-fade-in rounded-lg border border-cyan-500/40 bg-slate-950/95 px-3 py-2 text-xs text-cyan-100 shadow-xl shadow-cyan-500/20">
          Nice — shortcut unlocked. Press <span className="font-semibold text-cyan-300">?</span>{' '}
          anytime for winner formulas.
        </div>
      )}
    </PageContainer>
  );
};
