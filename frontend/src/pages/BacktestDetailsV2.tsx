/**
 * Enhanced BacktestDetailsV2 Component
 *
 * Displays real candle data and position information from persistent database.
 * Replaces placeholder data with actual market data, P&L by pair, and trade records.
 */

import { ArrowDown, ArrowUp, Loader } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
	Bar,
	BarChart,
	CartesianGrid,
	Line,
	LineChart,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from 'recharts';
import api from '../api';
import { useBacktestProgress } from '../api/hooks';
import { BacktestResultsEnhanced } from '../components/BacktestResultsEnhanced';
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
}

interface BacktestLogEntry {
  id: number;
  message: string;
  level: string;
  created_at: string;
}

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
    const parsed = typeof value === 'number' ? value : typeof value === 'string' ? Number(value) : NaN;
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

export const BacktestDetailsV2: React.FC = () => {
  const { runId } = useParams<{ runId: string }>();
  const progressQuery = useBacktestProgress(runId || '');

  // Main backtest data
  const [backtest, setBacktest] = useState<BacktestResponse | null>(null);

  // Real data from API
  const [candles, setCandles] = useState<Candle[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [markets, setMarkets] = useState<string[]>([]);

  // UI state
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedMarket, setSelectedMarket] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<
    'summary' | 'candles' | 'positions' | 'trades' | 'results'
  >('summary');
  const [liveLogs, setLiveLogs] = useState<BacktestLogEntry[]>([]);

  // Fetch backtest metadata
  useEffect(() => {
    const fetchBacktestMetadata = async () => {
      setLoading(true);
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
        setLoading(false);
      }
    };

    fetchBacktestMetadata();
  }, [runId]);

  // Fetch analytics and map it to chart-friendly candle-like series
  useEffect(() => {
    const fetchAnalytics = async () => {
      if (!runId || !backtest) return;
      if (normalizeStatus(backtest.status) !== 'completed') {
        setCandles([]);
        setMarkets([]);
        return;
      }

      try {
        const response = await api.getBacktestAnalytics(runId);
        const payload = asRecord(response?.data || response);
        const root = asRecord(payload?.data) || payload;
        const daily = root?.daily_pnl;

        if (!Array.isArray(daily) || daily.length === 0) {
          setCandles([]);
          setMarkets([]);
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
      } catch (err: unknown) {
        console.error('Failed to fetch backtest analytics:', err);
        setCandles([]);
        setMarkets([]);
      }
    };

    fetchAnalytics();
  }, [runId, backtest?.status]);

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
      if (!runId || !backtest) return;
      if (normalizeStatus(backtest.status) !== 'completed') {
        setPositions([]);
        return;
      }

      try {
        const response = await api.getBacktestPositionSnapshots(runId, 1000, 0);
        const payload = asRecord(response?.data || response);
        const root = asRecord(payload?.data) || payload;
        const snapshots = root?.snapshots;

        if (!Array.isArray(snapshots) || snapshots.length === 0) {
          setPositions([]);
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
      } catch (err: unknown) {
        console.error('Failed to fetch position snapshots:', err);
        setPositions([]);
      }
    };

    fetchPositionSnapshots();
  }, [runId, backtest?.status]);

  // Fetch trades
  useEffect(() => {
    const fetchTrades = async () => {
      if (!runId || !backtest) return;
      if (normalizeStatus(backtest.status) !== 'completed') {
        setTrades([]);
        return;
      }

      try {
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
        } else {
          setTrades([]);
        }
      } catch (err: unknown) {
        console.error('Failed to fetch trades:', err);
        setTrades([]);
      }
    };

    fetchTrades();
  }, [runId, backtest?.status]);

  // Auto-refresh status when backtest is still in progress
  useEffect(() => {
    if (!backtest || !runId) return;
    const sn = normalizeStatus(backtest.status);
    if (sn !== 'running' && sn !== 'pending') return;

    let cancelled = false;
    let timerId: ReturnType<typeof setTimeout> | null = null;
    let failureCount = 0;

    const scheduleNext = (delayMs: number) => {
      if (cancelled) return;
      timerId = setTimeout(() => {
        void pollStatus();
      }, delayMs);
    };

    const pollStatus = async () => {
      try {
        const res = await api.getBacktest(runId);
        if (cancelled) return;
        setBacktest((res?.data || res) as unknown as BacktestResponse);
        failureCount = 0;
        scheduleNext(5000);
      } catch {
        if (cancelled) return;
        failureCount = Math.min(failureCount + 1, 4);
        scheduleNext(Math.min(5000 * 2 ** failureCount, 30000));
      }
    };

    void pollStatus();

    return () => {
      cancelled = true;
      if (timerId) {
        clearTimeout(timerId);
      }
    };
  }, [backtest?.status, runId]);

  // Poll live logs while the backtest is active to surface current scan/task activity.
  useEffect(() => {
    if (!runId || !backtest) return;

    const status = normalizeStatus(backtest.status);
    const isActive = status === 'running' || status === 'pending';
    if (!isActive) return;

    let cancelled = false;
    let timerId: ReturnType<typeof setTimeout> | null = null;
    let failureCount = 0;

    const scheduleNext = (delayMs: number) => {
      if (cancelled) return;
      timerId = setTimeout(() => {
        void fetchLogs();
      }, delayMs);
    };

    const fetchLogs = async () => {
      try {
        const response = await api.getBacktestLogs(runId);
        if (cancelled || !response.success || !response.data?.logs) {
          scheduleNext(5000);
          return;
        }

        const normalized = response.data.logs
          .map((entry) => ({
            id: entry.id,
            message: entry.message,
            level: String(entry.level || 'info').toLowerCase(),
            created_at: entry.created_at,
          }))
          .slice(-8)
          .reverse();

        setLiveLogs(normalized);
        failureCount = 0;
        scheduleNext(5000);
      } catch (error) {
        if (cancelled) {
          return;
        }
        console.warn('📊 BacktestDetailsV2: failed to fetch live backtest logs', error);
        failureCount = Math.min(failureCount + 1, 4);
        scheduleNext(Math.min(5000 * 2 ** failureCount, 30000));
      }
    };

    void fetchLogs();

    return () => {
      cancelled = true;
      if (timerId) {
        clearTimeout(timerId);
      }
    };
  }, [runId, backtest?.status]);

  // Generate Equity Curve from candles (cumulative PnL series)
  const generateEquityCurveData = () => {
    if (candles.length === 0) return [];
    return candles
      .slice()
      .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
      .map((c) => ({
        timestamp: new Date(c.timestamp).toLocaleDateString(),
        balance: c.close,
      }));
  };

  // Generate P&L by Pair
  const generatePnlByPairData = () => {
    if (positions.length === 0) return [];

    const pairMap = new Map<string, { pnl: number; count: number }>();

    positions.forEach((pos) => {
      const pairKey = `${pos.market_1}/${pos.market_2}`;
      if (!pairMap.has(pairKey)) {
        pairMap.set(pairKey, { pnl: 0, count: 0 });
      }
      const pair = pairMap.get(pairKey)!;
      pair.pnl += pos.total_pnl_usd;
      pair.count += 1;
    });

    return Array.from(pairMap.entries())
      .map(([pair, data]) => ({
        pair,
        pnl: data.pnl,
        count: data.count,
      }))
      .sort((a, b) => b.pnl - a.pnl);
  };

  // Filter candles for selected market
  const selectedCandles = candles.filter((c) => c.market === selectedMarket);

  // Format candle chart data
  const candleChartData = selectedCandles.map((c) => ({
    timestamp: new Date(c.timestamp).toLocaleDateString(),
    close: c.close,
    high: c.high,
    low: c.low,
  }));

  const equityData = generateEquityCurveData();
  const pnlByPairData = generatePnlByPairData();

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

  const liveStatusNorm = normalizeStatus(progressQuery.data?.status);
  const statusNorm = liveStatusNorm || normalizeStatus(backtest.status);
  const isRunning = statusNorm === 'running' || statusNorm === 'pending';
  const isFailed = statusNorm === 'failed' || statusNorm === 'cancelled';
  const metadataProgress = firstFiniteNumber(
    backtest.progress_percent,
    backtest.progress_pct,
    backtest.progress
  );
  const liveProgress = progressQuery.progressPercent;
  const baseProgress =
    liveProgress > 0
      ? liveProgress
      : metadataProgress !== null && metadataProgress > 0
        ? metadataProgress
        : liveProgress;
  const progressPercent = isRunning ? Math.min(100, Math.max(0, baseProgress)) : 0;
  const currentPair = progressQuery.currentPair;
  const explicitScanningLine = liveLogs.find((log) => /(^|\b)scanning\s*:/i.test(log.message))?.message;
  const latestTaskFromLogs =
    explicitScanningLine ||
    liveLogs.find((log) => /(scan|processing|pair|market|running)/i.test(log.message))?.message;
  const currentTaskLine = latestTaskFromLogs || (currentPair ? `Scanning: ${currentPair}` : null);
  const etaLabel =
    typeof progressQuery.etaSeconds === 'number'
      ? formatDurationFromSeconds(progressQuery.etaSeconds)
      : null;
  const progressSourceLabel =
    progressQuery.progressSource === 'list_fallback'
      ? 'list fallback'
      : progressQuery.progressSource === 'details'
        ? 'details status'
        : 'default';
  const totalPnl = backtest.total_pnl_usd ?? backtest.total_pnl ?? 0;
  const maxDrawdown = backtest.max_drawdown ?? backtest.max_drawdown_pct ?? 0;
  const winRatePercent = normalizePercentValue(backtest.win_rate);
  const failureReason = firstMeaningfulString(backtest.error_message, backtest.error);

  const renderEmptyState = (label: string): React.ReactNode => {
    if (isRunning) {
      return (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <Loader className="w-6 h-6 animate-spin text-blue-400" />
          <p className="text-slate-400 text-center text-sm">
            Backtest is still running — {label} will appear here once complete.
          </p>
        </div>
      );
    }
    if (isFailed) {
      return (
        <div className="flex flex-col items-center justify-center py-16 gap-2">
          <p className="text-red-400 font-medium capitalize">Backtest {statusNorm}</p>
          <p className="text-slate-500 text-sm">
            No {label} available — the backtest did not complete successfully.
          </p>
          {failureReason && (
            <p className="max-w-2xl text-center text-xs text-red-300">
              Reason: {failureReason}
            </p>
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
      value: backtest.total_trades ?? trades.length,
      icon: '📊',
    },
    {
      label: 'Win Rate',
      value: `${winRatePercent.toFixed(1)}%`,
      icon: '✅',
    },
    {
      label: 'Total PnL',
      value: `$${totalPnl.toFixed(2)}`,
      icon: '💰',
      color: totalPnl >= 0 ? 'text-green-400' : 'text-red-400',
    },
    {
      label: 'Sharpe Ratio',
      value:
        backtest.sharpe_ratio !== undefined && backtest.sharpe_ratio !== null
          ? backtest.sharpe_ratio.toFixed(2)
          : 'N/A',
      icon: '📈',
    },
    {
      label: 'Max Drawdown',
      value: `${maxDrawdown.toFixed(1)}%`,
      icon: '📉',
    },
    {
      label: 'Profit Factor',
      value:
        backtest.profit_factor !== undefined && backtest.profit_factor !== null
          ? backtest.profit_factor.toFixed(2)
          : 'N/A',
      icon: '🎯',
    },
  ];

  return (
    <PageContainer size="wide" className="space-y-6 text-white">
        {/* Header */}
        <div>
          <h1 className="mb-2 text-2xl font-bold sm:text-4xl">Backtest Results</h1>
          <div className="flex flex-wrap items-center gap-3 text-sm text-slate-300 sm:text-base">
            <span>
              {backtest.start_date || 'N/A'} to {backtest.end_date || 'N/A'}
            </span>
            <span
              className={`px-3 py-1 rounded-full text-sm font-medium ${
                statusNorm === 'completed'
                  ? 'bg-green-900 text-green-200'
                  : statusNorm === 'running'
                    ? 'bg-blue-900 text-blue-200'
                    : statusNorm === 'failed' || statusNorm === 'cancelled'
                      ? 'bg-red-900 text-red-200'
                      : 'bg-yellow-900 text-yellow-200'
              }`}
            >
              {statusNorm}
            </span>
          </div>
        </div>

        {/* Status Banner */}
        {isRunning && (
          <div className="rounded-lg border border-blue-700 bg-blue-900/40 p-4 flex items-start gap-3">
            <Loader className="w-5 h-5 animate-spin text-blue-400 shrink-0 mt-0.5" />
            <div className="w-full">
              <p className="text-blue-300 font-medium">Backtest in progress</p>
              <p className="text-slate-400 text-sm mt-0.5">
                Tab data is hidden until the backtest completes. This page refreshes automatically
                every 5 seconds.
              </p>
              <div className="mt-3">
                <div className="flex items-center justify-between text-xs text-blue-300 mb-1">
                  <span>Progress</span>
                  <span>{progressPercent.toFixed(1)}%</span>
                </div>
                <div className="w-full bg-slate-700 rounded-full h-2 overflow-hidden">
                  <div
                    className="h-2 bg-blue-500 transition-all duration-500"
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-300">
                  {currentTaskLine ? (
                    <span>
                      Task: <span className="font-mono text-slate-100">{currentTaskLine}</span>
                    </span>
                  ) : (
                    <span className="italic text-slate-400">Task: Initialising...</span>
                  )}
                  {etaLabel && (
                    <span className="text-slate-400">
                      ETA: <span className="text-slate-200 font-medium">{etaLabel}</span>
                    </span>
                  )}
                </div>
                {import.meta.env.DEV && (
                  <p className="mt-1 text-[11px] text-slate-500">
                    Sync source: {progressSourceLabel}
                  </p>
                )}
                {liveLogs.length > 0 && (
                  <div className="mt-3 rounded border border-slate-700 bg-slate-900/60 p-2">
                    <p className="text-[11px] uppercase tracking-wide text-slate-400 mb-1">
                      Live Activity
                    </p>
                    <div className="space-y-1 max-h-24 overflow-y-auto">
                      {liveLogs.map((log) => (
                        <div key={`${log.id}-${log.created_at}`} className="text-xs text-slate-300">
                          <span className="text-slate-500 mr-1">
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
          </div>
        )}
        {isFailed && (
          <div className="rounded-lg border border-red-700 bg-red-900/40 p-4">
            <p className="text-red-300 font-medium capitalize">Backtest {statusNorm}</p>
            <p className="text-slate-400 text-sm mt-1">
              This backtest did not complete successfully. No result data is available.
            </p>
            {failureReason && (
              <p className="mt-2 text-sm text-red-200">
                Reason: <span className="font-mono break-words">{failureReason}</span>
              </p>
            )}
          </div>
        )}

        {/* Metrics Grid */}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
          {metrics.map((metric) => (
            <div key={metric.label} className="bg-slate-800 p-4 rounded-lg border border-slate-700">
              <p className="text-2xl mb-2">{metric.icon}</p>
              <p className="text-xs text-slate-400 mb-1">{metric.label}</p>
              <p className={`text-lg font-bold ${metric.color || 'text-slate-100'}`}>
                {metric.value}
              </p>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <div className="overflow-x-auto border-b border-slate-700">
          <div className="flex min-w-max gap-2 sm:gap-4">
            {(['summary', 'candles', 'positions', 'trades', 'results'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`border-b-2 px-4 py-2 transition ${
                  activeTab === tab
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Summary Tab */}
        {activeTab === 'summary' && (
            <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            {/* Equity Curve */}
              <div className="rounded-lg border border-slate-700 bg-slate-800 p-4 sm:p-6">
              <h2 className="text-xl font-bold mb-4">Equity Curve</h2>
              {equityData.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={equityData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
                    <XAxis dataKey="timestamp" stroke="#94a3b8" tick={{ fontSize: 12 }} />
                    <YAxis stroke="#94a3b8" tick={{ fontSize: 12 }} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1e293b',
                        border: '1px solid #475569',
                      }}
                      formatter={(value: unknown) => `$${(value as number).toFixed(2)}`}
                    />
                    <Line
                      type="monotone"
                      dataKey="balance"
                      stroke="#22c55e"
                      dot={false}
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                renderEmptyState('equity curve data')
              )}
            </div>

            {/* P&L by Pair */}
              <div className="rounded-lg border border-slate-700 bg-slate-800 p-4 sm:p-6">
              <h2 className="text-xl font-bold mb-4">P&L by Pair</h2>
              {pnlByPairData.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={pnlByPairData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
                    <XAxis dataKey="pair" stroke="#94a3b8" tick={{ fontSize: 12 }} />
                    <YAxis stroke="#94a3b8" tick={{ fontSize: 12 }} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1e293b',
                        border: '1px solid #475569',
                      }}
                      formatter={(value: unknown) => `$${(value as number).toFixed(2)}`}
                    />
                    <Bar dataKey="pnl" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                renderEmptyState('P&L data')
              )}
            </div>
          </div>
        )}

        {/* Candles Tab */}
        {activeTab === 'candles' && (
          <div className="rounded-lg border border-slate-700 bg-slate-800 p-4 sm:p-6">
            {candles.length === 0 ? (
              renderEmptyState('candle data')
            ) : (
              <>
                <div className="mb-4">
                  <p className="text-sm text-slate-400 mb-2">Select Market</p>
                  <div className="flex gap-2 flex-wrap">
                    {markets.map((market) => (
                      <button
                        key={market}
                        onClick={() => setSelectedMarket(market)}
                        className={`px-3 py-1 rounded text-sm transition ${
                          selectedMarket === market
                            ? 'bg-blue-600 text-white'
                            : 'bg-slate-700 text-slate-200 hover:bg-slate-600'
                        }`}
                      >
                        {market}
                      </button>
                    ))}
                  </div>
                </div>

                {selectedMarket && candleChartData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={400}>
                    <LineChart data={candleChartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
                      <XAxis dataKey="timestamp" stroke="#94a3b8" tick={{ fontSize: 12 }} />
                      <YAxis stroke="#94a3b8" tick={{ fontSize: 12 }} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#1e293b',
                          border: '1px solid #475569',
                        }}
                        formatter={(value: unknown) => `$${(value as number).toFixed(2)}`}
                      />
                      <Line
                        type="monotone"
                        dataKey="close"
                        stroke="#f59e0b"
                        dot={false}
                        isAnimationActive={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-100 flex items-center justify-center text-slate-400">
                    Select a market above to view its equity curve
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* Positions Tab */}
        {activeTab === 'positions' && (
          <div className="overflow-x-auto rounded-lg border border-slate-700 bg-slate-800 p-4 sm:p-6">
            <h2 className="text-xl font-bold mb-4">Positions ({positions.length})</h2>
            {positions.length === 0 ? (
              renderEmptyState('position data')
            ) : (
              <table className="w-full text-sm">
                <thead className="border-b border-slate-700">
                  <tr>
                    <th className="px-4 py-2 text-left text-slate-400">Pair</th>
                    <th className="px-4 py-2 text-left text-slate-400">Entry Time</th>
                    <th className="px-4 py-2 text-left text-slate-400">Exit Time</th>
                    <th className="px-4 py-2 text-right text-slate-400">Entry Z-Score</th>
                    <th className="px-4 py-2 text-right text-slate-400">Exit Z-Score</th>
                    <th className="px-4 py-2 text-right text-slate-400">PnL ($)</th>
                    <th className="px-4 py-2 text-left text-slate-400">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {positions.map((pos, idx) => (
                    <tr
                      key={`${pos.position_id}-${pos.entry_timestamp}-${idx}`}
                      className={`border-b border-slate-700 ${
                        pos.total_pnl_usd >= 0 ? 'bg-green-900/20' : 'bg-red-900/20'
                      }`}
                    >
                      <td className="px-4 py-2 text-white font-medium">
                        {pos.market_1}/{pos.market_2}
                      </td>
                      <td className="px-4 py-2 text-slate-300">
                        {formatDateValue(pos.entry_timestamp)}
                      </td>
                      <td className="px-4 py-2 text-slate-300">
                        {formatDateValue(pos.exit_timestamp)}
                      </td>
                      <td className="px-4 py-2 text-right text-slate-300">
                        {pos.entry_zscore !== undefined && pos.entry_zscore !== null
                          ? pos.entry_zscore.toFixed(3)
                          : '-'}
                      </td>
                      <td className="px-4 py-2 text-right text-slate-300">
                        {pos.exit_zscore !== undefined && pos.exit_zscore !== null
                          ? pos.exit_zscore.toFixed(3)
                          : '-'}
                      </td>
                      <td
                        className={`px-4 py-2 text-right font-bold ${
                          (pos.total_pnl_usd || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                        }`}
                      >
                        ${(pos.total_pnl_usd || 0).toFixed(2)}
                      </td>
                      <td className="px-4 py-2 text-slate-300">{pos.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {/* Trades Tab */}
        {activeTab === 'trades' && (
          <div className="overflow-x-auto rounded-lg border border-slate-700 bg-slate-800 p-4 sm:p-6">
            <h2 className="text-xl font-bold mb-4">Trades ({trades.length})</h2>
            {trades.length === 0 ? (
              renderEmptyState('trade data')
            ) : (
              <table className="w-full text-sm">
                <thead className="border-b border-slate-700">
                  <tr>
                    <th className="px-4 py-2 text-left text-slate-400">Pair</th>
                    <th className="px-4 py-2 text-left text-slate-400">Entry Time</th>
                    <th className="px-4 py-2 text-left text-slate-400">Exit Time</th>
                    <th className="px-4 py-2 text-right text-slate-400">Duration (h)</th>
                    <th className="px-4 py-2 text-right text-slate-400">PnL ($)</th>
                    <th className="px-4 py-2 text-right text-slate-400">Return %</th>
                    <th className="px-4 py-2 text-center text-slate-400">Result</th>
                  </tr>
                </thead>
                <tbody>
                  {trades.map((trade, idx) => (
                    <tr
                      key={trade.trade_id || `${trade.market_1}-${trade.market_2}-${trade.entry_timestamp}-${idx}`}
                      className={`border-b border-slate-700 ${
                        trade.win ? 'bg-green-900/20' : 'bg-red-900/20'
                      }`}
                    >
                      <td className="px-4 py-2 text-white font-medium">
                        {trade.market_1}/{trade.market_2}
                      </td>
                      <td className="px-4 py-2 text-slate-300">
                        {formatDateValue(trade.entry_timestamp)}
                      </td>
                      <td className="px-4 py-2 text-slate-300">
                        {formatDateValue(trade.exit_timestamp)}
                      </td>
                      <td className="px-4 py-2 text-right text-slate-300">
                        {(trade.duration_hours || 0).toFixed(1)}
                      </td>
                      <td
                        className={`px-4 py-2 text-right font-bold ${
                          (trade.pnl_usd || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                        }`}
                      >
                        ${(trade.pnl_usd || 0).toFixed(2)}
                      </td>
                      <td
                        className={`px-4 py-2 text-right font-bold ${
                          (trade.pnl_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                        }`}
                      >
                        {normalizePercentValue(trade.pnl_pct).toFixed(2)}%
                      </td>
                      <td className="px-4 py-2 text-center">
                        {trade.win ? (
                          <ArrowUp className="w-4 h-4 text-green-400 mx-auto" />
                        ) : (
                          <ArrowDown className="w-4 h-4 text-red-400 mx-auto" />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {/* Results Tab */}
        {activeTab === 'results' && (
          <div className="rounded-lg border border-slate-700 bg-slate-800 p-4 sm:p-6">
            <h2 className="text-xl font-bold mb-4">Detailed Results</h2>
            <BacktestResultsEnhanced runId={runId || ''} />
          </div>
        )}
    </PageContainer>
  );
};

export default BacktestDetailsV2;
