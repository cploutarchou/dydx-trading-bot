/**
 * Enhanced BacktestDetailsV2 Component
 *
 * Displays real candle data and position information from persistent database.
 * Replaces placeholder data with actual market data, P&L by pair, and trade records.
 */

import {
    Activity,
    Bot,
    CalendarRange,
    CandlestickChart,
    CircleDot,
    Clock3,
    Gauge,
    Layers,
    Loader,
    Pause,
    Percent,
    Play,
    Radar,
    Rocket,
    RotateCcw,
    Scale,
    ShieldCheck,
    Square,
    TrendingDown,
    TrendingUp,
    Waves,
} from 'lucide-react';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../api';
import { enhancedApiClient } from '../api/enhancedClient';
import { useBacktestProgress } from '../api/hooks';
import { AIBacktestExplainer } from '../components/AIBacktestExplainer';
import BacktestLightweightChart, {
    type BacktestChartMarker,
    type BacktestChartPoint,
} from '../components/BacktestLightweightChart';
import BacktestPositionsPanel from '../components/BacktestPositionsPanel';
import { BacktestResultsEnhanced } from '../components/BacktestResultsEnhanced';
import BacktestTradesPanel from '../components/BacktestTradesPanel';
import { PageContainer } from '../components/PageContainer';
import {
    LiveStateBadge,
    formatBacktestProgressSourceLabel,
    resolveBacktestStreamBadge,
} from '../components/ui/LiveState';
import { usePersistentPreference } from '../hooks/usePersistentPreference';

interface Candle {
  market: string;
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface Position {
  position_id: number;
  market_1: string;
  market_2: string;
  entry_timestamp: string;
  exit_timestamp: string | null;
  entry_price_m1: number;
  exit_price_m1: number | null;
  entry_price_m2: number;
  exit_price_m2: number | null;
  hedge_ratio: number;
  entry_zscore: number;
  exit_zscore: number | null;
  pnl_m1_usd: number;
  pnl_m2_usd: number;
  total_pnl_usd: number;
  status: string;
}

interface Trade {
  trade_id: string;
  market_1: string;
  market_2: string;
  entry_timestamp: string;
  exit_timestamp: string;
  entry_zscore: number;
  exit_zscore: number;
  entry_price_m1: number;
  exit_price_m1: number;
  entry_price_m2: number;
  exit_price_m2: number;
  hedge_ratio: number;
  pnl_usd: number;
  pnl_pct: number;
  duration_hours: number;
  win: boolean;
}

interface BacktestResponse {
  run_id: string;
  status: string;
  created_at: string;
  updated_at?: string;
  start_date?: string;
  end_date?: string;
  progress_percent?: number;
  progress_pct?: number;
  progress?: number;
  // Python field names
  total_pnl: number;
  total_pnl_usd?: number;
  win_rate: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  max_drawdown?: number;
  profit_factor?: number;
  total_trades?: number;
  error?: string;
  error_message?: string;
  cancellable?: boolean;
  pausable?: boolean;
  resumable?: boolean;
  restartable?: boolean;
  control_status?: string;
  control_action?: string;
  worker_backend?: string;
  request?: Record<string, unknown>;
  strategy_id?: number;
  strategy_snapshot?: Record<string, unknown>;
}

interface BacktestLogEntry {
  id: number;
  message: string;
  level: string;
  created_at: string;
}

interface StrategySummary {
  id: number;
  name: string;
  category?: string;
  description?: string;
  updated_at?: string;
  selected_markets?: string[];
  runtime_network?: 'testnet' | 'mainnet';
  zscore_threshold?: number;
  stats_window?: number;
}

interface SocketLogPayload {
  type?: string;
  timestamp?: string;
  level?: string;
  message?: string;
  current_pair?: string;
  current_task?: string;
  status?: string;
}

interface DetailSyncState {
  runId: string;
  cursor: string;
}

type ChartRange = '7D' | '30D' | '90D' | 'ALL';
type DetailTab = 'summary' | 'candles' | 'positions' | 'trades' | 'results';

const BACKTEST_DETAIL_TABS: readonly DetailTab[] = [
  'summary',
  'candles',
  'positions',
  'trades',
  'results',
];

const DETAIL_TAB_SHORTCUTS: Record<string, DetailTab> = {
  '1': 'summary',
  '2': 'candles',
  '3': 'positions',
  '4': 'trades',
  '5': 'results',
};

const asRecord = (value: unknown): Record<string, unknown> | null => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
};

const toNumber = (value: unknown, fallback: number = 0): number => {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
};

const toStringValue = (value: unknown, fallback: string = ''): string => {
  if (typeof value === 'string') return value;
  if (typeof value === 'number') return String(value);
  return fallback;
};

const firstMeaningfulString = (...values: unknown[]): string | null => {
  for (const value of values) {
    if (typeof value !== 'string') continue;
    const trimmed = value.trim();
    if (trimmed.length > 0) {
      return trimmed;
    }
  }
  return null;
};

const normalizePercentValue = (value: unknown): number => {
  const numeric = toNumber(value, 0);
  // Some endpoints return 0-1 and others return 0-100.
  return Math.abs(numeric) <= 1 ? numeric * 100 : numeric;
};

const formatDateValue = (value: string | null | undefined): string => {
  if (!value) return '-';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? '-'
    : parsed.toISOString().replace('T', ' ').replace('Z', ' UTC');
};

const normalizeStatus = (value: unknown): string => String(value || '').toLowerCase();

const shouldRenderListShellOnly = (status: unknown): boolean =>
  ['pending', 'queued', 'starting', 'started', 'running', 'in_progress'].includes(
    normalizeStatus(status)
  );

