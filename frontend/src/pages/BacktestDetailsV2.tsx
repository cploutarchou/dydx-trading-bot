/**
 * Enhanced BacktestDetailsV2 Component
 *
 * Displays real candle data and position information from persistent database.
 * Replaces placeholder data with actual market data, P&L by pair, and trade records.
 */

import {
  Activity,
  CalendarRange,
  CandlestickChart,
  CircleDot,
  Clock3,
  Gauge,
  Loader,
  Pause,
  Play,
  Radar,
  RotateCcw,
  Square,
  TrendingDown,
  TrendingUp,
  Waves,
} from 'lucide-react';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../api';
import { useBacktestProgress } from '../api/hooks';
import BacktestLightweightChart, {
  type BacktestChartMarker,
  type BacktestChartPoint,
} from '../components/BacktestLightweightChart';
import BacktestPositionsPanel from '../components/BacktestPositionsPanel';
import { BacktestResultsEnhanced } from '../components/BacktestResultsEnhanced';
import BacktestTradesPanel from '../components/BacktestTradesPanel';
import { PageContainer } from '../components/PageContainer';

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
}

interface BacktestLogEntry {
  id: number;
  message: string;
  level: string;
  created_at: string;
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
  const [activeTab, setActiveTab] = useState<
    'summary' | 'candles' | 'positions' | 'trades' | 'results'
  >('summary');
  const [liveLogs, setLiveLogs] = useState<BacktestLogEntry[]>([]);
  const [controlAction, setControlAction] = useState<string | null>(null);
  const [controlError, setControlError] = useState<string | null>(null);
  const liveLogCounterRef = useRef(0);

  const backtestStatus = normalizeStatus(backtest?.status);