const firstFiniteNumber = (...values: unknown[]): number | null => {
  for (const value of values) {
    const parsed =
      typeof value === 'number' ? value : typeof value === 'string' ? Number(value) : NaN;
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return null;
};

const withTimeout = async <T,>(
  promise: Promise<T>,
  timeoutMs: number,
  label: string
): Promise<T> => {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;
  const timeoutPromise = new Promise<T>((_, reject) => {
    timeoutId = setTimeout(() => {
      reject(new Error(`${label} timed out after ${timeoutMs}ms`));
    }, timeoutMs);
  });

  try {
    return await Promise.race([promise, timeoutPromise]);
  } finally {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
  }
};

const unwrapDataRecord = (payload: unknown): Record<string, unknown> => {
  const root = asRecord(payload) ?? {};
  return asRecord(root.data) ?? root;
};

const buildFallbackBacktestFromStatus = (
  runId: string,
  payload: Record<string, unknown>
): BacktestResponse => {
  const now = new Date().toISOString();
  const progress =
    firstFiniteNumber(payload.progress_percent, payload.progress_pct, payload.progress) ?? 0;
  const status = firstMeaningfulString(payload.status, payload.state) ?? 'PENDING';
  const updatedAt = firstMeaningfulString(
    payload.updated_at,
    payload.timestamp,
    payload.started_at
  );

  return {
    run_id: runId,
    status,
    created_at: firstMeaningfulString(payload.created_at, payload.started_at, updatedAt) ?? now,
    updated_at: updatedAt ?? now,
    progress_percent: progress,
    progress_pct: progress,
    progress,
    total_pnl: firstFiniteNumber(payload.total_pnl, payload.total_pnl_usd) ?? 0,
    total_pnl_usd: firstFiniteNumber(payload.total_pnl_usd, payload.total_pnl) ?? 0,
    win_rate: firstFiniteNumber(payload.win_rate) ?? 0,
    sharpe_ratio: firstFiniteNumber(payload.sharpe_ratio) ?? 0,
    max_drawdown_pct: firstFiniteNumber(payload.max_drawdown_pct, payload.max_drawdown) ?? 0,
    max_drawdown: firstFiniteNumber(payload.max_drawdown, payload.max_drawdown_pct) ?? 0,
    profit_factor: firstFiniteNumber(payload.profit_factor) ?? undefined,
    total_trades: firstFiniteNumber(payload.total_trades) ?? 0,
    error: firstMeaningfulString(payload.error) ?? undefined,
    error_message: firstMeaningfulString(payload.error_message, payload.message) ?? undefined,
    cancellable: Boolean(payload.cancellable),
    pausable: Boolean(payload.pausable),
    resumable: Boolean(payload.resumable),
    restartable: Boolean(payload.restartable ?? true),
    control_status: firstMeaningfulString(payload.control_status) ?? undefined,
    control_action: firstMeaningfulString(payload.control_action) ?? undefined,
    worker_backend: firstMeaningfulString(payload.worker_backend) ?? undefined,
    request: asRecord(payload.request) ?? undefined,
    strategy_id: firstFiniteNumber(payload.strategy_id) ?? undefined,
    strategy_snapshot: asRecord(payload.strategy_snapshot) ?? undefined,
  };
};

const formatDurationFromSeconds = (seconds: number): string => {
  if (!Number.isFinite(seconds) || seconds <= 0) return '< 1s';
  const totalSeconds = Math.round(seconds);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;
  const parts: string[] = [];
  if (hours > 0) parts.push(`${hours}h`);
  if (minutes > 0) parts.push(`${minutes}m`);
  if (secs > 0 || parts.length === 0) parts.push(`${secs}s`);
  return parts.join(' ');
};

const normalizeTradeRecord = (trade: Record<string, unknown>): Trade => {
  const pnlUsd = toNumber(trade.pnl_usd, toNumber(trade.pnl, 0));
  const serverTradeId = toStringValue(trade.trade_id);
  return {
    trade_id: serverTradeId,
    market_1: toStringValue(trade.market_1, toStringValue(trade.base_market, '-')),
    market_2: toStringValue(trade.market_2, toStringValue(trade.quote_market, '-')),
    entry_timestamp: toStringValue(trade.entry_timestamp) || toStringValue(trade.entry_time),
    exit_timestamp: toStringValue(trade.exit_timestamp) || toStringValue(trade.exit_time),
    entry_zscore: toNumber(trade.entry_zscore, toNumber(trade.entry_z_score, 0)),
    exit_zscore: toNumber(trade.exit_zscore, toNumber(trade.exit_z_score, 0)),
    entry_price_m1: toNumber(trade.entry_price_m1, toNumber(trade.entry_price_1, 0)),
    exit_price_m1: toNumber(trade.exit_price_m1, toNumber(trade.exit_price_1, 0)),
    entry_price_m2: toNumber(trade.entry_price_m2, toNumber(trade.entry_price_2, 0)),
    exit_price_m2: toNumber(trade.exit_price_m2, toNumber(trade.exit_price_2, 0)),
    hedge_ratio: toNumber(trade.hedge_ratio, 0),
    pnl_usd: pnlUsd,
    pnl_pct: toNumber(trade.pnl_pct, toNumber(trade.pnl_percent, 0)),
    duration_hours: toNumber(trade.duration_hours, toNumber(trade.duration_minutes, 0) / 60),
    win: pnlUsd >= 0,
  };
};

const CHART_RANGE_DAYS: Record<Exclude<ChartRange, 'ALL'>, number> = {
  '7D': 7,
  '30D': 30,
  '90D': 90,
};

const OPERATOR_DENSITY_STORAGE_KEY = 'operator-ui-density';
const LEGACY_SUMMARY_DENSITY_STORAGE_KEY = 'backtest-details-summary-density';

const formatSignedCurrency = (value: number): string => {
  const sign = value >= 0 ? '+' : '-';
  return `${sign}$${Math.abs(value).toLocaleString('en-US', {
    maximumFractionDigits: 2,
  })}`;
};

const formatCurrency = (value: number): string =>
  `$${value.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;

const formatCompactValue = (value: number): string =>
  new Intl.NumberFormat('en-US', {
    notation: Math.abs(value) >= 1000 ? 'compact' : 'standard',
    maximumFractionDigits: Math.abs(value) >= 1000 ? 1 : 2,
  }).format(value);

const filterChartPointsByRange = (
  points: BacktestChartPoint[],
  range: ChartRange
): BacktestChartPoint[] => {
  if (range === 'ALL' || points.length === 0) {
    return points;
  }

  const latestPoint = points[points.length - 1];
  const latestDate = new Date(`${latestPoint.time}T00:00:00Z`);
  if (Number.isNaN(latestDate.getTime())) {
    return points;
  }

  const lookbackDays = CHART_RANGE_DAYS[range];
  const cutoff = latestDate.getTime() - lookbackDays * 24 * 60 * 60 * 1000;
  const filtered = points.filter((point) => {
    const pointDate = new Date(`${point.time}T00:00:00Z`);
    return !Number.isNaN(pointDate.getTime()) && pointDate.getTime() >= cutoff;
  });

  return filtered.length > 1 ? filtered : points;
};

const formatTimeAgo = (value: string | null | undefined): string => {
  if (!value) return 'No sync yet';
  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return 'No sync yet';
  const diffMs = Date.now() - timestamp;
  const diffSeconds = Math.max(0, Math.round(diffMs / 1000));
  if (diffSeconds < 5) return 'Just now';
  if (diffSeconds < 60) return `${diffSeconds}s ago`;
  const diffMinutes = Math.round(diffSeconds / 60);
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.round(diffHours / 24);
  return `${diffDays}d ago`;
};

const clampPercentage = (value: number): number => Math.max(0, Math.min(100, value));

const classifyFailureDiagnostic = (message?: string | null) => {
  const summary = String(message || '').trim();
  const normalized = summary.toLowerCase();

  if (!summary) {
    return {
      category: 'unknown',
      hint: 'No failure payload was returned. Check worker/API logs for this run ID.',
    };
  }

  if (/timeout|timed out|deadline/.test(normalized)) {
    return {
      category: 'timeout',
      hint: 'Try a shorter backtest window or fewer pairs and watch progress cadence.',
    };
  }
  if (/cancel|cancelled|canceled|user stopped|stop requested/.test(normalized)) {
    return {
      category: 'cancelled',
      hint: 'This run was stopped manually. Restart or retry it when ready.',
    };
  }
  if (/heartbeat|stale|stalled|worker task|interrupted|restarted/.test(normalized)) {
    return {
      category: 'runtime',
      hint: 'Cancel or delete this stale run, restart the bot API if needed, then launch a fresh backtest.',
    };
  }
  if (/network|connection|unreachable|socket|dns|refused/.test(normalized)) {
    return {
      category: 'network',
      hint: 'Verify API/worker connectivity and infrastructure service availability.',
    };
  }
  if (/config|invalid|missing|required|parameter|env/.test(normalized)) {
    return {
      category: 'config',
      hint: 'Re-check runtime configuration and required parameters before rerunning.',
    };
  }
  if (/insufficient|balance|margin|collateral/.test(normalized)) {
    return {
      category: 'account',
      hint: 'Validate funding and account constraints for the tested setup.',
    };
  }
  if (/panic|exception|traceback|internal/.test(normalized)) {
    return {
      category: 'runtime',
      hint: 'Inspect backend traces for this run and retry after fixing the root cause.',
    };
  }

  return {
    category: 'unknown',
    hint: 'Open logs for this run to inspect full execution context and stack traces.',
  };
};

export const BacktestDetailsV2: React.FC = () => {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const progressQuery = useBacktestProgress(runId || '');

  // Main backtest data
  const [backtest, setBacktest] = useState<BacktestResponse | null>(null);

  // Real data from API
  const [candles, setCandles] = useState<Candle[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [markets, setMarkets] = useState<string[]>([]);
  const [chartMarkers, setChartMarkers] = useState<BacktestChartMarker[]>([]);
  const [analyticsLoadedState, setAnalyticsLoadedState] = useState<DetailSyncState | null>(null);
  const [positionsLoadedState, setPositionsLoadedState] = useState<DetailSyncState | null>(null);
  const [tradesLoadedState, setTradesLoadedState] = useState<DetailSyncState | null>(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [positionsLoading, setPositionsLoading] = useState(false);
  const [tradesLoading, setTradesLoading] = useState(false);
  const [analyticsError, setAnalyticsError] = useState<string | null>(null);
  const [positionsError, setPositionsError] = useState<string | null>(null);
  const [tradesError, setTradesError] = useState<string | null>(null);

  // UI state
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedMarket, setSelectedMarket] = useState<string | null>(null);
  const [chartRange, setChartRange] = useState<ChartRange>('30D');
  const [activeTab, setActiveTab] = useState<DetailTab>('summary');
  const [summaryDensity, setSummaryDensity] = usePersistentPreference<'comfortable' | 'dense'>(
    OPERATOR_DENSITY_STORAGE_KEY,
    'comfortable',
    {
      allowedValues: ['comfortable', 'dense'] as const,
      legacyKeys: [LEGACY_SUMMARY_DENSITY_STORAGE_KEY],
    }
  );
  const [liveLogs, setLiveLogs] = useState<BacktestLogEntry[]>([]);
  const [controlAction, setControlAction] = useState<string | null>(null);
  const [controlError, setControlError] = useState<string | null>(null);
  const [runtimeNetwork, setRuntimeNetwork] = useState<'testnet' | 'mainnet'>('testnet');
  const [promotionAction, setPromotionAction] = useState<'create' | 'start' | null>(null);
  const [promotionMessage, setPromotionMessage] = useState<string | null>(null);
  const [promotionError, setPromotionError] = useState<string | null>(null);
  const [linkedStrategy, setLinkedStrategy] = useState<StrategySummary | null>(null);
  const [linkedStrategyLoading, setLinkedStrategyLoading] = useState(false);
  const [linkedStrategyError, setLinkedStrategyError] = useState<string | null>(null);
  const liveLogCounterRef = useRef(0);

  const backtestStatus = normalizeStatus(backtest?.status);
  const linkedStrategyId = useMemo(() => {
    const request = asRecord(backtest?.request);
    return firstFiniteNumber(backtest?.strategy_id, request?.strategy_id);
  }, [backtest?.request, backtest?.strategy_id]);

  const fetchBacktestMetadata = useCallback(
    async (showLoading: boolean = true) => {
      if (showLoading) {
        setLoading(true);
      }
      setError(null);

      if (!runId) {
        setBacktest(null);
        setError('Missing backtest run id');
        return;
      }

      const safeRunId = runId;

      try {
        const liveStatusResponse = await withTimeout(
          enhancedApiClient.getBacktestStatus(safeRunId),
          8000,
          'Backtest live status'
        );
        const liveStatusPayload = unwrapDataRecord(liveStatusResponse);
        const fallbackBacktest = buildFallbackBacktestFromStatus(safeRunId, liveStatusPayload);

        if (shouldRenderListShellOnly(fallbackBacktest.status)) {
          setBacktest(fallbackBacktest);
          setError(null);
          return;
        }

        try {
          const response = await withTimeout(api.getBacktest(safeRunId), 12000, 'Backtest detail');
          const data = response?.data || response;
          setBacktest(data as unknown as BacktestResponse);
        } catch (detailErr: unknown) {
          console.debug('Backtest detail request failed, rendering live summary shell:', detailErr);
          setBacktest(fallbackBacktest);
          setError(null);
        }
      } catch (err: unknown) {
        console.debug('Backtest live summary failed, rendering route-only run shell:', err);
        setBacktest(buildFallbackBacktestFromStatus(safeRunId, {}));
        setError(null);
      } finally {
        if (showLoading) {
          setLoading(false);
        }
      }
    },
    [runId]
  );

  // Fetch backtest metadata
  useEffect(() => {
    fetchBacktestMetadata();
  }, [fetchBacktestMetadata]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) {
        return;
      }

      const target = event.target as HTMLElement | null;
      if (target) {
        const tagName = target.tagName;
        const isTypingTarget =
          target.isContentEditable ||
          tagName === 'INPUT' ||
          tagName === 'TEXTAREA' ||
          tagName === 'SELECT';
        if (isTypingTarget) {
          return;
        }
      }

      const nextTab = DETAIL_TAB_SHORTCUTS[event.key];
      if (!nextTab) {
        return;
      }

      event.preventDefault();
      setActiveTab(nextTab);
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    if (!linkedStrategyId) {
      setLinkedStrategy(null);
      setLinkedStrategyError(null);
      setLinkedStrategyLoading(false);
      return;
    }

    const loadLinkedStrategy = async () => {
      setLinkedStrategyLoading(true);
      setLinkedStrategyError(null);
      try {
        const response = await api.getStrategy(linkedStrategyId);
        const data = response.data as StrategySummary | undefined;
        if (!cancelled) {
          setLinkedStrategy(data ?? null);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setLinkedStrategy(null);
          setLinkedStrategyError(
            err instanceof Error ? err.message : 'Unable to load linked strategy'
          );
        }
      } finally {
        if (!cancelled) {
          setLinkedStrategyLoading(false);
        }
      }
    };

    void loadLinkedStrategy();

    return () => {
      cancelled = true;
    };
  }, [linkedStrategyId]);

  useEffect(() => {
    setCandles([]);
    setPositions([]);
    setTrades([]);
    setMarkets([]);
    setChartMarkers([]);
    setSelectedMarket(null);
    setAnalyticsLoadedState(null);
    setPositionsLoadedState(null);
    setTradesLoadedState(null);
    setAnalyticsLoading(false);
    setPositionsLoading(false);
    setTradesLoading(false);
    setAnalyticsError(null);
    setPositionsError(null);
    setTradesError(null);
    setLiveLogs([]);
    liveLogCounterRef.current = 0;
  }, [runId]);

  const liveDetailCursor =
    typeof progressQuery.data?.updated_at === 'string' && progressQuery.data.updated_at.length > 0
      ? progressQuery.data.updated_at
      : typeof progressQuery.lastSocketEvent?.timestamp === 'string' &&
          progressQuery.lastSocketEvent.timestamp.length > 0
        ? progressQuery.lastSocketEvent.timestamp
        : `${progressQuery.progressPercent.toFixed(2)}`;
  const liveStatusForDetailSync = normalizeStatus(progressQuery.data?.status || backtest?.status);
  const isLiveDetailRun =
    liveStatusForDetailSync === 'running' ||
    liveStatusForDetailSync === 'pending' ||
    liveStatusForDetailSync === 'queued' ||
    liveStatusForDetailSync === 'created';
  const detailSyncCursor = isLiveDetailRun ? liveDetailCursor : 'settled';

  // Fetch analytics and map it to chart-friendly candle-like series
  useEffect(() => {
    const fetchAnalytics = async () => {
      if (!runId) {
        setCandles([]);
        setMarkets([]);
        setAnalyticsLoadedState(null);
        return;
      }
      if (activeTab !== 'candles') return;
      if (
        analyticsLoadedState?.runId === runId &&
        analyticsLoadedState.cursor === detailSyncCursor
      ) {
        return;
      }

      try {
        const hasExistingAnalytics = candles.length > 0;
        setAnalyticsLoading(!hasExistingAnalytics);
        setAnalyticsError(null);
        const response = await api.getBacktestAnalytics(runId);
        const payload = asRecord(response?.data || response);
        const root = asRecord(payload?.data) || payload;
        const daily = root?.daily_pnl;

        if (!Array.isArray(daily) || daily.length === 0) {
          setCandles([]);
          setMarkets([]);
          setChartMarkers([]);
          setAnalyticsLoadedState({
            runId,
            cursor: detailSyncCursor,
          });
          return;
        }

        let runningCumulative = 0;
        const marketSet = new Set<string>();

        const mapped: Candle[] = daily
          .map((item) => asRecord(item))
          .filter((item): item is Record<string, unknown> => item !== null)
          .map((point) => {
            const market = toStringValue(point.market, 'PORTFOLIO');
            const tsRaw =
              toStringValue(point.timestamp) ||
              toStringValue(point.date) ||
              new Date().toISOString();

            const pnlValue = toNumber(point.pnl, 0);
            const explicitCumulative = toNumber(point.cumulative_pnl, Number.NaN);

            if (Number.isFinite(explicitCumulative)) {
              runningCumulative = explicitCumulative;
            } else {
              runningCumulative += pnlValue;
            }

            marketSet.add(market);

            return {
              market,
              timestamp: tsRaw,
              open: runningCumulative,
              high: runningCumulative,
              low: runningCumulative,
              close: runningCumulative,
              volume: toNumber(point.trades, 0),
            };
          });

        setCandles(mapped);
        setMarkets(Array.from(marketSet));
        const analyticsTrades = Array.isArray(root?.trades)
          ? root.trades
              .map((item) => asRecord(item))
              .filter((item): item is Record<string, unknown> => item !== null)
              .map(normalizeTradeRecord)
          : [];
        setChartMarkers(
          analyticsTrades.map((trade) => ({
            time: trade.exit_timestamp || trade.entry_timestamp,
            pair: `${trade.market_1}/${trade.market_2}`,
            pnl: trade.pnl_usd,
          }))
        );
        setAnalyticsLoadedState({
          runId,
          cursor: detailSyncCursor,
        });
      } catch (err: unknown) {
        console.error('Failed to fetch backtest analytics:', err);
        if (candles.length === 0) {
          setCandles([]);
          setMarkets([]);
          setChartMarkers([]);
        }
        setAnalyticsError(err instanceof Error ? err.message : 'Failed to load analytics');
      } finally {
        setAnalyticsLoading(false);
      }
    };

    fetchAnalytics();
  }, [runId, activeTab, analyticsLoadedState, detailSyncCursor]);

  // Keep selected market valid when available markets update
  useEffect(() => {
    if (markets.length === 0) {
      setSelectedMarket(null);
      return;
    }

    if (!selectedMarket || !markets.includes(selectedMarket)) {
      setSelectedMarket(markets[0]);
    }
  }, [markets, selectedMarket]);

  // Fetch position snapshots and flatten to latest known entries per snapshot
  useEffect(() => {
    const fetchPositionSnapshots = async () => {
      if (!runId) {
        setPositions([]);
        setPositionsLoadedState(null);
        return;
      }
      if (activeTab !== 'positions') return;
      if (
        positionsLoadedState?.runId === runId &&
        positionsLoadedState.cursor === detailSyncCursor
      ) {
        return;
      }

      try {
        const hasExistingPositions = positions.length > 0;
        setPositionsLoading(!hasExistingPositions);
        setPositionsError(null);
        const response = await api.getBacktestPositionSnapshots(runId, 1000, 0);
        const payload = asRecord(response?.data || response);
        const root = asRecord(payload?.data) || payload;
        const snapshots = root?.snapshots;

        if (!Array.isArray(snapshots) || snapshots.length === 0) {
          setPositions([]);
          setPositionsLoadedState({
            runId,
            cursor: detailSyncCursor,
          });
          return;
        }

        const flattened: Position[] = [];

        snapshots.forEach((snapshot) => {
          const snapshotRecord = asRecord(snapshot);
          if (!snapshotRecord) return;

          const snapshotTimestamp =
            toStringValue(snapshotRecord.timestamp) || new Date().toISOString();
          const snapshotPositions = snapshotRecord.positions;

          if (!Array.isArray(snapshotPositions)) return;

          snapshotPositions.forEach((rawPos) => {
            const pos = asRecord(rawPos);
            if (!pos) return;

            const pnl = toNumber(pos.total_pnl_usd, Number.NaN) || toNumber(pos.unrealized_pnl, 0);

            flattened.push({
              position_id: toNumber(pos.position_id, 0),
              market_1: toStringValue(pos.market_1, '-'),
              market_2: toStringValue(pos.market_2, '-'),
              entry_timestamp:
                toStringValue(pos.entry_timestamp) ||
                toStringValue(pos.entry_time) ||
                snapshotTimestamp,
              exit_timestamp: toStringValue(pos.exit_timestamp) || null,
              entry_price_m1: toNumber(pos.entry_price_m1, toNumber(pos.entry_price_1, 0)),
              exit_price_m1: null,
              entry_price_m2: toNumber(pos.entry_price_m2, toNumber(pos.entry_price_2, 0)),
              exit_price_m2: null,
              hedge_ratio: toNumber(pos.hedge_ratio, 0),
              entry_zscore: toNumber(pos.entry_zscore, toNumber(pos.current_z_score, 0)),
              exit_zscore: null,
              pnl_m1_usd: 0,
              pnl_m2_usd: 0,
              total_pnl_usd: Number.isFinite(pnl) ? pnl : 0,
              status: toStringValue(pos.status, 'OPEN'),
            });
          });
        });

        setPositions(flattened);
        setPositionsLoadedState({
          runId,
          cursor: detailSyncCursor,
        });
      } catch (err: unknown) {
        console.error('Failed to fetch position snapshots:', err);
        if (positions.length === 0) {
          setPositions([]);
        }
        setPositionsError(err instanceof Error ? err.message : 'Failed to load positions');
      } finally {
        setPositionsLoading(false);
      }
    };

    fetchPositionSnapshots();
  }, [runId, activeTab, positionsLoadedState, detailSyncCursor]);

  // Fetch trades
  useEffect(() => {
    const fetchTrades = async () => {
      if (!runId) {
        setTrades([]);
        setTradesLoadedState(null);
        return;
      }
      if (activeTab !== 'trades') return;
      if (tradesLoadedState?.runId === runId && tradesLoadedState.cursor === detailSyncCursor) {
        return;
      }

      try {
        const hasExistingTrades = trades.length > 0;
        setTradesLoading(!hasExistingTrades);
        setTradesError(null);
        const response = await api.getBacktestTradesDetailed(runId, undefined, undefined, 0, 500);

        const payload = asRecord(response?.data || response);
        const root = asRecord(payload?.data) || payload;
        const rawTrades = root?.trades;

        if (Array.isArray(rawTrades)) {
          const normalizedTrades: Trade[] = rawTrades
            .map((item) => asRecord(item))
            .filter((item): item is Record<string, unknown> => item !== null)
            .map((trade) => {
              const pnlUsd = toNumber(trade.pnl_usd, toNumber(trade.pnl, 0));
              const serverTradeId = toStringValue(trade.trade_id);
              return {
                trade_id: serverTradeId,
                market_1: toStringValue(trade.market_1, toStringValue(trade.base_market, '-')),
                market_2: toStringValue(trade.market_2, toStringValue(trade.quote_market, '-')),
                entry_timestamp:
                  toStringValue(trade.entry_timestamp) || toStringValue(trade.entry_time),
                exit_timestamp:
                  toStringValue(trade.exit_timestamp) || toStringValue(trade.exit_time),
                entry_zscore: toNumber(trade.entry_zscore, toNumber(trade.entry_z_score, 0)),
                exit_zscore: toNumber(trade.exit_zscore, toNumber(trade.exit_z_score, 0)),
                entry_price_m1: toNumber(trade.entry_price_m1, toNumber(trade.entry_price_1, 0)),
                exit_price_m1: toNumber(trade.exit_price_m1, toNumber(trade.exit_price_1, 0)),
                entry_price_m2: toNumber(trade.entry_price_m2, toNumber(trade.entry_price_2, 0)),
                exit_price_m2: toNumber(trade.exit_price_m2, toNumber(trade.exit_price_2, 0)),
                hedge_ratio: toNumber(trade.hedge_ratio, 0),
                pnl_usd: pnlUsd,
                pnl_pct: toNumber(trade.pnl_pct, toNumber(trade.pnl_percent, 0)),
                duration_hours: toNumber(
                  trade.duration_hours,
                  toNumber(trade.duration_minutes, 0) / 60
                ),
                win: pnlUsd >= 0,
              };
            });

          setTrades(normalizedTrades);
          setTradesLoadedState({
            runId,
            cursor: detailSyncCursor,
          });
        } else {
          setTrades([]);
          setTradesLoadedState({
            runId,
            cursor: detailSyncCursor,
          });
        }
      } catch (err: unknown) {
        console.error('Failed to fetch trades:', err);
        if (trades.length === 0) {
          setTrades([]);
        }
        setTradesError(err instanceof Error ? err.message : 'Failed to load trades');
      } finally {
        setTradesLoading(false);
      }
    };

    fetchTrades();
  }, [runId, activeTab, tradesLoadedState, detailSyncCursor]);

  useEffect(() => {
    if (!runId) return;

    const liveStatus = normalizeStatus(progressQuery.data?.status);
    if (
      liveStatus !== 'completed' &&
      liveStatus !== 'failed' &&
      liveStatus !== 'timeout' &&
      liveStatus !== 'timed_out' &&
      liveStatus !== 'stale' &&
      liveStatus !== 'stalled' &&
      liveStatus !== 'cancelled'
    ) {
      return;
    }
    if (liveStatus === normalizeStatus(backtest?.status)) {
      return;
    }

    let cancelled = false;

    const syncFinalBacktest = async () => {
      try {
        const response = await api.getBacktest(runId);
        if (!cancelled) {
          setBacktest((response?.data || response) as unknown as BacktestResponse);
        }
      } catch (err) {
        console.warn('Failed to sync final backtest details:', err);
      }
    };

    void syncFinalBacktest();

    return () => {
      cancelled = true;
    };
  }, [backtest?.status, progressQuery.data?.status, runId]);

  useEffect(() => {
    const event = progressQuery.lastSocketEvent as SocketLogPayload | null;
    if (!event) return;

    const message =
      typeof event.message === 'string' && event.message.trim().length > 0
        ? event.message.trim()
        : typeof event.current_task === 'string' && typeof event.current_pair === 'string'
          ? `${event.current_task}: ${event.current_pair}`
          : typeof event.current_pair === 'string'
            ? `Scanning: ${event.current_pair}`
            : typeof event.status === 'string'
              ? `Status: ${event.status}`
              : null;

    if (!message) return;

    const level = typeof event.level === 'string' ? event.level.toLowerCase() : 'info';
    const createdAt =
      typeof event.timestamp === 'string' && event.timestamp.length > 0
        ? event.timestamp
        : new Date().toISOString();

    setLiveLogs((previous) => {
      if (previous[0] && previous[0].message === message && previous[0].level === level) {
        const updated = [...previous];
        updated[0] = { ...updated[0], created_at: createdAt };
        return updated;
      }

      liveLogCounterRef.current += 1;
      const nextEntry: BacktestLogEntry = {
        id: liveLogCounterRef.current,
        message,
        level,
        created_at: createdAt,
      };
      return [nextEntry, ...previous].slice(0, 8);
    });
  }, [progressQuery.lastSocketEvent]);

  // Filter candles for selected market
  const selectedCandles = useMemo(
    () => candles.filter((c) => c.market === selectedMarket),
    [candles, selectedMarket]
  );
  const selectedChartPoints = useMemo<BacktestChartPoint[]>(
    () =>
      selectedCandles.map((candle, index) => {
        const previous = index > 0 ? selectedCandles[index - 1] : null;
        return {
          time: candle.timestamp,
          value: candle.close,
          pnl: previous ? candle.close - previous.close : candle.close,
          trades: Math.max(0, Math.round(candle.volume)),
        };
      }),
    [selectedCandles]
  );
  const filteredChartPoints = useMemo(
    () => filterChartPointsByRange(selectedChartPoints, chartRange),
    [chartRange, selectedChartPoints]
  );
  const filteredChartMarkers = useMemo(
    () =>
      chartMarkers.filter((marker) => {
        const matchesMarket =
          !selectedMarket ||
          marker.pair === selectedMarket ||
          marker.pair.includes(selectedMarket) ||
          selectedMarket.includes(marker.pair);

        if (!matchesMarket) {
          return false;
        }

        if (chartRange === 'ALL') {
          return true;
        }

        const markerDate = new Date(`${marker.time.slice(0, 10)}T00:00:00Z`);
        const latestPoint = filteredChartPoints[filteredChartPoints.length - 1];
        if (!latestPoint || Number.isNaN(markerDate.getTime())) {
          return false;
        }
        const latestDate = new Date(`${latestPoint.time}T00:00:00Z`);
        if (Number.isNaN(latestDate.getTime())) {
          return false;
        }
        const lookbackDays = CHART_RANGE_DAYS[chartRange];
        const cutoff = latestDate.getTime() - lookbackDays * 24 * 60 * 60 * 1000;
        return markerDate.getTime() >= cutoff;
      }),
    [chartMarkers, chartRange, filteredChartPoints, selectedMarket]
  );

  if (loading) {
    return (
      <PageContainer size="wide" className="flex min-h-[60vh] items-center justify-center">
        <Loader className="h-8 w-8 animate-spin text-blue-500" />
      </PageContainer>
    );
  }

  if (error || !backtest) {
    return (
      <PageContainer size="wide" className="flex min-h-[60vh] items-center justify-center">
        <div className="text-center text-red-500">
          <p className="text-xl font-bold mb-2">Error</p>
          <p>{error || 'Backtest not found'}</p>
        </div>
      </PageContainer>
    );
  }

  const liveRecord = asRecord(progressQuery.data);
  const liveBacktest: BacktestResponse = {
    ...backtest,
    status:
      typeof liveRecord?.status === 'string' && liveRecord.status.trim().length > 0
        ? liveRecord.status
        : backtest.status,
    progress_percent:
      firstFiniteNumber(
        liveRecord?.progress_percent,
        liveRecord?.progress_pct,
        liveRecord?.progress,
        backtest.progress_percent,
        backtest.progress_pct,
        backtest.progress
      ) ?? 0,
    progress_pct:
      firstFiniteNumber(
        liveRecord?.progress_pct,
        liveRecord?.progress_percent,
        liveRecord?.progress,
        backtest.progress_pct,
        backtest.progress_percent,
        backtest.progress
      ) ?? 0,
    progress:
      firstFiniteNumber(
        liveRecord?.progress,
        liveRecord?.progress_percent,
        liveRecord?.progress_pct,
        backtest.progress,
        backtest.progress_percent,
        backtest.progress_pct
      ) ?? 0,
    total_pnl:
      firstFiniteNumber(liveRecord?.total_pnl, backtest.total_pnl, backtest.total_pnl_usd) ?? 0,
    total_pnl_usd:
      firstFiniteNumber(liveRecord?.total_pnl, backtest.total_pnl_usd, backtest.total_pnl) ?? 0,
    total_trades:
      firstFiniteNumber(liveRecord?.total_trades, backtest.total_trades, trades.length) ??
      trades.length,
    win_rate: firstFiniteNumber(liveRecord?.win_rate, backtest.win_rate) ?? 0,
    sharpe_ratio: firstFiniteNumber(liveRecord?.sharpe_ratio, backtest.sharpe_ratio) ?? 0,
    max_drawdown_pct:
      firstFiniteNumber(
        liveRecord?.max_drawdown_pct,
        backtest.max_drawdown_pct,
        backtest.max_drawdown
      ) ?? 0,
    max_drawdown:
      firstFiniteNumber(
        liveRecord?.max_drawdown_pct,
        backtest.max_drawdown,
        backtest.max_drawdown_pct
      ) ?? 0,
    profit_factor:
      firstFiniteNumber(liveRecord?.profit_factor, backtest.profit_factor) ??
      backtest.profit_factor,
    error: firstMeaningfulString(liveRecord?.error, backtest.error) ?? backtest.error ?? undefined,
    error_message:
      firstMeaningfulString(liveRecord?.error_message, backtest.error_message) ??
      backtest.error_message ??
      undefined,
    cancellable: Boolean(liveRecord?.cancellable ?? backtest.cancellable),
    pausable: Boolean(liveRecord?.pausable ?? backtest.pausable),
    resumable: Boolean(liveRecord?.resumable ?? backtest.resumable),
    restartable: Boolean(liveRecord?.restartable ?? backtest.restartable ?? true),
    control_status:
      firstMeaningfulString(liveRecord?.control_status, backtest.control_status) ??
      backtest.control_status,
    control_action:
      firstMeaningfulString(liveRecord?.control_action, backtest.control_action) ??
      backtest.control_action,
    worker_backend:
      firstMeaningfulString(liveRecord?.worker_backend, backtest.worker_backend) ??
      backtest.worker_backend,
    request: asRecord(liveRecord?.request) || backtest.request,
    strategy_id:
      firstFiniteNumber(liveRecord?.strategy_id, backtest.strategy_id) ?? backtest.strategy_id,
    strategy_snapshot: asRecord(liveRecord?.strategy_snapshot) || backtest.strategy_snapshot,
  };

  const liveStatusNorm = normalizeStatus(progressQuery.data?.status);
  const statusNorm = normalizeStatus(liveBacktest.status) || liveStatusNorm || backtestStatus;
  const isPaused = statusNorm === 'paused';
  const isRunning =
    statusNorm === 'running' ||
    statusNorm === 'pending' ||
    statusNorm === 'queued' ||
    statusNorm === 'created';
  const isCompleted = statusNorm === 'completed';
  const isFailed =
    statusNorm === 'failed' ||
    statusNorm === 'timeout' ||
    statusNorm === 'timed_out' ||
    statusNorm === 'stale' ||
    statusNorm === 'stalled' ||
    statusNorm === 'cancelled';
  const metadataProgress = firstFiniteNumber(
    liveBacktest.progress_percent,
    liveBacktest.progress_pct,
    liveBacktest.progress
  );
  const liveProgress = progressQuery.progressPercent;
  const baseProgress =
    liveProgress > 0
      ? liveProgress
      : metadataProgress !== null && metadataProgress > 0
        ? metadataProgress
        : liveProgress;
  const rawProgressPercent = Math.min(100, Math.max(0, baseProgress));
  const isProgressVisible =
    isRunning || (!isCompleted && !isFailed && rawProgressPercent > 0 && rawProgressPercent < 100);
  const progressPercent = isCompleted ? 100 : rawProgressPercent;
  const currentPair = progressQuery.currentPair;
  const explicitScanningLine = liveLogs.find((log) =>
    /(^|\b)scanning\s*:/i.test(log.message)
  )?.message;
  const latestTaskFromLogs =
    explicitScanningLine ||
    liveLogs.find((log) => /(scan|processing|pair|market|running)/i.test(log.message))?.message;
  const currentTaskLine = latestTaskFromLogs || (currentPair ? `Scanning: ${currentPair}` : null);
  const etaLabel =
    typeof progressQuery.etaSeconds === 'number'
      ? formatDurationFromSeconds(progressQuery.etaSeconds)
      : null;
  const progressSourceLabel = formatBacktestProgressSourceLabel(progressQuery.progressSource);
  const streamBadge = resolveBacktestStreamBadge(
    progressQuery.progressSource,
    Boolean(progressQuery.isConnected)
  );
  const totalPnl = liveBacktest.total_pnl_usd ?? liveBacktest.total_pnl ?? 0;
  const maxDrawdown = liveBacktest.max_drawdown ?? liveBacktest.max_drawdown_pct ?? 0;
  const winRatePercent = normalizePercentValue(liveBacktest.win_rate);
  const failureReason = firstMeaningfulString(liveBacktest.error_message, liveBacktest.error);
  const failureDiagnostic = classifyFailureDiagnostic(failureReason);
  const latestCheckTimestamp =
    (typeof progressQuery.data?.checked_at === 'string' ? progressQuery.data.checked_at : null) ||
    (typeof progressQuery.lastSocketEvent?.timestamp === 'string'
      ? progressQuery.lastSocketEvent.timestamp
      : null);
  const latestRunUpdateTimestamp =
    (typeof progressQuery.data?.updated_at === 'string' ? progressQuery.data.updated_at : null) ||
    liveBacktest.updated_at ||
    null;
  const latestProgressTimestamp =
    latestCheckTimestamp ||
    latestRunUpdateTimestamp ||
    (typeof progressQuery.lastSocketEvent?.timestamp === 'string'
      ? progressQuery.lastSocketEvent.timestamp
      : null) ||
    null;
  const filteredChartStart = filteredChartPoints[0];
  const filteredChartEnd = filteredChartPoints[filteredChartPoints.length - 1];
  const periodPnl =
    filteredChartStart && filteredChartEnd
      ? filteredChartEnd.value - filteredChartStart.value
      : totalPnl;
  const periodReturnPct =
    filteredChartStart && Math.abs(filteredChartStart.value) > 0
      ? (periodPnl / Math.abs(filteredChartStart.value)) * 100
      : 0;
  const peakEquity =
    filteredChartPoints.length > 0
      ? Math.max(...filteredChartPoints.map((point) => point.value))
      : totalPnl;
  const troughEquity =
    filteredChartPoints.length > 0
      ? Math.min(...filteredChartPoints.map((point) => point.value))
      : totalPnl;
  const bestSessionPnl =
    filteredChartPoints.length > 0 ? Math.max(...filteredChartPoints.map((point) => point.pnl)) : 0;
  const worstSessionPnl =
    filteredChartPoints.length > 0 ? Math.min(...filteredChartPoints.map((point) => point.pnl)) : 0;
  const averageTradesPerBar =
    filteredChartPoints.length > 0
      ? filteredChartPoints.reduce((sum, point) => sum + point.trades, 0) /
        filteredChartPoints.length
      : 0;
  const pairBreakdown = filteredChartMarkers.reduce<
    Array<{ pair: string; count: number; pnl: number }>
  >((acc, marker) => {
    const existing = acc.find((item) => item.pair === marker.pair);
    if (existing) {
      existing.count += marker.count || 1;
      existing.pnl += marker.pnl;
    } else {
      acc.push({
        pair: marker.pair,
        count: marker.count || 1,
        pnl: marker.pnl,
      });
    }
    return acc;
  }, []);
  const topPairs = pairBreakdown.sort((a, b) => b.count - a.count || b.pnl - a.pnl).slice(0, 5);
  const requestPayload = asRecord(liveBacktest.request);
  const requestTaskContext = asRecord(requestPayload?._task_context);
  const requestMetadata = asRecord(requestTaskContext?.metadata);
  const historyFetchTelemetry = asRecord(requestMetadata?.history_fetch_telemetry);
  const historyFetchMarketsRecord = asRecord(historyFetchTelemetry?.markets);
  const historyFetchTotalWindows = toNumber(historyFetchTelemetry?.total_windows, 0);
  const historyFetchTotalRetries = toNumber(historyFetchTelemetry?.total_retries, 0);
  const historyFetchTotalFailedWindows = toNumber(historyFetchTelemetry?.total_failed_windows, 0);
  const historyFetchTotalBackoffSeconds = toNumber(historyFetchTelemetry?.total_backoff_seconds, 0);
  const historyFetchAvgBackoffSeconds = toNumber(
    historyFetchTelemetry?.avg_backoff_per_retry_seconds,
    0
  );
  const historyFetchRetryRatePct =
    historyFetchTotalWindows > 0 ? (historyFetchTotalRetries / historyFetchTotalWindows) * 100 : 0;
  const historyFetchFailureRatePct =
    historyFetchTotalWindows > 0
      ? (historyFetchTotalFailedWindows / historyFetchTotalWindows) * 100
      : 0;
  const retryPressureScore = clampPercentage(
    historyFetchRetryRatePct * 0.55 +
      historyFetchFailureRatePct * 0.9 +
      Math.min(12, historyFetchAvgBackoffSeconds * 3)
  );
  const retryPressureTone =
    retryPressureScore < 30
      ? 'text-emerald-300'
      : retryPressureScore < 60
        ? 'text-amber-300'
        : 'text-rose-300';
  const retryPressureLabel =
    retryPressureScore < 30
      ? 'Low pressure'
      : retryPressureScore < 60
        ? 'Moderate pressure'
        : 'High pressure';
  const historyFetchMarketRows = historyFetchMarketsRecord
    ? Object.entries(historyFetchMarketsRecord)
        .map(([market, telemetry]) => {
          const telemetryRecord = asRecord(telemetry);
          return {
            market,
            retries: toNumber(telemetryRecord?.retries, 0),
            windows: toNumber(telemetryRecord?.windows, 0),
            failedWindows: toNumber(telemetryRecord?.failed_windows, 0),
            avgBackoff: toNumber(telemetryRecord?.avg_backoff_per_retry_seconds, 0),
          };
        })
        .sort(
          (left, right) =>
            right.retries - left.retries ||
            right.failedWindows - left.failedWindows ||
            right.windows - left.windows
        )
        .slice(0, 6)
    : ([] as Array<{
        market: string;
        retries: number;
        windows: number;
        failedWindows: number;
        avgBackoff: number;
      }>);
  const hasHistoryFetchTelemetry =
    historyFetchTelemetry !== null &&
    (historyFetchTotalWindows > 0 ||
      historyFetchTotalRetries > 0 ||
      historyFetchMarketRows.length > 0);
  const requestParams = asRecord(requestPayload?.trading_parameters);
  const requestedPairs = Array.isArray(requestPayload?.pairs)
    ? requestPayload.pairs.map((pair) => String(pair)).filter(Boolean)
    : [];
  const selectedMarketsForRuntime =
    requestedPairs.length > 0
      ? requestedPairs
      : markets.length > 0
        ? markets
        : Array.from(
            new Set(
              trades
                .flatMap((trade) => [trade.market_1, trade.market_2])
                .filter((market) => market && market !== '-')
            )
          );
  const initialCapital = Math.max(
    1,
    firstFiniteNumber(
      requestPayload?.initial_balance,
      requestParams?.starting_balance,
      requestParams?.initial_amount
    ) ?? 1000
  );
  const avgPnlPerTrade =
    trades.length > 0 ? trades.reduce((sum, trade) => sum + trade.pnl_usd, 0) / trades.length : 0;
  const avgTradeDurationHours =
    trades.length > 0
      ? trades.reduce((sum, trade) => sum + Math.max(0, trade.duration_hours), 0) / trades.length
      : 0;
  const grossProfit = trades
    .filter((trade) => trade.pnl_usd > 0)
    .reduce((sum, trade) => sum + trade.pnl_usd, 0);
  const grossLoss = Math.abs(
    trades.filter((trade) => trade.pnl_usd < 0).reduce((sum, trade) => sum + trade.pnl_usd, 0)
  );
  const computedProfitFactor =
    liveBacktest.profit_factor ??
    (grossLoss > 0 ? grossProfit / grossLoss : grossProfit > 0 ? grossProfit : 0);
  const capitalEfficiencyPct = (totalPnl / initialCapital) * 100;
  const topPairAbsPnl = topPairs.length > 0 ? Math.abs(topPairs[0].pnl) : 0;
  const aggregatePairAbsPnl = pairBreakdown.reduce((sum, pair) => sum + Math.abs(pair.pnl), 0);
  const pairConcentrationPct =
    aggregatePairAbsPnl > 0 ? (topPairAbsPnl / aggregatePairAbsPnl) * 100 : 0;
  const edgeQualityScore = Math.max(
    0,
    Math.min(
      100,
      computedProfitFactor * 18 +
        Math.max(0, liveBacktest.sharpe_ratio || 0) * 12 +
        winRatePercent * 0.35 -
        Math.max(0, maxDrawdown) * 0.8 -
        Math.max(0, pairConcentrationPct - 45) * 0.35
    )
  );
  const candidatePairs =
    selectedMarketsForRuntime.length > 1
      ? (selectedMarketsForRuntime.length * (selectedMarketsForRuntime.length - 1)) / 2
      : pairBreakdown.length;
  const arbScorecards = [
    {
      label: 'Arb Edge Score',
      value: `${edgeQualityScore.toFixed(0)}/100`,
      detail: 'Profit factor, Sharpe, win rate, drawdown, concentration',
      icon: ShieldCheck,
      pct: edgeQualityScore,
      tone: edgeQualityScore >= 70 ? 'emerald' : edgeQualityScore >= 45 ? 'amber' : 'rose',
    },
    {
      label: 'Capital Efficiency',
      value: `${capitalEfficiencyPct >= 0 ? '+' : ''}${capitalEfficiencyPct.toFixed(2)}%`,
      detail: `${formatCurrency(totalPnl)} on ${formatCurrency(initialCapital)} test capital`,
      icon: Percent,
      pct: Math.min(100, Math.abs(capitalEfficiencyPct) * 5),
      tone: capitalEfficiencyPct >= 0 ? 'emerald' : 'rose',
    },
    {
      label: 'Pair Concentration',
      value: `${pairConcentrationPct.toFixed(1)}%`,
      detail: 'Share of absolute PnL from the leading pair',
      icon: Scale,
      pct: Math.min(100, pairConcentrationPct),
      tone: pairConcentrationPct <= 45 ? 'emerald' : pairConcentrationPct <= 65 ? 'amber' : 'rose',
    },
    {
      label: 'Execution Cadence',
      value: `${avgTradeDurationHours.toFixed(1)}h`,
      detail: `${formatSignedCurrency(avgPnlPerTrade)} average PnL per closed trade`,
      icon: Activity,
      pct: Math.min(100, Math.max(8, trades.length)),
      tone: avgPnlPerTrade >= 0 ? 'emerald' : 'rose',
    },
    {
      label: 'Market Coverage',
      value: `${selectedMarketsForRuntime.length} markets`,
      detail: `${candidatePairs} candidate pair${candidatePairs === 1 ? '' : 's'} for runtime discovery`,
      icon: Layers,
      pct: Math.min(100, selectedMarketsForRuntime.length * 5),
      tone: selectedMarketsForRuntime.length >= 5 ? 'emerald' : 'amber',
    },
  ];
  const isSummaryDense = summaryDensity === 'dense';

  const renderEmptyState = (label: string): React.ReactNode => {
    if (isRunning) {
      return (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <Loader className="w-6 h-6 animate-spin text-blue-400" />
          <p className="text-slate-400 text-center text-sm">
            The backtest is in progress — {label} will appear here once pairs finish processing.
          </p>
        </div>
      );
    }
    if (isFailed) {
      return (
        <div className="flex flex-col items-center justify-center py-16 gap-2">
          <p className="text-red-400 font-medium capitalize">Backtest {statusNorm}</p>
          <p className="text-slate-500 text-sm">
            The run ended before generating {label} data. Review the failure diagnostic panel above.
          </p>
          {failureReason && (
            <p className="max-w-2xl text-center text-xs text-red-300">{failureReason}</p>
          )}
        </div>
      );
    }
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-2">
        <p className="text-slate-400 font-medium">No {label} found</p>
        <p className="text-slate-500 text-sm">
          This backtest completed but produced no {label} records.
        </p>
      </div>
    );
  };

  const metrics = [
    {
      label: 'Total Trades',
      value: liveBacktest.total_trades ?? trades.length,
      detail: `${formatCompactValue(averageTradesPerBar)} avg / bar`,
      icon: Activity,
    },
    {
      label: 'Win Rate',
      value: `${winRatePercent.toFixed(1)}%`,
      detail: isRunning ? 'Updating live' : 'Finalized',
      icon: Gauge,
    },
    {
      label: 'Total PnL',
      value: formatCurrency(totalPnl),
      detail: `${periodPnl >= 0 ? '+' : ''}${periodReturnPct.toFixed(2)}% selected range`,
      icon: TrendingUp,
      color: totalPnl >= 0 ? 'text-green-400' : 'text-red-400',
    },
    {
      label: 'Sharpe Ratio',
      value:
        liveBacktest.sharpe_ratio !== undefined && liveBacktest.sharpe_ratio !== null
          ? liveBacktest.sharpe_ratio.toFixed(2)
          : 'N/A',
      detail: `PF ${
        liveBacktest.profit_factor !== undefined && liveBacktest.profit_factor !== null
          ? liveBacktest.profit_factor.toFixed(2)
          : 'N/A'
      }`,
      icon: Radar,
    },
    {
      label: 'Max Drawdown',
      value: `${maxDrawdown.toFixed(1)}%`,
      detail: `Low watermark ${formatCurrency(troughEquity)}`,
      icon: TrendingDown,
    },
    {
      label: 'Live Sync',
      value: progressQuery.isConnected ? 'Streaming' : 'Recovering',
      detail: formatTimeAgo(latestProgressTimestamp),
      icon: Waves,
      color: progressQuery.isConnected ? 'text-cyan-300' : 'text-amber-300',
    },
    {
      label: 'Stats Integrity',
      value: `${
        [
          Number.isFinite(totalPnl),
          Number.isFinite(winRatePercent),
          Number.isFinite(liveBacktest.sharpe_ratio),
          Number.isFinite(maxDrawdown),
        ].filter(Boolean).length * 25
      }%`,
      detail: `${
        [
          Number.isFinite(totalPnl),
          Number.isFinite(winRatePercent),
          Number.isFinite(liveBacktest.sharpe_ratio),
          Number.isFinite(maxDrawdown),
        ].filter(Boolean).length
      }/4 core signals validated`,
      icon: ShieldCheck,
      color:
        [
          Number.isFinite(totalPnl),
          Number.isFinite(winRatePercent),
          Number.isFinite(liveBacktest.sharpe_ratio),
          Number.isFinite(maxDrawdown),
        ].filter(Boolean).length === 4
          ? 'text-emerald-300'
          : 'text-amber-300',
    },
  ];

  const tabMetadata = {
    summary: {
      countLabel: 'Overview',
      isLoading: false,
    },
    candles: {
      countLabel: `${filteredChartPoints.length} bars`,
      isLoading: analyticsLoading,
    },
    positions: {
      countLabel: `${positions.length} rows`,
      isLoading: positionsLoading,
    },
    trades: {
      countLabel: `${liveBacktest.total_trades ?? trades.length} trades`,
      isLoading: tradesLoading,
    },
    results: {
      countLabel: `${pairBreakdown.length} pairs`,
      isLoading: false,
    },
  } as const;

  const runControlStatus = normalizeStatus(liveBacktest.control_status);
  const controlBusy = controlAction !== null;
  const canPause =
    Boolean(runId) &&
    !controlBusy &&
    (liveBacktest.pausable || isRunning) &&
    runControlStatus !== 'pause_requested';
  const canResume =
    Boolean(runId) &&
    !controlBusy &&
    (liveBacktest.resumable || isPaused || runControlStatus === 'pause_requested');
  const canCancel =
    Boolean(runId) &&
    !controlBusy &&
    !isCompleted &&
    !isFailed &&
    (liveBacktest.cancellable || isRunning || isPaused);
  const canRestart =
    Boolean(runId) &&
    !controlBusy &&
    (liveBacktest.restartable || isFailed || isCompleted || isPaused);
  const canRetry = Boolean(runId) && !controlBusy && isFailed;

  const handleBacktestControl = async (
    action: 'pause' | 'resume' | 'cancel' | 'restart' | 'retry'
  ) => {
    if (!runId) return;

    setControlAction(action);
    setControlError(null);

    const runFromPersistedRequest = async () => {
      const requestPayload = asRecord(liveBacktest.request);
      if (!requestPayload) {
        throw new Error('Original backtest request is unavailable');
      }
      const cleanRequest = { ...requestPayload };
      delete cleanRequest._runtime_control;
      cleanRequest.source = 'backtest-rerun';
      const response = await api.runBacktest(
        cleanRequest as { start_date: string; end_date: string } & Record<string, unknown>
      );
      const payload = asRecord(response?.data || response);
      const newRunId = toStringValue(payload?.run_id);
      if (!newRunId) {
        throw new Error('Retry started but did not return a run id');
      }
      navigate(`/backtest/${newRunId}`);
    };

    try {
      const response =
        action === 'pause'
          ? await api.pauseBacktest(runId)
          : action === 'resume'
            ? await api.resumeBacktest(runId)
            : action === 'cancel'
              ? await api.cancelBacktest(runId)
              : action === 'restart'
                ? await api.restartBacktest(runId)
                : await api.retryBacktest(runId);

      const payload = asRecord(response?.data || response);
      const newRunId = toStringValue(payload?.new_run_id);
      if ((action === 'restart' || action === 'retry') && newRunId) {
        navigate(`/backtest/${newRunId}`);
        return;
      }

      await fetchBacktestMetadata(false);
    } catch (err: unknown) {
      const response = asRecord(asRecord(err)?.response);
      const statusCode = toNumber(response?.status, 0);
      const responseData = asRecord(response?.data);
      const conflictMessage = firstMeaningfulString(
        responseData?.message,
        responseData?.error,
        responseData?.detail,
        (err as { message?: unknown } | null)?.message
      );

      if ((action === 'restart' || action === 'retry') && statusCode === 409) {
        await fetchBacktestMetadata(false);
        setControlError(
          conflictMessage ||
            `This run changed state while we processed your request. We refreshed the latest status—please retry the same action if needed.`
        );
        return;
      }

      if ((action === 'restart' || action === 'retry') && statusCode === 404) {
        try {
          await runFromPersistedRequest();
          return;
        } catch (fallbackErr: unknown) {
          const fallbackMsg =
            fallbackErr instanceof Error
              ? `We couldn't continue with ${action} from the saved request: ${fallbackErr.message}`
              : `We couldn't continue with ${action} from the saved request right now.`;
          setControlError(fallbackMsg);
          return;
        }
      }
      const msg =
        err instanceof Error
          ? `We couldn't ${action} this backtest right now. ${err.message}`
          : `We couldn't ${action} this backtest right now.`;
      setControlError(msg);
    } finally {
      setControlAction(null);
    }
  };

  const buildStrategyConfigFromBacktest = (): Record<string, unknown> => {
    const snapshot = asRecord(liveBacktest.strategy_snapshot);
    const config: Record<string, unknown> = snapshot ? { ...snapshot } : {};

    if (requestParams) {
      Object.entries(requestParams).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          config[key] = value;
        }
      });
    }

    if (selectedMarketsForRuntime.length > 0) {
      config.selected_markets = selectedMarketsForRuntime;
    }
    if (requestPayload?.initial_balance !== undefined) {
      config.starting_balance = requestPayload.initial_balance;
      config.initial_amount = requestPayload.initial_balance;
    }
    config.runtime_network = runtimeNetwork;
    config.runtime_strategy = config.runtime_strategy || 'cointegration';
    config.pair_selection_mode =
      requestPayload?.pair_selection_mode || config.pair_selection_mode || 'liquidity';
    config.source_backtest_run_id = runId;
    if (liveBacktest.strategy_id) {
      config.source_strategy_id = liveBacktest.strategy_id;
    }

    return config;
  };

  const createStrategyFromCurrentBacktest = async (): Promise<number> => {
    if (!runId) {
      throw new Error('Backtest run id is unavailable');
    }
    const response = await api.createStrategyFromBacktest({
      backtest_run_id: runId,
      name: `Live candidate - ${runId.slice(0, 8)}`,
      description: `Promoted from backtest ${runId}`,
      config: buildStrategyConfigFromBacktest(),
    });
    const data = asRecord(response.data);
    const strategyId = firstFiniteNumber(data?.id, data?.strategy_id);
    if (!strategyId) {
      throw new Error('Strategy was created but no strategy id was returned');
    }
    setBacktest((current) => (current ? { ...current, strategy_id: strategyId } : current));
    return strategyId;
  };

  const handlePromoteBacktest = async (startRuntime: boolean) => {
    setPromotionAction(startRuntime ? 'start' : 'create');
    setPromotionError(null);
    setPromotionMessage(null);

    try {
      const existingStrategyId = firstFiniteNumber(liveBacktest.strategy_id);
      const strategyId =
        startRuntime && existingStrategyId
          ? existingStrategyId
          : await createStrategyFromCurrentBacktest();

      if (startRuntime) {
        const readiness = await api.getStrategyStartReadiness(strategyId, runtimeNetwork);
        if (readiness.data && readiness.data.ready === false) {
          const blockers = Array.isArray(readiness.data.blockers)
            ? readiness.data.blockers.join(' ')
            : 'Runtime readiness check failed';
          throw new Error(blockers || 'Runtime readiness check failed');
        }
        const runtime = await api.startStrategyRuntime(strategyId, runtimeNetwork);
        const runtimeData = asRecord(runtime.data);
        setPromotionMessage(
          `Live bot started for strategy #${strategyId}${
            runtimeData?.instance_id ? ` (${runtimeData.instance_id})` : ''
          }.`
        );
      } else {
        setPromotionMessage(`Strategy #${strategyId} created from this backtest.`);
      }

      try {
        const strategyResponse = await api.getStrategy(strategyId);
        setLinkedStrategy((strategyResponse.data as StrategySummary | undefined) ?? null);
      } catch {
        setLinkedStrategy(null);
      }
    } catch (err: unknown) {
      setPromotionError(err instanceof Error ? err.message : 'Unable to promote this backtest');
    } finally {
      setPromotionAction(null);
    }
  };

  const renderDeferredTabHint = (label: string): React.ReactNode => (
    <div className="flex flex-col items-center justify-center py-16 gap-2">
      <p className="text-slate-300 font-medium">{label} are loaded on demand</p>
      <p className="text-center text-sm text-slate-500 max-w-xl">
        {isRunning
          ? 'Live — new rows appear as pairs finish processing.'
          : 'Data loads on demand. Open this tab after the run completes to fetch the full dataset.'}
      </p>
    </div>
  );

  return (
    <PageContainer size="wide" className="space-y-6 text-white">
      <div className="light-dark-surface rounded-[28px] border border-slate-800 bg-[radial-gradient(circle_at_top_left,rgba(34,197,94,0.10),transparent_24%),radial-gradient(circle_at_top_right,rgba(56,189,248,0.14),transparent_28%),linear-gradient(180deg,rgba(15,23,42,0.98),rgba(2,6,23,0.98))] p-5 shadow-[0_20px_80px_rgba(2,6,23,0.45)] sm:p-7">
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-cyan-200">
                  Backtest Lab
                </span>
                <span
                  className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${
                    statusNorm === 'completed'
                      ? 'bg-emerald-500/15 text-emerald-200'
                      : statusNorm === 'running'
                        ? 'bg-blue-500/15 text-blue-200'
                        : statusNorm === 'failed' ||
                            statusNorm === 'timeout' ||
                            statusNorm === 'timed_out' ||
                            statusNorm === 'stale' ||
                            statusNorm === 'stalled' ||
                            statusNorm === 'cancelled'
                          ? 'bg-rose-500/15 text-rose-200'
                          : 'bg-amber-500/15 text-amber-200'
                  }`}
                >
                  {statusNorm}
                </span>
                <LiveStateBadge
                  tone={streamBadge.tone}
                  label={streamBadge.label}
                  className="rounded-full px-3 py-1 normal-case"
                />
              </div>
              <div>
                <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-5xl">
                  Backtest Control Room
                </h1>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400 sm:text-base">
                  Monitor live execution, inspect the equity curve, and drill into pair-level
                  outcome data without leaving the page or waiting on hard refreshes.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-slate-300">
                <span className="inline-flex items-center gap-2">
                  <CalendarRange className="h-4 w-4 text-slate-500" />
                  {backtest.start_date || 'N/A'} to {backtest.end_date || 'N/A'}
                </span>
                <span className="inline-flex items-center gap-2">
                  <Clock3 className="h-4 w-4 text-slate-500" />
                  Last sync {formatTimeAgo(latestProgressTimestamp)}
                </span>
                <span className="inline-flex items-center gap-2">
                  <CircleDot
                    className={`h-4 w-4 ${progressQuery.isConnected ? 'text-cyan-400' : 'text-amber-400'}`}
                  />
                  Source {progressSourceLabel}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-2 pt-2">
                <span className="rounded-full border border-slate-700 bg-slate-950/70 px-3 py-1 text-xs text-slate-400">
                  Worker {liveBacktest.worker_backend || 'asyncio'}
                </span>
                <button
                  type="button"
                  onClick={() => handleBacktestControl('pause')}
                  disabled={!canPause}
                  className="inline-flex items-center gap-2 rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-xs font-medium text-cyan-100 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <Pause className="h-4 w-4" />
                  {controlAction === 'pause' ? 'Pausing' : 'Pause'}
                </button>
                <button
                  type="button"
                  onClick={() => handleBacktestControl('resume')}
                  disabled={!canResume}
                  className="inline-flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs font-medium text-emerald-100 transition hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <Play className="h-4 w-4" />
                  {controlAction === 'resume' ? 'Resuming' : 'Resume'}
                </button>
                <button
                  type="button"
                  onClick={() => handleBacktestControl('cancel')}
                  disabled={!canCancel}
                  className="inline-flex items-center gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs font-medium text-rose-100 transition hover:bg-rose-500/20 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <Square className="h-4 w-4" />
                  {controlAction === 'cancel' ? 'Stopping' : 'Stop'}
                </button>
                <button
                  type="button"
                  onClick={() => handleBacktestControl('restart')}
                  disabled={!canRestart}
                  className="inline-flex items-center gap-2 rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-xs font-medium text-slate-100 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <RotateCcw className="h-4 w-4" />
                  {controlAction === 'restart' ? 'Restarting' : 'Restart'}
                </button>
                {canRetry && (
                  <button
                    type="button"
                    onClick={() => handleBacktestControl('retry')}
                    disabled={controlBusy}
                    className="inline-flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs font-medium text-amber-100 transition hover:bg-amber-500/20 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    <RotateCcw className="h-4 w-4" />
                    {controlAction === 'retry' ? 'Retrying' : 'Retry'}
                  </button>
                )}
                {controlError && (
                  <span className="text-xs font-medium text-rose-300">{controlError}</span>
                )}
              </div>
            </div>

            <div className="grid min-w-full grid-cols-2 gap-3 sm:min-w-90 xl:max-w-105">
              <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Run ID</p>
                <p className="mt-2 break-all font-mono text-sm text-slate-100">{backtest.run_id}</p>
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                  Current Pair
                </p>
                <p className="mt-2 text-sm font-medium text-slate-100">
                  {currentPair || selectedMarket || 'Awaiting signal'}
                </p>
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                  Peak Equity
                </p>
                <p
                  className={`mt-2 text-lg font-semibold ${peakEquity >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}
                >
                  {formatSignedCurrency(peakEquity)}
                </p>
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                  Best Session
                </p>
                <p
                  className={`mt-2 text-lg font-semibold ${bestSessionPnl >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}
                >
                  {formatSignedCurrency(bestSessionPnl)}
                </p>
              </div>
            </div>
          </div>

          {isProgressVisible && (
            <div className="rounded-2xl border border-cyan-500/25 bg-cyan-500/10 p-4 sm:p-5">
              <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
                <div className="flex items-start gap-3">
                  <Loader className="mt-0.5 h-5 w-5 shrink-0 animate-spin text-cyan-300" />
                  <div>
                    <p className="font-medium text-cyan-200">Execution is live</p>
                    <p className="mt-1 text-sm text-slate-300">
                      Progress, live activity, and detailed datasets are updating in place while the
                      run advances through each pair.
                    </p>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <div className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2">
                    <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                      Progress
                    </p>
                    <p className="mt-1 text-base font-semibold text-slate-100">
                      {progressPercent.toFixed(1)}%
                    </p>
                  </div>
                  <div className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2">
                    <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">ETA</p>
                    <p className="mt-1 text-base font-semibold text-slate-100">
                      {etaLabel || 'Calibrating'}
                    </p>
                  </div>
                  <div className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2">
                    <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                      Markets
                    </p>
                    <p className="mt-1 text-base font-semibold text-slate-100">{markets.length}</p>
                  </div>
                  <div className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2">
                    <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                      Signals
                    </p>
                    <p className="mt-1 text-base font-semibold text-slate-100">
                      {filteredChartMarkers.length}
                    </p>
                  </div>
                </div>
              </div>
              <div className="mt-4">
                <div className="mb-1 flex items-center justify-between text-xs text-cyan-200">
                  <span>Execution Progress</span>
                  <span>{progressPercent.toFixed(1)}%</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                  <div
                    className="h-2 bg-[linear-gradient(90deg,#06b6d4,#3b82f6)] transition-all duration-500"
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-slate-300">
                  <span>
                    Task:{' '}
                    <span className="font-mono text-slate-100">
                      {currentTaskLine || 'Initializing runtime'}
                    </span>
                  </span>
                  {etaLabel && (
                    <span className="text-slate-400">
                      ETA: <span className="font-medium text-slate-200">{etaLabel}</span>
                    </span>
                  )}
                  <span className="text-slate-400">
                    Checked:{' '}
                    <span className="font-medium text-slate-200">
                      {formatTimeAgo(latestProgressTimestamp)}
                    </span>
                  </span>
                </div>
                {liveLogs.length > 0 && (
                  <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/65 p-3">
                    <p className="mb-2 text-[11px] uppercase tracking-[0.18em] text-slate-500">
                      Live Activity
                    </p>
                    <div className="max-h-28 space-y-1 overflow-y-auto">
                      {liveLogs.map((log) => (
                        <div key={`${log.id}-${log.created_at}`} className="text-xs text-slate-300">
                          <span className="mr-1 text-slate-500">
                            {new Date(log.created_at).toLocaleTimeString()}
                          </span>
                          <span
                            className={`mr-1 ${
                              log.level === 'error'
                                ? 'text-red-400'
                                : log.level === 'warning'
                                  ? 'text-yellow-400'
                                  : log.level === 'debug'
                                    ? 'text-blue-400'
                                    : 'text-green-400'
                            }`}
                          >
                            [{log.level.toUpperCase()}]
                          </span>
                          <span>{log.message}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
          {isFailed && (
            <div className="rounded-2xl border border-red-700 bg-red-900/40 p-4">
              <p className="font-medium capitalize text-red-300">Backtest {statusNorm}</p>
              <p className="mt-1 text-sm text-slate-400">
                This backtest did not complete successfully. No result data is available.
              </p>
              {failureReason && (
                <p className="mt-2 text-sm text-red-200">
                  Reason: <span className="wrap-break-word font-mono">{failureReason}</span>
                </p>
              )}
              {failureDiagnostic.category !== 'cancelled' && (
                <div className="mt-3 rounded-xl border border-red-700/60 bg-slate-950/45 p-3 text-xs text-slate-200">
                  <p className="uppercase tracking-[0.14em] text-red-300">Diagnostic category</p>
                  <p className="mt-1 font-semibold capitalize text-white">
                    {failureDiagnostic.category}
                  </p>
                  <p className="mt-2 text-slate-300">Next step: {failureDiagnostic.hint}</p>
                </div>
              )}
            </div>
          )}
          {isCompleted && (
            <div className="rounded-2xl border border-emerald-700/50 bg-emerald-950/20 p-4">
              <p className="font-medium text-emerald-300">Run finalized</p>
              <p className="mt-1 text-sm text-slate-300">
                Performance, trades, positions, and pair aggregates remain available in the tabs
                below with no extra navigation or manual reloads.
              </p>
            </div>
          )}

          <div className="rounded-2xl border border-slate-800 bg-slate-950/55 p-4 sm:p-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div className="max-w-3xl">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-cyan-300">
                  Strategy relationship
                </p>
                <h2 className="mt-1 text-xl font-semibold text-white">
                  {linkedStrategyId
                    ? linkedStrategy?.name || `Strategy #${linkedStrategyId}`
                    : 'Manual backtest ticket'}
                </h2>
                <p className="mt-2 text-sm leading-6 text-slate-400">
                  {linkedStrategyId
                    ? 'This backtest is linked to a saved strategy. Use the relationship to return to the strategy, create another validation run, or keep the report attached to the source setup.'
                    : 'This run was launched without a saved strategy relation. Save it as a strategy when the result is strong enough to reuse.'}
                </p>
                {linkedStrategyLoading && (
                  <p className="mt-2 text-xs text-slate-500">Loading strategy metadata...</p>
                )}
                {linkedStrategyError && (
                  <p className="mt-2 text-xs text-amber-300">{linkedStrategyError}</p>
                )}
              </div>

              <div className="grid min-w-full gap-2 sm:grid-cols-2 xl:min-w-105">
                <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-3 py-3">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Relation</p>
                  <p className="mt-1 text-sm font-semibold text-slate-100">
                    {linkedStrategyId ? `Strategy #${linkedStrategyId}` : 'Unlinked'}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-3 py-3">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Mode</p>
                  <p className="mt-1 text-sm font-semibold text-slate-100">
                    {linkedStrategyId ? 'Strategy-triggered' : 'Backtest-created'}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    linkedStrategyId
                      ? navigate(`/strategies/${linkedStrategyId}/edit`)
                      : void handlePromoteBacktest(false)
                  }
                  disabled={!linkedStrategyId && (promotionAction !== null || !isCompleted)}
                  className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-sm font-semibold text-cyan-100 transition hover:border-cyan-400/60 disabled:cursor-not-allowed disabled:opacity-45"
                >
                  {linkedStrategyId ? 'Open Strategy' : 'Create Strategy'}
                </button>
                <button
                  type="button"
                  onClick={() =>
                    linkedStrategyId
                      ? navigate(`/backtests/new?strategy_id=${linkedStrategyId}`)
                      : navigate('/backtests/new')
                  }
                  className="rounded-xl border border-slate-700 bg-slate-900/80 px-3 py-2 text-sm font-semibold text-slate-100 transition hover:border-slate-500"
                >
                  New Linked Backtest
                </button>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 2xl:grid-cols-3">
            {metrics.map((metric) => {
              const Icon = metric.icon;
              return (
                <div
                  key={metric.label}
                  className="rounded-2xl border border-slate-800 bg-slate-950/55 p-4 shadow-[0_8px_32px_rgba(2,6,23,0.22)]"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                        {metric.label}
                      </p>
                      <p
                        className={`mt-2 text-2xl font-semibold tracking-tight ${metric.color || 'text-slate-100'}`}
                      >
                        {metric.value}
                      </p>
                      <p className="mt-2 text-xs text-slate-400">{metric.detail}</p>
                    </div>
                    <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-2 text-cyan-200">
                      <Icon className="h-5 w-5" />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.45fr)_420px]">
            <div className="rounded-3xl border border-slate-800 bg-slate-950/50 p-4 sm:p-5">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <p className="text-[11px] font-semibold uppercase text-cyan-300">
                    DeFi arbitrage stack
                  </p>
                  <h2 className="mt-1 text-xl font-semibold text-white">
                    Runtime Readiness Metrics
                  </h2>
                </div>
                <p className="max-w-xl text-sm text-slate-400">
                  Built for pair-trading decisions: edge quality, capital efficiency, concentration
                  risk, cadence, and live market coverage.
                </p>
              </div>
              <div className="mt-5 grid gap-3 md:grid-cols-2 2xl:grid-cols-5">
                {arbScorecards.map((item) => {
                  const Icon = item.icon;
                  const toneClass =
                    item.tone === 'emerald'
                      ? 'text-emerald-300 bg-emerald-500'
                      : item.tone === 'amber'
                        ? 'text-amber-300 bg-amber-500'
                        : 'text-rose-300 bg-rose-500';
                  return (
                    <div
                      key={item.label}
                      className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-[10px] font-semibold uppercase text-slate-500">
                            {item.label}
                          </p>
                          <p className={`mt-2 text-lg font-semibold ${toneClass.split(' ')[0]}`}>
                            {item.value}
                          </p>
                        </div>
                        <div className="rounded-xl border border-slate-800 bg-slate-950 p-2 text-cyan-200">
                          <Icon className="h-4 w-4" />
                        </div>
                      </div>
                      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-800">
                        <div
                          className={`h-full ${toneClass.split(' ')[1]}`}
                          style={{ width: `${Math.min(100, Math.max(0, item.pct))}%` }}
                        />
                      </div>
                      <p className="mt-3 text-xs leading-5 text-slate-400">{item.detail}</p>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="rounded-3xl border border-cyan-500/25 bg-cyan-950/20 p-4 sm:p-5">
              <div className="flex items-start gap-3">
                <div className="rounded-2xl border border-cyan-500/30 bg-cyan-500/10 p-3 text-cyan-200">
                  <Bot className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-[11px] font-semibold uppercase text-cyan-300">
                    Promote to live
                  </p>
                  <h2 className="mt-1 text-xl font-semibold text-white">Create Runtime Strategy</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-300">
                    Save this backtest configuration as a strategy, then optionally start a managed
                    live bot with the same markets, risk limits, timeframe, and execution settings.
                  </p>
                </div>
              </div>
              <div className="mt-5 grid grid-cols-2 gap-3">
                <label className="col-span-2">
                  <span className="mb-2 block text-xs font-semibold uppercase text-slate-500">
                    Runtime network
                  </span>
                  <select
                    value={runtimeNetwork}
                    onChange={(event) =>
                      setRuntimeNetwork(event.target.value as 'testnet' | 'mainnet')
                    }
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-400"
                  >
                    <option value="testnet">Testnet</option>
                    <option value="mainnet">Mainnet</option>
                  </select>
                </label>
                <button
                  type="button"
                  onClick={() => void handlePromoteBacktest(false)}
                  disabled={promotionAction !== null || !isCompleted}
                  className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm font-semibold text-slate-200 transition hover:border-cyan-400 disabled:cursor-not-allowed disabled:opacity-45"
                >
                  <ShieldCheck className="h-4 w-4" />
                  {promotionAction === 'create' ? 'Creating' : 'Save Strategy'}
                </button>
                <button
                  type="button"
                  onClick={() => void handlePromoteBacktest(true)}
                  disabled={promotionAction !== null || !isCompleted}
                  className="inline-flex items-center justify-center gap-2 rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm font-semibold text-emerald-100 transition hover:border-emerald-300 disabled:cursor-not-allowed disabled:opacity-45"
                >
                  <Rocket className="h-4 w-4" />
                  {promotionAction === 'start' ? 'Starting' : 'Start Bot'}
                </button>
              </div>
              {!isCompleted ? (
                <p className="mt-3 text-xs text-amber-300">
                  Promotion unlocks after the backtest completes successfully.
                </p>
              ) : null}
              {promotionMessage ? (
                <p className="mt-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">
                  {promotionMessage}
                </p>
              ) : null}
              {promotionError ? (
                <p className="mt-3 rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
                  {promotionError}
                </p>
              ) : null}
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-800 bg-slate-950/65 px-3 py-2">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="overflow-x-auto">
            <div className="flex min-w-max gap-2">
              {BACKTEST_DETAIL_TABS.map((tab, index) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  aria-current={activeTab === tab ? 'page' : undefined}
                  aria-keyshortcuts={`${index + 1}`}
                  className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition ${
                    activeTab === tab
                      ? 'bg-cyan-500/15 text-cyan-200 shadow-[inset_0_0_0_1px_rgba(34,211,238,0.24)]'
                      : 'text-slate-400 hover:bg-slate-900/80 hover:text-slate-200'
                  }`}
                >
                  {tab.charAt(0).toUpperCase() + tab.slice(1)}
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-semibold tracking-[0.08em] ${
                      activeTab === tab
                        ? 'bg-cyan-500/20 text-cyan-100'
                        : 'bg-slate-800 text-slate-400'
                    }`}
                  >
                    {tabMetadata[tab].isLoading ? 'Loading…' : tabMetadata[tab].countLabel}
                  </span>
                </button>
              ))}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded-full border border-slate-800 bg-slate-900/80 px-3 py-1 text-slate-400">
              {progressQuery.isConnected
                ? 'Realtime stream online'
                : 'Realtime stream reconnecting'}
            </span>
            <span className="rounded-full border border-slate-800 bg-slate-900/80 px-3 py-1 text-slate-400">
              {tabMetadata[activeTab].isLoading
                ? 'Loading tab data…'
                : `${tabMetadata[activeTab].countLabel} ready`}
            </span>
            <span className="rounded-full border border-slate-800 bg-slate-900/80 px-3 py-1 text-slate-500">
              Shortcuts 1–5
            </span>
          </div>
        </div>
      </div>

      {/* Summary Tab */}
      {activeTab === 'summary' && (
        <div className="space-y-3">
          <div className="rounded-2xl border border-slate-800 bg-slate-950/55 px-3 py-2">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                  Summary density
                </p>
                <p className="text-xs text-slate-400">
                  Switch to dense mode for tighter scanning on smaller laptop screens.
                </p>
              </div>
              <div className="inline-flex rounded-xl border border-slate-700 bg-slate-900/70 p-1">
                <button
                  type="button"
                  onClick={() => setSummaryDensity('comfortable')}
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                    !isSummaryDense
                      ? 'bg-cyan-500/15 text-cyan-200 shadow-[inset_0_0_0_1px_rgba(34,211,238,0.24)]'
                      : 'text-slate-300 hover:text-slate-100'
                  }`}
                >
                  Comfort
                </button>
                <button
                  type="button"
                  onClick={() => setSummaryDensity('dense')}
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                    isSummaryDense
                      ? 'bg-cyan-500/15 text-cyan-200 shadow-[inset_0_0_0_1px_rgba(34,211,238,0.24)]'
                      : 'text-slate-300 hover:text-slate-100'
                  }`}
                >
                  Operator Dense
                </button>
              </div>
            </div>
          </div>

          <div className={`grid grid-cols-1 xl:grid-cols-2 ${isSummaryDense ? 'gap-4' : 'gap-6'}`}>
            <div
              className={`rounded-2xl border border-slate-800 bg-slate-900/75 ${isSummaryDense ? 'p-4' : 'p-4 sm:p-6'}`}
            >
              <div
                className={`${isSummaryDense ? 'mb-3' : 'mb-4'} flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between`}
              >
                <div>
                  <h2 className="text-xl font-bold">Run Snapshot</h2>
                  <p className={`mt-1 ${isSummaryDense ? 'text-xs' : 'text-sm'} text-slate-400`}>
                    Live status, timing, and runtime metadata for this backtest ticket.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <span className="rounded-full border border-slate-700 bg-slate-950/70 px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-slate-300">
                    {statusNorm}
                  </span>
                  <span className="rounded-full border border-cyan-500/35 bg-cyan-500/10 px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-cyan-200">
                    {progressPercent.toFixed(1)}% progress
                  </span>
                </div>
              </div>

              <div
                className={`${isSummaryDense ? 'mb-3' : 'mb-4'} grid gap-2 text-xs sm:grid-cols-3`}
              >
                <div className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2">
                  <p className="text-[10px] uppercase tracking-[0.14em] text-slate-500">
                    Last sync
                  </p>
                  <p className="mt-1 font-semibold text-slate-200">
                    {formatTimeAgo(latestProgressTimestamp)}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2">
                  <p className="text-[10px] uppercase tracking-[0.14em] text-slate-500">Source</p>
                  <p className="mt-1 font-semibold text-slate-200">{progressSourceLabel}</p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2">
                  <p className="text-[10px] uppercase tracking-[0.14em] text-slate-500">ETA</p>
                  <p className="mt-1 font-semibold text-slate-200">{etaLabel || 'Calibrating'}</p>
                </div>
              </div>

              <dl
                className={`grid grid-cols-1 sm:grid-cols-2 ${isSummaryDense ? 'gap-3' : 'gap-4'}`}
              >
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">Run ID</dt>
                  <dd
                    className={`mt-1 font-mono ${isSummaryDense ? 'text-xs' : 'text-sm'} text-slate-200`}
                  >
                    {backtest.run_id}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">Created</dt>
                  <dd className={`mt-1 ${isSummaryDense ? 'text-xs' : 'text-sm'} text-slate-200`}>
                    {formatDateValue(backtest.created_at)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">Date Range</dt>
                  <dd className={`mt-1 ${isSummaryDense ? 'text-xs' : 'text-sm'} text-slate-200`}>
                    {backtest.start_date || 'N/A'} to {backtest.end_date || 'N/A'}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">Status</dt>
                  <dd
                    className={`mt-1 ${isSummaryDense ? 'text-xs' : 'text-sm'} capitalize text-slate-200`}
                  >
                    {statusNorm}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">Profit Factor</dt>
                  <dd className={`mt-1 ${isSummaryDense ? 'text-xs' : 'text-sm'} text-slate-200`}>
                    {liveBacktest.profit_factor !== undefined && liveBacktest.profit_factor !== null
                      ? liveBacktest.profit_factor.toFixed(2)
                      : 'N/A'}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">Max Drawdown</dt>
                  <dd className={`mt-1 ${isSummaryDense ? 'text-xs' : 'text-sm'} text-slate-200`}>
                    {maxDrawdown.toFixed(1)}%
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">Worker</dt>
                  <dd className={`mt-1 ${isSummaryDense ? 'text-xs' : 'text-sm'} text-slate-200`}>
                    {liveBacktest.worker_backend || 'asyncio'}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">
                    Markets in scope
                  </dt>
                  <dd className={`mt-1 ${isSummaryDense ? 'text-xs' : 'text-sm'} text-slate-200`}>
                    {selectedMarketsForRuntime.length}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">Trades indexed</dt>
                  <dd className={`mt-1 ${isSummaryDense ? 'text-xs' : 'text-sm'} text-slate-200`}>
                    {liveBacktest.total_trades ?? trades.length}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">Current task</dt>
                  <dd className={`mt-1 ${isSummaryDense ? 'text-xs' : 'text-sm'} text-slate-200`}>
                    {currentTaskLine || 'Initializing runtime'}
                  </dd>
                </div>
              </dl>
            </div>

            <div
              className={`rounded-2xl border border-slate-800 bg-slate-900/75 ${isSummaryDense ? 'p-4' : 'p-4 sm:p-6'}`}
            >
              <div
                className={`${isSummaryDense ? 'mb-3' : 'mb-4'} flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between`}
              >
                <div>
                  <h2 className="text-xl font-bold">Analysis Access</h2>
                  <p className={`mt-1 ${isSummaryDense ? 'text-xs' : 'text-sm'} text-slate-400`}>
                    Open only the dataset you need and keep heavy panels lazy-loaded.
                  </p>
                </div>
                <LiveStateBadge
                  tone={streamBadge.tone}
                  label={streamBadge.label}
                  className="rounded-full px-3 py-1 text-[11px]"
                />
              </div>

              <div
                className={`${isSummaryDense ? 'mb-3' : 'mb-4'} grid gap-2 text-xs sm:grid-cols-3`}
              >
                <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2">
                  <p className="text-[10px] uppercase tracking-[0.14em] text-emerald-200">
                    Edge score
                  </p>
                  <p className="mt-1 font-semibold text-emerald-100">
                    {edgeQualityScore.toFixed(0)}/100
                  </p>
                </div>
                <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-3 py-2">
                  <p className="text-[10px] uppercase tracking-[0.14em] text-cyan-200">
                    Capital efficiency
                  </p>
                  <p className="mt-1 font-semibold text-cyan-100">
                    {capitalEfficiencyPct >= 0 ? '+' : ''}
                    {capitalEfficiencyPct.toFixed(2)}%
                  </p>
                </div>
                <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2">
                  <p className="text-[10px] uppercase tracking-[0.14em] text-amber-200">
                    Retry pressure
                  </p>
                  <p className="mt-1 font-semibold text-amber-100">
                    {retryPressureScore.toFixed(1)}/100
                  </p>
                </div>
              </div>

              <div className={`${isSummaryDense ? 'mb-3' : 'mb-4'} flex flex-wrap gap-2`}>
                <button
                  type="button"
                  onClick={() => setActiveTab('candles')}
                  className="rounded-xl border border-cyan-500/35 bg-cyan-500/10 px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-cyan-200 transition hover:border-cyan-400/70"
                >
                  Open candles
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('positions')}
                  className="rounded-xl border border-slate-700 bg-slate-900/75 px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-200 transition hover:border-slate-500"
                >
                  Open positions
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('trades')}
                  className="rounded-xl border border-slate-700 bg-slate-900/75 px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-200 transition hover:border-slate-500"
                >
                  Open trades
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('results')}
                  className="rounded-xl border border-slate-700 bg-slate-900/75 px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-200 transition hover:border-slate-500"
                >
                  Open results
                </button>
              </div>

              <div
                className={`${isSummaryDense ? 'space-y-2 text-xs' : 'space-y-3 text-sm'} text-slate-300`}
              >
                <p>Open a detail tab to load the heavier datasets only when you need them.</p>
                <div className={`grid ${isSummaryDense ? 'gap-2' : 'gap-3'} sm:grid-cols-2`}>
                  <div
                    className={`rounded-2xl border border-slate-800 bg-slate-950/55 ${isSummaryDense ? 'p-3' : 'p-4'}`}
                  >
                    <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                      Chart workspace
                    </p>
                    <p className="mt-2 text-slate-200">
                      Period filters, market switching, live equity curve, trade markers, and sync
                      telemetry.
                    </p>
                  </div>
                  <div
                    className={`rounded-2xl border border-slate-800 bg-slate-950/55 ${isSummaryDense ? 'p-3' : 'p-4'}`}
                  >
                    <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                      Detail panels
                    </p>
                    <p className="mt-2 text-slate-200">
                      Positions, trades, and pair ranking update live without hard resets while the
                      run executes.
                    </p>
                  </div>
                  <div
                    className={`rounded-2xl border border-slate-800 bg-slate-950/55 sm:col-span-2 ${isSummaryDense ? 'p-3' : 'p-4'}`}
                  >
                    <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                      Runtime telemetry
                    </p>
                    <p className="mt-2 text-slate-200">
                      Current task:{' '}
                      <span className="font-mono text-slate-100">
                        {currentTaskLine || 'Initializing runtime'}
                      </span>
                    </p>
                    <p className="mt-1 text-sm text-slate-400">
                      Sync status:{' '}
                      {progressQuery.isConnected
                        ? 'websocket streaming live'
                        : 'silent fallback recovery'}
                      .
                    </p>
                  </div>

                  <div
                    className={`rounded-2xl border border-slate-800 bg-slate-950/55 sm:col-span-2 ${isSummaryDense ? 'p-3' : 'p-4'}`}
                  >
                    <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                      History fetch telemetry
                    </p>
                    {hasHistoryFetchTelemetry ? (
                      <>
                        <div className="mt-2 flex flex-wrap items-center gap-3 text-sm">
                          <span className={`font-semibold ${retryPressureTone}`}>
                            Retry pressure: {retryPressureScore.toFixed(1)} / 100
                          </span>
                          <span className="rounded-full border border-slate-800 bg-slate-900/70 px-2.5 py-1 text-[11px] text-slate-300">
                            {retryPressureLabel}
                          </span>
                        </div>
                        <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
                          <div className="rounded-lg border border-slate-800 bg-slate-900/70 px-2.5 py-2 text-slate-300">
                            <p className="text-[10px] uppercase tracking-[0.14em] text-slate-500">
                              Windows
                            </p>
                            <p className="mt-1 font-semibold text-slate-100">
                              {historyFetchTotalWindows}
                            </p>
                          </div>
                          <div className="rounded-lg border border-slate-800 bg-slate-900/70 px-2.5 py-2 text-slate-300">
                            <p className="text-[10px] uppercase tracking-[0.14em] text-slate-500">
                              Retries
                            </p>
                            <p className="mt-1 font-semibold text-slate-100">
                              {historyFetchTotalRetries}
                            </p>
                          </div>
                          <div className="rounded-lg border border-slate-800 bg-slate-900/70 px-2.5 py-2 text-slate-300">
                            <p className="text-[10px] uppercase tracking-[0.14em] text-slate-500">
                              Failed windows
                            </p>
                            <p className="mt-1 font-semibold text-slate-100">
                              {historyFetchTotalFailedWindows}
                            </p>
                          </div>
                          <div className="rounded-lg border border-slate-800 bg-slate-900/70 px-2.5 py-2 text-slate-300">
                            <p className="text-[10px] uppercase tracking-[0.14em] text-slate-500">
                              Backoff
                            </p>
                            <p className="mt-1 font-semibold text-slate-100">
                              {historyFetchTotalBackoffSeconds.toFixed(1)}s
                            </p>
                          </div>
                        </div>
                        {historyFetchMarketRows.length > 0 && (
                          <div className="mt-3 overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/60">
                            <table className="min-w-full text-left text-xs">
                              <thead className="border-b border-slate-800 text-[10px] uppercase tracking-[0.14em] text-slate-500">
                                <tr>
                                  <th className="px-3 py-2">Market</th>
                                  <th className="px-3 py-2">Retries</th>
                                  <th className="px-3 py-2">Windows</th>
                                  <th className="px-3 py-2">Failed</th>
                                  <th className="px-3 py-2">Avg backoff</th>
                                </tr>
                              </thead>
                              <tbody>
                                {historyFetchMarketRows.map((row) => (
                                  <tr
                                    key={row.market}
                                    className="border-b border-slate-800/60 text-slate-300 last:border-none"
                                  >
                                    <td className="px-3 py-2 font-medium text-slate-100">
                                      {row.market}
                                    </td>
                                    <td className="px-3 py-2">{row.retries}</td>
                                    <td className="px-3 py-2">{row.windows}</td>
                                    <td className="px-3 py-2">{row.failedWindows}</td>
                                    <td className="px-3 py-2">{row.avgBackoff.toFixed(2)}s</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </>
                    ) : (
                      <p
                        className={`mt-2 ${isSummaryDense ? 'text-xs' : 'text-sm'} text-slate-400`}
                      >
                        No retry/backoff telemetry was captured for this run yet.
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* AI Backtest Explainer — full width below the two snapshot cards */}
          <div className="xl:col-span-2">
            <AIBacktestExplainer
              winRate={liveBacktest.win_rate}
              totalPnlUsd={liveBacktest.total_pnl_usd ?? liveBacktest.total_pnl ?? 0}
              sharpeRatio={liveBacktest.sharpe_ratio}
              maxDrawdownPct={liveBacktest.max_drawdown_pct}
              totalTrades={liveBacktest.total_trades ?? 0}
              profitFactor={liveBacktest.profit_factor ?? 0}
              markets={markets}
              startDate={backtest.start_date ?? ''}
              endDate={backtest.end_date ?? ''}
            />
          </div>
        </div>
      )}

      {/* Candles Tab */}
      {activeTab === 'candles' && (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.5fr)_360px]">
          <div className="rounded-3xl border border-slate-800 bg-slate-900/75 p-4 sm:p-5">
            {analyticsLoading ? (
              <div className="flex items-center justify-center py-16 gap-3">
                <Loader className="w-6 h-6 animate-spin text-blue-400" />
                <p className="text-sm text-slate-400">Loading candle analytics...</p>
              </div>
            ) : analyticsError ? (
              <div className="rounded border border-red-700 bg-red-950/30 px-4 py-3 text-sm text-red-200">
                {analyticsError}
              </div>
            ) : candles.length === 0 ? (
              analyticsLoadedState?.runId === runId ? (
                renderEmptyState('candle data')
              ) : (
                renderDeferredTabHint('Candle analytics')
              )
            ) : (
              <>
                <div className="mb-5 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                  <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <CandlestickChart className="h-5 w-5 text-cyan-300" />
                        <p className="text-sm font-semibold text-slate-100">
                          Equity Curve Workspace
                        </p>
                      </div>
                      <p className="mt-1 text-sm text-slate-400">
                        Browse market-level equity, filter the visible window, and inspect trade
                        activity without resetting the chart.
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {(['7D', '30D', '90D', 'ALL'] as const).map((range) => (
                        <button
                          key={range}
                          onClick={() => setChartRange(range)}
                          className={`rounded-xl px-3 py-1.5 text-xs font-medium transition ${
                            chartRange === range
                              ? 'bg-cyan-500/15 text-cyan-200 shadow-[inset_0_0_0_1px_rgba(34,211,238,0.24)]'
                              : 'bg-slate-900 text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                          }`}
                        >
                          {range}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {markets.map((market) => (
                      <button
                        key={market}
                        onClick={() => setSelectedMarket(market)}
                        className={`rounded-xl px-3 py-2 text-sm transition ${
                          selectedMarket === market
                            ? 'bg-slate-100 text-slate-950'
                            : 'bg-slate-900 text-slate-300 hover:bg-slate-800'
                        }`}
                      >
                        {market}
                      </button>
                    ))}
                  </div>
                </div>

                {selectedMarket && filteredChartPoints.length > 0 ? (
                  <BacktestLightweightChart
                    data={filteredChartPoints}
                    markers={filteredChartMarkers}
                    height={520}
                    resetKey={`${selectedMarket}:${chartRange}`}
                    title={`${selectedMarket} Equity`}
                  />
                ) : (
                  <div className="h-100 flex items-center justify-center text-slate-400">
                    Select a market above to view its equity curve
                  </div>
                )}
              </>
            )}
          </div>
          <div className="space-y-5">
            <div className="rounded-3xl border border-slate-800 bg-slate-900/75 p-5">
              <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
                Visible Range
              </p>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <div className="rounded-2xl border border-slate-800 bg-slate-950/65 p-4">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                    Window PnL
                  </p>
                  <p
                    className={`mt-2 text-xl font-semibold ${periodPnl >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}
                  >
                    {formatSignedCurrency(periodPnl)}
                  </p>
                </div>
                <div className="rounded-2xl border border-slate-800 bg-slate-950/65 p-4">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                    Window Return
                  </p>
                  <p
                    className={`mt-2 text-xl font-semibold ${periodReturnPct >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}
                  >
                    {periodReturnPct >= 0 ? '+' : ''}
                    {periodReturnPct.toFixed(2)}%
                  </p>
                </div>
                <div className="rounded-2xl border border-slate-800 bg-slate-950/65 p-4">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                    Worst Session
                  </p>
                  <p className="mt-2 text-xl font-semibold text-rose-300">
                    {formatSignedCurrency(worstSessionPnl)}
                  </p>
                </div>
                <div className="rounded-2xl border border-slate-800 bg-slate-950/65 p-4">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                    Avg Trades / Bar
                  </p>
                  <p className="mt-2 text-xl font-semibold text-slate-100">
                    {formatCompactValue(averageTradesPerBar)}
                  </p>
                </div>
              </div>
            </div>

            <div className="rounded-3xl border border-slate-800 bg-slate-900/75 p-5">
              <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
                Live Telemetry
              </p>
              <div className="mt-4 space-y-4">
                <div className="rounded-2xl border border-slate-800 bg-slate-950/65 p-4">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                    Active task
                  </p>
                  <p className="mt-2 wrap-break-word font-mono text-sm text-slate-100">
                    {currentTaskLine || 'No active task line yet'}
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-2xl border border-slate-800 bg-slate-950/65 p-4">
                    <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Bars</p>
                    <p className="mt-2 text-lg font-semibold text-slate-100">
                      {filteredChartPoints.length}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-slate-800 bg-slate-950/65 p-4">
                    <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                      Trade markers
                    </p>
                    <p className="mt-2 text-lg font-semibold text-slate-100">
                      {filteredChartMarkers.length}
                    </p>
                  </div>
                </div>
                <div className="rounded-2xl border border-slate-800 bg-slate-950/65 p-4">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                    Stream health
                  </p>
                  <div className="mt-2 flex items-center gap-2">
                    <CircleDot
                      className={`h-4 w-4 ${progressQuery.isConnected ? 'text-cyan-400' : 'text-amber-400'}`}
                    />
                    <span className="text-sm text-slate-200">
                      {progressQuery.isConnected ? 'Live socket healthy' : 'Socket reconnecting'}
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-slate-500">
                    Updated {formatTimeAgo(latestProgressTimestamp)}
                  </p>
                </div>
              </div>
            </div>

            <div className="rounded-3xl border border-slate-800 bg-slate-900/75 p-5">
              <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Top Pairs</p>
              <div className="mt-4 space-y-3">
                {topPairs.length > 0 ? (
                  topPairs.map((pair) => (
                    <div
                      key={pair.pair}
                      className="flex items-center justify-between rounded-2xl border border-slate-800 bg-slate-950/65 px-4 py-3"
                    >
                      <div>
                        <p className="text-sm font-medium text-slate-100">{pair.pair}</p>
                        <p className="mt-1 text-xs text-slate-500">{pair.count} trade markers</p>
                      </div>
                      <p
                        className={`text-sm font-semibold ${pair.pnl >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}
                      >
                        {formatSignedCurrency(pair.pnl)}
                      </p>
                    </div>
                  ))
                ) : (
                  <div className="rounded-2xl border border-dashed border-slate-800 px-4 py-6 text-sm text-slate-500">
                    Pair-level marker insights will populate as trades settle.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Positions Tab */}
      {activeTab === 'positions' && (
        <div>
          {positionsLoading ? (
            <div className="rounded-3xl border border-slate-800 bg-slate-900/75 p-6">
              <div className="flex items-center justify-center gap-3 py-16">
                <Loader className="h-6 w-6 animate-spin text-blue-400" />
                <p className="text-sm text-slate-400">Loading position snapshots...</p>
              </div>
            </div>
          ) : positionsError ? (
            <div className="rounded-3xl border border-red-700 bg-red-950/30 px-4 py-3 text-sm text-red-200">
              {positionsError}
            </div>
          ) : positions.length === 0 ? (
            positionsLoadedState?.runId === runId ? (
              renderEmptyState('position data')
            ) : (
              renderDeferredTabHint('Position snapshots')
            )
          ) : (
            <BacktestPositionsPanel
              positions={positions}
              isConnected={progressQuery.isConnected}
              liveLabel={`Updated ${formatTimeAgo(latestProgressTimestamp)}`}
            />
          )}
        </div>
      )}

      {/* Trades Tab */}
      {activeTab === 'trades' && (
        <div>
          {tradesLoading ? (
            <div className="rounded-3xl border border-slate-800 bg-slate-900/75 p-6">
              <div className="flex items-center justify-center gap-3 py-16">
                <Loader className="h-6 w-6 animate-spin text-blue-400" />
                <p className="text-sm text-slate-400">Loading trade history...</p>
              </div>
            </div>
          ) : tradesError ? (
            <div className="rounded-3xl border border-red-700 bg-red-950/30 px-4 py-3 text-sm text-red-200">
              {tradesError}
            </div>
          ) : trades.length === 0 ? (
            tradesLoadedState?.runId === runId ? (
              renderEmptyState('trade data')
            ) : (
              renderDeferredTabHint('Trade history')
            )
          ) : (
            <BacktestTradesPanel
              trades={trades}
              isConnected={progressQuery.isConnected}
              liveLabel={`Updated ${formatTimeAgo(latestProgressTimestamp)}`}
            />
          )}
        </div>
      )}

      {/* Results Tab */}
      {activeTab === 'results' && (
        <div className="rounded-lg border border-slate-700 bg-slate-800 p-4 sm:p-6">
          <h2 className="text-xl font-bold mb-4">Detailed Results</h2>
          <BacktestResultsEnhanced
            runId={runId || ''}
            liveRefreshToken={activeTab === 'results' ? detailSyncCursor : null}
          />
        </div>
      )}
    </PageContainer>
  );
};

export default BacktestDetailsV2;