  const fetchBacktestMetadata = useCallback(
    async (showLoading: boolean = true) => {
      if (showLoading) {
        setLoading(true);
      }
      setError(null);

      try {
        if (!runId) {
          setBacktest(null);
          setError('Missing backtest run id');
          return;
        }

        const response = await api.getBacktest(runId);
        const data = response?.data || response;
        setBacktest(data as unknown as BacktestResponse);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Failed to fetch backtest';
        setError(msg);
        setBacktest(null);
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
  const progressSourceLabels: Record<string, string> = {
    status: 'status endpoint',
    websocket: 'websocket',
    polling_recovery: 'polling recovery',
    polling: 'polling',
    list_fallback: 'list fallback',
    details: 'details status',
  };
  const progressSourceLabel = progressSourceLabels[progressQuery.progressSource] || 'default';
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
  ];

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
  const canRestart = Boolean(runId) && !controlBusy;
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
      const response = await api.runBacktest(
        cleanRequest as { start_date: string; end_date: string } & Record<string, unknown>
      );
      const payload = asRecord(response?.data || response);
      const newRunId = toStringValue(payload?.run_id);
      if (!newRunId) {
        throw new Error('Retry started but did not return a run id');
      }
      navigate(`/backtests/${newRunId}`);
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
        navigate(`/backtests/${newRunId}`);
        return;
      }

      await fetchBacktestMetadata(false);
    } catch (err: unknown) {
      const response = asRecord(asRecord(err)?.response);
      const statusCode = toNumber(response?.status, 0);
      if ((action === 'restart' || action === 'retry') && statusCode === 404) {
        try {
          await runFromPersistedRequest();
          return;
        } catch (fallbackErr: unknown) {
          const fallbackMsg =
            fallbackErr instanceof Error
              ? fallbackErr.message
              : `Failed to ${action} from saved request`;
          setControlError(fallbackMsg);
          return;
        }
      }
      const msg =
        err instanceof Error ? err.message : `Failed to ${action} backtest ${runId}`;
      setControlError(msg);
    } finally {
      setControlAction(null);
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
      <div className="rounded-[28px] border border-slate-800 bg-[radial-gradient(circle_at_top_left,_rgba(34,197,94,0.10),_transparent_24%),radial-gradient(circle_at_top_right,_rgba(56,189,248,0.14),_transparent_28%),linear-gradient(180deg,rgba(15,23,42,0.98),rgba(2,6,23,0.98))] p-5 shadow-[0_20px_80px_rgba(2,6,23,0.45)] sm:p-7">
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
                <span className="rounded-full border border-slate-700 bg-slate-900/70 px-3 py-1 text-[11px] font-medium text-slate-300">
                  {progressQuery.isConnected ? 'Live websocket' : 'Silent recovery mode'}
                </span>
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

            <div className="grid min-w-full grid-cols-2 gap-3 sm:min-w-[360px] xl:max-w-[420px]">
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
                <p className="mt-2 text-lg font-semibold text-emerald-300">
                  {formatCurrency(peakEquity)}
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
                  Reason: <span className="break-words font-mono">{failureReason}</span>
                </p>
              )}
              <div className="mt-3 rounded-xl border border-red-700/60 bg-slate-950/45 p-3 text-xs text-slate-200">
                <p className="uppercase tracking-[0.14em] text-red-300">Diagnostic category</p>
                <p className="mt-1 font-semibold capitalize text-white">
                  {failureDiagnostic.category}
                </p>
                <p className="mt-2 text-slate-300">Next step: {failureDiagnostic.hint}</p>
              </div>
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
        </div>
      </div>

      <div className="rounded-2xl border border-slate-800 bg-slate-950/65 px-3 py-2">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="overflow-x-auto">
            <div className="flex min-w-max gap-2">
              {(['summary', 'candles', 'positions', 'trades', 'results'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`rounded-xl px-4 py-2 text-sm font-medium transition ${
                    activeTab === tab
                      ? 'bg-cyan-500/15 text-cyan-200 shadow-[inset_0_0_0_1px_rgba(34,211,238,0.24)]'
                      : 'text-slate-400 hover:bg-slate-900/80 hover:text-slate-200'
                  }`}
                >
                  {tab.charAt(0).toUpperCase() + tab.slice(1)}
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
              {activeTab === 'candles'
                ? `${filteredChartPoints.length} bars loaded`
                : `${liveBacktest.total_trades ?? trades.length} trades indexed`}
            </span>
          </div>
        </div>
      </div>

      {/* Summary Tab */}
      {activeTab === 'summary' && (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/75 p-4 sm:p-6">
            <h2 className="mb-4 text-xl font-bold">Run Snapshot</h2>
            <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">Run ID</dt>
                <dd className="mt-1 font-mono text-sm text-slate-200">{backtest.run_id}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">Created</dt>
                <dd className="mt-1 text-sm text-slate-200">
                  {formatDateValue(backtest.created_at)}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">Date Range</dt>
                <dd className="mt-1 text-sm text-slate-200">
                  {backtest.start_date || 'N/A'} to {backtest.end_date || 'N/A'}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">Status</dt>
                <dd className="mt-1 text-sm capitalize text-slate-200">{statusNorm}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">Profit Factor</dt>
                <dd className="mt-1 text-sm text-slate-200">
                  {liveBacktest.profit_factor !== undefined && liveBacktest.profit_factor !== null
                    ? liveBacktest.profit_factor.toFixed(2)
                    : 'N/A'}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">Max Drawdown</dt>
                <dd className="mt-1 text-sm text-slate-200">{maxDrawdown.toFixed(1)}%</dd>
              </div>
            </dl>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900/75 p-4 sm:p-6">
            <h2 className="mb-4 text-xl font-bold">Analysis Access</h2>
            <div className="space-y-3 text-sm text-slate-300">
              <p>Open a detail tab to load the heavier datasets only when you need them.</p>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl border border-slate-800 bg-slate-950/55 p-4">
                  <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                    Chart workspace
                  </p>
                  <p className="mt-2 text-slate-200">
                    Period filters, market switching, live equity curve, trade markers, and sync
                    telemetry.
                  </p>
                </div>
                <div className="rounded-2xl border border-slate-800 bg-slate-950/55 p-4">
                  <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                    Detail panels
                  </p>
                  <p className="mt-2 text-slate-200">
                    Positions, trades, and pair ranking update live without hard resets while the
                    run executes.
                  </p>
                </div>
                <div className="rounded-2xl border border-slate-800 bg-slate-950/55 p-4 sm:col-span-2">
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
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Candles Tab */}
      {activeTab === 'candles' && (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.5fr)_360px]">
          <div className="rounded-[24px] border border-slate-800 bg-slate-900/75 p-4 sm:p-5">
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
            <div className="rounded-[24px] border border-slate-800 bg-slate-900/75 p-5">
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

            <div className="rounded-[24px] border border-slate-800 bg-slate-900/75 p-5">
              <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
                Live Telemetry
              </p>
              <div className="mt-4 space-y-4">
                <div className="rounded-2xl border border-slate-800 bg-slate-950/65 p-4">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                    Active task
                  </p>
                  <p className="mt-2 break-words font-mono text-sm text-slate-100">
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

            <div className="rounded-[24px] border border-slate-800 bg-slate-900/75 p-5">
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
            <div className="rounded-[24px] border border-slate-800 bg-slate-900/75 p-6">
              <div className="flex items-center justify-center gap-3 py-16">
                <Loader className="h-6 w-6 animate-spin text-blue-400" />
                <p className="text-sm text-slate-400">Loading position snapshots...</p>
              </div>
            </div>
          ) : positionsError ? (
            <div className="rounded-[24px] border border-red-700 bg-red-950/30 px-4 py-3 text-sm text-red-200">
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
            <div className="rounded-[24px] border border-slate-800 bg-slate-900/75 p-6">
              <div className="flex items-center justify-center gap-3 py-16">
                <Loader className="h-6 w-6 animate-spin text-blue-400" />
                <p className="text-sm text-slate-400">Loading trade history...</p>
              </div>
            </div>
          ) : tradesError ? (
            <div className="rounded-[24px] border border-red-700 bg-red-950/30 px-4 py-3 text-sm text-red-200">
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
