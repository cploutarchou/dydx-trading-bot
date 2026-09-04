import {
	Activity,
	ChevronDown,
	ChevronUp,
	Pause,
	Play,
	Plus,
	RefreshCw,
	ShieldCheck,
	Trash2,
	Zap,
} from 'lucide-react';
import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { classifyApiError } from '../api';
import {
	useBotInstances,
	useBotRuntimeStatsStream,
	useBotStats,
	useCreateBotInstance,
	useDeleteBotInstance,
	useRestartBotInstance,
	useStartBotInstance,
	useStopBotInstance,
} from '../api/hooks';
import { ArbitrageImprovementPanel } from './ArbitrageImprovementPanel';
import { useToastStore } from './ErrorBoundary';
import { PageContainer } from './PageContainer';
import { ActionDialog, EmptyState, InlineNotice } from './ui/PlatformUI';

interface BotInstance {
  instance_id: string;
  status: 'CREATED' | 'RUNNING' | 'STOPPED' | 'FAILED' | 'ERROR' | 'STARTING' | 'STOPPING';
  process_id?: number;
  configuration?: Record<string, unknown>;
  created_at?: string;
  started_at?: string;
  instance_name?: string;
  strategy?: string;
  error_message?: string;
}

interface BotStats {
  total_positions: number;
  open_positions: number;
  closed_positions: number;
  total_pnl: number;
  realized_pnl: number;
  unrealized_pnl: number;
  total_trades: number;
  win_rate: number;
  last_update?: string;
  degraded?: boolean;
  warning?: string;
}

type PendingRuntimeAction = {
  kind: 'start' | 'stop' | 'restart' | 'delete';
  instanceId: string;
} | null;

const normalizeStatus = (status: string | undefined): BotInstance['status'] => {
  const normalized = String(status || '').toUpperCase();
  if (
    ['CREATED', 'RUNNING', 'STOPPED', 'FAILED', 'ERROR', 'STARTING', 'STOPPING'].includes(
      normalized
    )
  ) {
    return normalized as BotInstance['status'];
  }
  return 'CREATED';
};

const toNumber = (value: unknown, fallback = 0): number => {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

const mapBots = (data: unknown): BotInstance[] => {
  if (!Array.isArray(data)) return [];
  return data
    .map((bot) => {
      const record = isRecord(bot) ? bot : {};
      return {
        ...(record as unknown as BotInstance),
        instance_id: typeof record.instance_id === 'string' ? record.instance_id : '',
        status: normalizeStatus(record.status as string | undefined),
        strategy: typeof record.strategy === 'string' ? record.strategy : undefined,
        error_message: typeof record.error_message === 'string' ? record.error_message : undefined,
      };
    })
    .filter((bot) => bot.instance_id.length > 0);
};

const mapBotStats = (raw: Record<string, unknown>): BotStats => {
  const realtimeStats =
    typeof raw.stats === 'object' && raw.stats && !Array.isArray(raw.stats)
      ? (raw.stats as Record<string, unknown>)
      : {};
  const botStatistics =
    typeof raw.bot_statistics === 'object' && raw.bot_statistics
      ? (raw.bot_statistics as Record<string, unknown>)
      : {};

  const tradeStatistics =
    typeof raw.trade_statistics === 'object' && raw.trade_statistics
      ? (raw.trade_statistics as Record<string, unknown>)
      : {};

  const positions = Array.isArray(raw.positions) ? raw.positions : null;
  const positionPnl = (positions ?? []).reduce((sum, position) => {
    if (!isRecord(position)) return sum;
    return (
      sum +
      toNumber(
        position.unrealized_pnl,
        toNumber(position.current_pnl, toNumber(position.profit_loss))
      )
    );
  }, 0);
  const dailyOpened = toNumber(raw.daily_trades_opened, toNumber(realtimeStats.daily_trades_opened));
  const dailyClosed = toNumber(raw.daily_trades_closed, toNumber(realtimeStats.daily_trades_closed));
  const totalTrades = toNumber(
    tradeStatistics.total_trades,
    toNumber(
      botStatistics.total_trades,
      toNumber(raw.total_trades, toNumber(realtimeStats.total_trades, dailyOpened + dailyClosed))
    )
  );
  const openPositions = positions
    ? positions.length
    : toNumber(
        raw.open_positions,
        toNumber(
          raw.total_open_positions,
          toNumber(realtimeStats.open_positions, toNumber(realtimeStats.total_open_positions))
        )
      );
  const closedPositions = toNumber(
    raw.closed_positions,
    toNumber(realtimeStats.closed_positions, toNumber(raw.daily_trades_closed, dailyClosed))
  );
  const totalPnl = toNumber(
    tradeStatistics.net_profit,
    toNumber(
      botStatistics.total_profit_loss,
      toNumber(
        raw.total_pnl,
        toNumber(
          raw.total_unrealized_pnl,
          toNumber(
            realtimeStats.total_unrealized_pnl,
            positions && positions.length > 0
              ? positionPnl
              : toNumber(raw.daily_pnl, toNumber(realtimeStats.daily_pnl))
          )
        )
      )
    )
  );
  const winRateRaw = toNumber(
    tradeStatistics.win_rate,
    toNumber(
      botStatistics.win_rate,
      toNumber(
        raw.win_rate,
        toNumber(
          realtimeStats.win_rate,
          toNumber(raw.daily_win_rate, toNumber(realtimeStats.daily_win_rate))
        )
      )
    )
  );

  return {
    total_positions: openPositions + closedPositions,
    open_positions: openPositions,
    closed_positions: closedPositions,
    total_pnl: totalPnl,
    realized_pnl: toNumber(tradeStatistics.total_profit, toNumber(raw.realized_pnl)),
    unrealized_pnl: toNumber(
      raw.unrealized_pnl,
      toNumber(realtimeStats.total_unrealized_pnl, positions ? positionPnl : 0)
    ),
    total_trades: totalTrades,
    win_rate: Math.abs(winRateRaw) <= 1 ? winRateRaw : winRateRaw / 100,
    last_update:
      typeof raw.last_update === 'string'
        ? raw.last_update
        : typeof raw.updated_at === 'string'
          ? raw.updated_at
          : typeof realtimeStats.updated_at === 'string'
            ? realtimeStats.updated_at
          : new Date().toISOString(),
    degraded: raw.degraded === true,
    warning: typeof raw.warning === 'string' ? raw.warning : undefined,
  };
};

const isManagedStrategyRuntime = (bot: BotInstance): boolean =>
  /^strategy-\d+-\d+$/.test(bot.instance_id) ||
  bot.strategy === 'cointegration' ||
  bot.strategy === 'mean_reversion';

const EMPTY_BOT_STATS: BotStats = {
  total_positions: 0,
  open_positions: 0,
  closed_positions: 0,
  total_pnl: 0,
  realized_pnl: 0,
  unrealized_pnl: 0,
  total_trades: 0,
  win_rate: 0,
  last_update: undefined,
};

const MANAGED_RUNTIMES_VISIBILITY_KEY = 'botManager.showManagedRuntimes';

const getInitialManagedRuntimeVisibility = (): boolean => {
  if (typeof window === 'undefined') return false;
  const stored = window.localStorage.getItem(MANAGED_RUNTIMES_VISIBILITY_KEY);
  return stored === 'true';
};

const toOperatorErrorMessage = (error: unknown, fallback: string): string => {
  const failure = classifyApiError(error);
  if (failure.kind === 'transport') {
    return `Network/transport issue${failure.statusCode ? ` (${failure.statusCode})` : ''}: ${failure.message}`;
  }
  if (failure.kind === 'business') {
    return `Request rejected${failure.statusCode ? ` (${failure.statusCode})` : ''}: ${failure.message}`;
  }
  return error instanceof Error ? error.message : fallback;
};

const formatUsd = (value: number): string =>
  `${value >= 0 ? '+' : '-'}$${Math.abs(value).toLocaleString('en-US', {
    maximumFractionDigits: 2,
  })}`;

const formatDateTime = (value?: string): string => {
  if (!value) return 'N/A';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return 'N/A';
  return parsed.toLocaleString();
};

const getStatusTone = (
  status: BotInstance['status'],
  degraded?: boolean
): 'positive' | 'accent' | 'warning' | 'danger' => {
  if (degraded || status === 'FAILED' || status === 'ERROR') return 'danger';
  if (status === 'RUNNING') return 'positive';
  if (status === 'STARTING' || status === 'STOPPING') return 'accent';
  return 'warning';
};

interface BotCardProps {
  bot: BotInstance;
  isExpanded: boolean;
  actionLoading: string | null;
  onToggleExpand: (_instanceId: string) => void;
  onStart: (_instanceId: string) => void;
  onStop: (_instanceId: string) => void;
  onRestart: (_instanceId: string) => void;
  onDelete: (_instanceId: string) => void;
}

const BotCard: React.FC<BotCardProps> = ({
  bot,
  isExpanded,
  actionLoading,
  onToggleExpand,
  onStart,
  onStop,
  onRestart,
  onDelete,
}) => {
  const shouldStreamRuntime =
    isExpanded || ['RUNNING', 'STARTING', 'STOPPING'].includes(bot.status);
  const isManagedRuntime = isManagedStrategyRuntime(bot);
  const statsQuery = useBotStats(bot.instance_id, !isManagedRuntime);
  const liveStatsQuery = useBotRuntimeStatsStream(bot.instance_id, shouldStreamRuntime);
  const rawStats =
    liveStatsQuery.data && isRecord(liveStatsQuery.data)
      ? liveStatsQuery.data
      : statsQuery.data && isRecord(statsQuery.data)
        ? statsQuery.data
        : null;
  const stats = rawStats ? mapBotStats(rawStats) : { ...EMPTY_BOT_STATS };
  const hasStatsPayload = rawStats !== null;
  const shouldShowStatsWarning =
    stats.degraded === true || (!!liveStatsQuery.error && !hasStatsPayload);
  const statusTone = getStatusTone(bot.status, stats.degraded);
  const reconnectingWithFallback =
    shouldStreamRuntime && !liveStatsQuery.isConnected && hasStatsPayload;
  const streamLabel = shouldStreamRuntime
    ? liveStatsQuery.isConnected
      ? 'Live runtime stream connected'
      : bot.status === 'RUNNING' && hasStatsPayload
        ? 'Running (live metrics channel reconnecting)'
        : hasStatsPayload
          ? 'Runtime stream reconnecting (API fallback active)'
          : 'Runtime stream reconnecting'
    : 'Polling runtime state';

  return (
    <div className="overflow-hidden rounded-lg border border-slate-800 bg-slate-950/45">
      <div
        className="grid cursor-pointer gap-3 p-4 transition hover:bg-slate-900/35 xl:grid-cols-[minmax(0,1fr)_minmax(420px,auto)] xl:items-center"
        onClick={() => onToggleExpand(bot.instance_id)}
      >
        <div className="flex min-w-0 items-start gap-3">
          <button
            type="button"
            className="mt-0.5 rounded-lg border border-slate-800 bg-slate-950/70 p-2 text-slate-400 hover:text-white"
            onClick={(e) => {
              e.stopPropagation();
              onToggleExpand(bot.instance_id);
            }}
            aria-label={isExpanded ? 'Collapse runtime details' : 'Expand runtime details'}
          >
            {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
          </button>

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="truncate font-semibold text-white">
                {bot.instance_name || bot.instance_id}
              </h3>
              <span className="operator-status-pill" data-tone={statusTone}>
                {bot.status}
              </span>
              {isManagedRuntime && (
                <Link
                  to="/strategies/manage"
                  onClick={(e) => e.stopPropagation()}
                  className="operator-status-pill hover:border-cyan-500/60"
                  data-tone="accent"
                >
                  Managed
                </Link>
              )}
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
              <span className="font-mono">ID: {bot.instance_id}</span>
              <span>Started: {bot.started_at ? formatDateTime(bot.started_at) : 'Never'}</span>
              <span
                className={
                  liveStatsQuery.isConnected
                    ? 'text-emerald-400'
                    : reconnectingWithFallback
                      ? 'text-amber-300'
                      : 'text-slate-500'
                }
              >
                {streamLabel}
              </span>
            </div>
            {bot.error_message && (
              <p className="mt-2 text-xs text-amber-300">{bot.error_message}</p>
            )}
          </div>
        </div>

        <div
          className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-center"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <div className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">P&amp;L</p>
              <p
                className={`mt-1 text-sm font-semibold ${stats.total_pnl >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}
              >
                {formatUsd(stats.total_pnl)}
              </p>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Open</p>
              <p className="mt-1 text-sm font-semibold text-white">{stats.open_positions}</p>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Closed</p>
              <p className="mt-1 text-sm font-semibold text-white">{stats.closed_positions}</p>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Trades</p>
              <p className="mt-1 text-sm font-semibold text-white">
                {stats.total_trades}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap justify-start gap-2 sm:justify-end">
            {bot.status === 'RUNNING' ? (
              <>
                <button
                  type="button"
                  onClick={() => onStop(bot.instance_id)}
                  disabled={actionLoading === `stop:${bot.instance_id}`}
                  className="rounded-lg bg-amber-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-amber-500 disabled:opacity-60"
                  title="Stop bot"
                >
                  <span className="inline-flex items-center gap-2">
                    <Pause size={15} />
                    Stop
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => onRestart(bot.instance_id)}
                  disabled={actionLoading === `restart:${bot.instance_id}`}
                  className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:opacity-60"
                  title="Restart bot"
                >
                  <span className="inline-flex items-center gap-2">
                    <RefreshCw size={15} />
                    Restart
                  </span>
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={() => onStart(bot.instance_id)}
                disabled={actionLoading === `start:${bot.instance_id}`}
                className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-emerald-500 disabled:opacity-60"
                title="Start bot"
              >
                <span className="inline-flex items-center gap-2">
                  <Play size={15} />
                  Start
                </span>
              </button>
            )}
            <button
              type="button"
              onClick={() => onDelete(bot.instance_id)}
              disabled={actionLoading === `delete:${bot.instance_id}`}
              className="rounded-lg bg-rose-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-rose-500 disabled:opacity-60"
              title="Delete bot"
            >
              <span className="inline-flex items-center gap-2">
                <Trash2 size={15} />
                Delete
              </span>
            </button>
          </div>
        </div>
      </div>

      {shouldShowStatsWarning && (
        <div className="mx-4 mb-4 rounded-lg border border-amber-700/60 bg-amber-950/25 px-3 py-2 text-xs text-amber-200">
          {stats.warning || 'Runtime stats temporarily unavailable or reconnecting.'}
        </div>
      )}

      {isExpanded && (
        <div className="border-t border-slate-800/80 bg-slate-950/28 p-5 space-y-4">
          <div className="grid gap-4 md:grid-cols-3">
            <div className="metric-tile p-3">
              <p className="text-xs text-slate-400">Total P&amp;L</p>
              <p
                className={`text-lg font-semibold ${stats.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}
              >
                {formatUsd(stats.total_pnl)}
              </p>
            </div>
            <div className="metric-tile p-3">
              <p className="text-xs text-slate-400">Win Rate</p>
              <p className="text-lg font-semibold text-white">
                {(stats.win_rate * 100).toFixed(1)}%
              </p>
            </div>
            <div className="metric-tile p-3">
              <p className="text-xs text-slate-400">Total Trades</p>
              <p className="text-lg font-semibold text-white">{stats.total_trades}</p>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <div className="metric-tile p-3">
              <p className="text-xs text-slate-400">Created</p>
              <p className="text-sm font-semibold text-white">{formatDateTime(bot.created_at)}</p>
            </div>
            <div className="metric-tile p-3">
              <p className="text-xs text-slate-400">Last runtime update</p>
              <p className="text-sm font-semibold text-white">
                {formatDateTime(stats.last_update)}
              </p>
            </div>
            <div className="metric-tile p-3">
              <p className="text-xs text-slate-400">Exposure state</p>
              <p className="text-sm font-semibold text-white">
                {stats.open_positions} open / {stats.closed_positions} closed
              </p>
            </div>
          </div>

          {bot.configuration && (
            <div className="rounded-2xl border border-slate-800 bg-slate-950/45 p-4">
              <p className="mb-2 text-xs text-slate-400">Configuration</p>
              <pre className="max-h-32 overflow-auto text-xs text-slate-300">
                {JSON.stringify(bot.configuration, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

interface BotManagerProps {
  embedded?: boolean;
  onStatusMetricsChange?: (_metrics: BotRuntimeStatusMetrics) => void;
}

interface BotRuntimeStatusMetrics {
  activeBotRuntimes: number;
  reconnectingBotStreams: number;
  degradedBotRuntimes: number;
}

const BotManager: React.FC<BotManagerProps> = ({ embedded = false, onStatusMetricsChange }) => {
  const [error, setError] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [showManagedRuntimes, setShowManagedRuntimes] = useState(
    getInitialManagedRuntimeVisibility
  );
  const [expandedBot, setExpandedBot] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<PendingRuntimeAction>(null);
  const successToast = useToastStore((state) => state.success);
  const errorToast = useToastStore((state) => state.error);
  const infoToast = useToastStore((state) => state.info);

  const [createForm, setCreateForm] = useState({
    instance_id: '',
    chain_id: 'dydx-mainnet-1',
    address: '',
    mnemonic: '',
    is_testnet: false,
    zscore_threshold: 1.5,
    max_half_life: 24,
    usd_per_trade: 10,
  });

  const botsQuery = useBotInstances({ limit: 100 });
  const bots = mapBots(botsQuery.data?.data);

  const createBotMutation = useCreateBotInstance();
  const startBotMutation = useStartBotInstance();
  const stopBotMutation = useStopBotInstance();
  const restartBotMutation = useRestartBotInstance();
  const deleteBotMutation = useDeleteBotInstance();

  useEffect(() => {
    if (botsQuery.error) {
      setError(toOperatorErrorMessage(botsQuery.error, 'Failed to load bot instances'));
      return;
    }

    setError(null);
  }, [botsQuery.error]);

  useEffect(() => {
    const interval = setInterval(() => {
      void botsQuery.refetch();
    }, 30000);

    return () => {
      clearInterval(interval);
    };
  }, [botsQuery.refetch]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(MANAGED_RUNTIMES_VISIBILITY_KEY, String(showManagedRuntimes));
  }, [showManagedRuntimes]);

  const refreshBots = async () => {
    setError(null);
    await botsQuery.refetch();
  };

  const resetCreateForm = () => {
    setCreateForm({
      instance_id: '',
      chain_id: 'dydx-mainnet-1',
      address: '',
      mnemonic: '',
      is_testnet: false,
      zscore_threshold: 1.5,
      max_half_life: 24,
      usd_per_trade: 10,
    });
  };

  const pendingBot = useMemo(
    () =>
      pendingAction
        ? (bots.find((bot) => bot.instance_id === pendingAction.instanceId) ?? null)
        : null,
    [bots, pendingAction]
  );

  const pendingActionConfig = useMemo(() => {
    if (!pendingAction) return null;

    if (pendingAction.kind === 'start') {
      return {
        title: `Start ${pendingAction.instanceId}?`,
        description:
          'This can move the selected runtime into live execution. Confirm credentials, network, and sizing before continuing.',
        confirmLabel: 'Start runtime',
        confirmTone: 'success' as const,
      };
    }

    if (pendingAction.kind === 'stop') {
      return {
        title: `Stop ${pendingAction.instanceId}?`,
        description:
          'This pauses live execution for the selected runtime. Open positions may still need operator review depending on strategy state.',
        confirmLabel: 'Stop runtime',
        confirmTone: 'warning' as const,
      };
    }

    if (pendingAction.kind === 'restart') {
      return {
        title: `Restart ${pendingAction.instanceId}?`,
        description:
          'Use restart when the runtime is stale, degraded, or after a controlled config change. The desk will briefly lose live continuity.',
        confirmLabel: 'Restart runtime',
        confirmTone: 'accent' as const,
      };
    }

    return {
      title: `Delete ${pendingAction.instanceId}?`,
      description:
        'This permanently removes the runtime from the desk. Only continue if this instance is retired and no longer needed for monitoring or recovery.',
      confirmLabel: 'Delete runtime',
      confirmTone: 'danger' as const,
    };
  }, [pendingAction]);

  const handleCreateBot = async () => {
    try {
      if (!createForm.instance_id || !createForm.address || !createForm.mnemonic) {
        const message =
          'Complete the runtime ID, wallet address, and secret phrase before creating a new bot.';
        setError(message);
        errorToast('Runtime details missing', message);
        return;
      }

      setError(null);
      await createBotMutation.mutateAsync({
        instance_id: createForm.instance_id,
        name: createForm.instance_id,
        credentials: {
          address: createForm.address,
          mnemonic: createForm.mnemonic,
          network: createForm.is_testnet ? 'testnet' : 'mainnet',
          chain_id: createForm.chain_id,
          secret_phrase: createForm.mnemonic,
        },
        trading_params: {
          is_testnet: createForm.is_testnet,
          zscore_threshold: createForm.zscore_threshold,
          max_half_life: createForm.max_half_life,
          usd_per_trade: createForm.usd_per_trade,
          max_positions: 5,
          slippage_tolerance: 0.001,
          risk_multiplier: 1,
        },
      });

      setShowCreateForm(false);
      resetCreateForm();
      await refreshBots();
      successToast(
        'Runtime created',
        `${createForm.instance_id} is ready for review and can be started from the desk.`
      );
    } catch (err) {
      console.error('Failed to create bot:', err);
      const message = toOperatorErrorMessage(err, 'Failed to create bot instance');
      setError(message);
      errorToast('Unable to create runtime', message);
    }
  };

  const runBotAction = async (
    actionKey: string,
    action: () => Promise<unknown>,
    fallbackMessage: string,
    successTitle: string,
    successMessage: string
  ) => {
    try {
      setActionLoading(actionKey);
      setError(null);
      await action();
      await refreshBots();
      successToast(successTitle, successMessage);
    } catch (err) {
      console.error(`${actionKey} failed:`, err);
      const message = toOperatorErrorMessage(err, fallbackMessage);
      setError(message);
      errorToast(successTitle, message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleStartBot = async (instanceId: string) =>
    runBotAction(
      `start:${instanceId}`,
      () => startBotMutation.mutateAsync({ instanceId }),
      'Failed to start bot',
      'Runtime start requested',
      `${instanceId} is moving into live execution. Watch its stream status for confirmation.`
    );

  const handleStopBot = async (instanceId: string) =>
    runBotAction(
      `stop:${instanceId}`,
      () => stopBotMutation.mutateAsync(instanceId),
      'Failed to stop bot',
      'Runtime stop requested',
      `${instanceId} is stopping. Confirm exposure and reconnect state once the desk refreshes.`
    );

  const handleRestartBot = async (instanceId: string) =>
    runBotAction(
      `restart:${instanceId}`,
      () => restartBotMutation.mutateAsync(instanceId),
      'Failed to restart bot',
      'Runtime restart requested',
      `${instanceId} is restarting. Expect a brief monitoring gap while the stream reconnects.`
    );

  const handleDeleteBot = async (instanceId: string) => {
    await runBotAction(
      `delete:${instanceId}`,
      () => deleteBotMutation.mutateAsync(instanceId),
      'Failed to delete bot',
      'Runtime deleted',
      `${instanceId} was removed from the desk.`
    );
  };

  const confirmPendingAction = async () => {
    if (!pendingAction) return;

    const { instanceId, kind } = pendingAction;
    setPendingAction(null);

    if (kind === 'start') {
      await handleStartBot(instanceId);
      return;
    }
    if (kind === 'stop') {
      await handleStopBot(instanceId);
      return;
    }
    if (kind === 'restart') {
      await handleRestartBot(instanceId);
      return;
    }
    await handleDeleteBot(instanceId);
  };

  const isCreating = createBotMutation.isPending;
  const isRefreshing = botsQuery.isFetching && bots.length > 0;
  const isInitialLoading = botsQuery.isLoading && bots.length === 0;
  const runningBots = bots.filter((bot) => bot.status === 'RUNNING').length;
  const erroredBots = bots.filter(
    (bot) => bot.status === 'FAILED' || bot.status === 'ERROR'
  ).length;
  const transitioningBots = bots.filter(
    (bot) => bot.status === 'STARTING' || bot.status === 'STOPPING'
  ).length;
  const managedBots = bots.filter((bot) => isManagedStrategyRuntime(bot)).length;
  const directBots = bots.filter((bot) => !isManagedStrategyRuntime(bot));
  const strategyManagedBots = bots.filter((bot) => isManagedStrategyRuntime(bot));

  useEffect(() => {
    if (!onStatusMetricsChange) return;
    onStatusMetricsChange({
      activeBotRuntimes: runningBots,
      reconnectingBotStreams: transitioningBots,
      degradedBotRuntimes: erroredBots,
    });
  }, [erroredBots, onStatusMetricsChange, runningBots, transitioningBots]);

  const content = (
    <>
      {!embedded && (
        <section className="operator-hero px-6 py-6 sm:px-8 sm:py-8">
          <div className="relative grid gap-6 xl:grid-cols-[1.12fr,0.88fr]">
            <div>
              <div className="surface-label">
                <Zap className="h-3.5 w-3.5" />
                Bots desk
              </div>
              <h2 className="mt-5 text-3xl font-bold text-white sm:text-4xl">Bots</h2>
              <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">
                Manage live instances like an operator surface, not a settings form: health and
                degraded-state signals first, actions close to each runtime, and clearer create-flow
                context before credentials are submitted.
              </p>

              <div className="mt-5 flex flex-wrap gap-3">
                <div
                  className="operator-status-pill"
                  data-tone={runningBots > 0 ? 'positive' : 'warning'}
                >
                  <Activity className="h-3.5 w-3.5" />
                  {runningBots > 0 ? `${runningBots} running` : 'No active bots'}
                </div>
                <div
                  className="operator-status-pill"
                  data-tone={erroredBots > 0 ? 'danger' : 'accent'}
                >
                  <ShieldCheck className="h-3.5 w-3.5" />
                  {erroredBots > 0 ? `${erroredBots} need attention` : 'No runtime failures'}
                </div>
                <div className="operator-status-pill" data-tone="accent">
                  {managedBots} managed strategy runtime{managedBots === 1 ? '' : 's'}
                </div>
              </div>
            </div>

            <div className="operator-mini-grid">
              <div className="operator-hero-panel px-4 py-4">
                <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Instances</p>
                <p className="mt-2 text-xl font-semibold text-white">{bots.length}</p>
                <p className="mt-1 text-xs text-slate-500">Known runtime instances</p>
              </div>
              <div className="operator-hero-panel px-4 py-4">
                <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                  Transitioning
                </p>
                <p className="mt-2 text-xl font-semibold text-white">{transitioningBots}</p>
                <p className="mt-1 text-xs text-slate-500">Starting or stopping</p>
              </div>
              <div className="operator-hero-panel px-4 py-4">
                <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                  Refresh cadence
                </p>
                <p className="mt-2 text-xl font-semibold text-white">30s</p>
                <p className="mt-1 text-xs text-slate-500">Automatic desk refresh</p>
              </div>
              <div className="operator-hero-panel px-4 py-4">
                <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Boundary</p>
                <p className="mt-2 text-xl font-semibold text-white">Backend-only</p>
                <p className="mt-1 text-xs text-slate-500">
                  No direct bot API access from the browser
                </p>
              </div>
            </div>
          </div>
        </section>
      )}

      {!embedded && (
        <section className="grid grid-cols-2 gap-4 xl:grid-cols-4">
          <div className="operator-stat-card p-5">
            <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Running</p>
            <p className="mt-2 text-2xl font-semibold text-emerald-300">{runningBots}</p>
            <p className="mt-1 text-xs text-slate-500">Instances currently live</p>
          </div>
          <div className="operator-stat-card p-5">
            <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">
              Managed runtimes
            </p>
            <p className="mt-2 text-2xl font-semibold text-cyan-300">{managedBots}</p>
            <p className="mt-1 text-xs text-slate-500">Strategy-linked operators</p>
          </div>
          <div className="operator-stat-card p-5">
            <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Transitioning</p>
            <p className="mt-2 text-2xl font-semibold text-blue-300">{transitioningBots}</p>
            <p className="mt-1 text-xs text-slate-500">Starting or stopping now</p>
          </div>
          <div className="operator-stat-card p-5">
            <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">
              Attention needed
            </p>
            <p
              className={`mt-2 text-2xl font-semibold ${erroredBots > 0 ? 'text-rose-300' : 'text-emerald-300'}`}
            >
              {erroredBots}
            </p>
            <p className="mt-1 text-xs text-slate-500">Failed or error state runtimes</p>
          </div>
        </section>
      )}

      {!embedded && <ArbitrageImprovementPanel />}

      {error && (
        <InlineNotice tone="danger" title="Runtime action needs attention" description={error} />
      )}

      <section
        className={`grid grid-cols-1 gap-6 ${embedded ? '' : 'xl:grid-cols-[0.95fr,1.05fr]'}`}
      >
        <div className="operator-section-card p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-white">
                {embedded ? 'Runtime Control actions' : 'Runtime Control actions'}
              </h2>
              <p className="mt-1 text-sm text-slate-400">
                {embedded
                  ? 'Refresh runtime state and create bot instances without leaving the Bots desk.'
                  : 'Refresh runtime state, create a new instance, or inspect managed runtimes.'}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => void refreshBots()}
                disabled={botsQuery.isFetching}
                className="premium-button premium-button-secondary rounded-[1rem] px-4 py-2 text-sm disabled:opacity-60"
              >
                <RefreshCw size={18} className={botsQuery.isFetching ? 'animate-spin' : ''} />
                {isRefreshing ? 'Refreshing...' : 'Refresh'}
              </button>
              <button
                type="button"
                onClick={() => setShowCreateForm(!showCreateForm)}
                className="premium-button premium-button-primary rounded-[1rem] px-4 py-2 text-sm text-white"
              >
                <Plus size={18} />
                {showCreateForm ? 'Hide form' : 'New bot'}
              </button>
            </div>
          </div>

          <div className="mt-5 grid gap-3">
            {!embedded && (
              <Link to="/strategies/manage" className="operator-action-card p-4">
                <p className="text-sm font-semibold text-white">Open managed runtimes</p>
                <p className="mt-1 text-xs text-slate-500">
                  Monitor managed strategy processes beside direct bot instances.
                </p>
              </Link>
            )}
            <Link to="/settings" className="operator-action-card p-4">
              <p className="text-sm font-semibold text-white">Review credentials and settings</p>
              <p className="mt-1 text-xs text-slate-500">
                Keep operator configuration and credentials aligned before activating new bots.
              </p>
            </Link>
          </div>
        </div>

        {!embedded && (
          <div className="operator-section-card p-5">
            <h2 className="text-lg font-semibold text-white">Operator notes</h2>
            <div className="mt-4 space-y-3">
              <div className="rounded-2xl border border-slate-800 bg-slate-950/45 px-4 py-4">
                <p className="text-sm font-semibold text-white">
                  Degraded state should be explicit
                </p>
                <p className="mt-1 text-sm leading-6 text-slate-400">
                  Live runtime stats can reconnect independently of the instance lifecycle. Treat a
                  reconnecting stream as an operator signal, not a silent failure.
                </p>
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-950/45 px-4 py-4">
                <p className="text-sm font-semibold text-white">Instance creation is operational</p>
                <p className="mt-1 text-sm leading-6 text-slate-400">
                  The create flow now sits inside the Bots desk so credential, network, and
                  trading-parameter choices feel part of one controlled setup workflow.
                </p>
              </div>
            </div>
          </div>
        )}
      </section>

      {showCreateForm && (
        <div className="operator-section-card p-6 space-y-4">
          <div>
            <h2 className="text-xl font-semibold text-white">Create new bot instance</h2>
            <p className="mt-1 text-sm text-slate-400">
              Walk through runtime identity, wallet credentials, and execution defaults before the
              instance enters the desk.
            </p>
          </div>

          <div className="grid gap-3 lg:grid-cols-3">
            <div className="metric-tile px-4 py-4">
              <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Identity</p>
              <p className="mt-2 text-sm font-semibold text-white">Name the runtime clearly</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                Use an ID that reflects route, market pair, or strategy owner so operators can scan
                it instantly later.
              </p>
            </div>
            <div className="metric-tile px-4 py-4">
              <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Wallet</p>
              <p className="mt-2 text-sm font-semibold text-white">Attach the correct account</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                Enter the wallet address and secret phrase for the intended dYdX environment before
                the runtime is allowed to trade.
              </p>
            </div>
            <div className="metric-tile px-4 py-4">
              <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Risk</p>
              <p className="mt-2 text-sm font-semibold text-white">Set execution defaults</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                Keep z-score, half-life, and per-trade sizing explicit so the first launch is easy
                to review.
              </p>
            </div>
          </div>

          <InlineNotice
            tone="warning"
            title="Sensitive runtime setup"
            description="Seed phrases are operational secrets. Double-check environment, account, and sizing before you create the runtime."
          />

          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Instance ID *</label>
              <input
                type="text"
                placeholder="e.g., btc-eth-bot-01"
                value={createForm.instance_id}
                onChange={(e) => setCreateForm({ ...createForm, instance_id: e.target.value })}
                className="premium-input"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Chain ID</label>
              <select
                value={createForm.chain_id}
                onChange={(e) => setCreateForm({ ...createForm, chain_id: e.target.value })}
                className="premium-input"
              >
                <option value="dydx-mainnet-1">dYdX Mainnet</option>
                <option value="dydx-testnet-4">dYdX Testnet</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Address *</label>
              <input
                type="text"
                placeholder="dydx1..."
                value={createForm.address}
                onChange={(e) => setCreateForm({ ...createForm, address: e.target.value })}
                className="premium-input"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Mnemonic *</label>
              <input
                type="password"
                placeholder="Your seed phrase..."
                value={createForm.mnemonic}
                onChange={(e) => setCreateForm({ ...createForm, mnemonic: e.target.value })}
                className="premium-input"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">
                Z-Score Threshold
              </label>
              <input
                type="number"
                step="0.1"
                value={createForm.zscore_threshold}
                onChange={(e) =>
                  setCreateForm({ ...createForm, zscore_threshold: parseFloat(e.target.value) })
                }
                className="premium-input"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">
                Max Half-Life (hours)
              </label>
              <input
                type="number"
                value={createForm.max_half_life}
                onChange={(e) =>
                  setCreateForm({ ...createForm, max_half_life: parseInt(e.target.value, 10) })
                }
                className="premium-input"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">USD Per Trade</label>
              <input
                type="number"
                step="0.01"
                value={createForm.usd_per_trade}
                onChange={(e) =>
                  setCreateForm({ ...createForm, usd_per_trade: parseFloat(e.target.value) })
                }
                className="premium-input"
              />
            </div>

            <div>
              <label className="mt-6 flex items-center gap-2 text-sm font-medium text-slate-300">
                <input
                  type="checkbox"
                  checked={createForm.is_testnet}
                  onChange={(e) => setCreateForm({ ...createForm, is_testnet: e.target.checked })}
                  className="rounded"
                />
                Use Testnet
              </label>
            </div>
          </div>

          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => void handleCreateBot()}
              disabled={isCreating}
              className="premium-button premium-button-primary flex-1 justify-center rounded-[1rem] px-4 py-3 text-white disabled:opacity-60"
            >
              {isCreating ? 'Creating...' : 'Create Bot'}
            </button>
            <button
              type="button"
              onClick={() => setShowCreateForm(false)}
              className="premium-button premium-button-secondary flex-1 justify-center rounded-[1rem] px-4 py-3"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <section className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-white">Runtime instances</h2>
            <p className="text-sm text-slate-400">
              Unified monitoring view: direct runtimes stay fully actionable here, while
              strategy-managed runtimes can be shown on demand.
            </p>
          </div>
          <span className="operator-status-pill" data-tone={bots.length > 0 ? 'accent' : 'warning'}>
            {bots.length} instance{bots.length === 1 ? '' : 's'}
          </span>
        </div>

        {isInitialLoading ? (
          <div className="operator-section-card py-10 text-center text-slate-400">
            Loading bots...
          </div>
        ) : bots.length === 0 ? (
          <div className="operator-section-card p-8">
            <EmptyState
              icon={Zap}
              title="No runtimes are active yet"
              description="Create a bot instance to connect wallet credentials, define core execution defaults, and bring a new arbitrage runtime into the desk."
              action={
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateForm(true);
                    infoToast(
                      'New runtime flow opened',
                      'Fill in identity, wallet, and risk defaults before creating the bot.'
                    );
                  }}
                  className="premium-button premium-button-primary inline-flex px-4 py-2.5 text-sm text-white"
                >
                  Create first runtime
                </button>
              }
            />
          </div>
        ) : (
          <div className="space-y-5">
            <div className="rounded-lg border border-slate-800 bg-slate-950/28 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-white">Direct runtime instances</h3>
                  <p className="mt-1 text-xs text-slate-500">
                    Primary controls live here for start, stop, restart, and delete actions.
                  </p>
                </div>
                <span
                  className="operator-status-pill"
                  data-tone={directBots.length > 0 ? 'positive' : 'warning'}
                >
                  {directBots.length} direct
                </span>
              </div>
              <div className="mt-4 space-y-3">
                {directBots.length === 0 ? (
                  <div className="rounded-lg border border-slate-800 bg-slate-950/45 px-4 py-3 text-xs text-slate-400">
                    No direct runtimes found.
                  </div>
                ) : (
                  directBots.map((bot) => {
                    const isExpanded = expandedBot === bot.instance_id;
                    return (
                      <BotCard
                        key={bot.instance_id}
                        bot={bot}
                        isExpanded={isExpanded}
                        actionLoading={actionLoading}
                        onToggleExpand={(instanceId) =>
                          setExpandedBot((current) => (current === instanceId ? null : instanceId))
                        }
                        onStart={(instanceId) => setPendingAction({ kind: 'start', instanceId })}
                        onStop={(instanceId) => setPendingAction({ kind: 'stop', instanceId })}
                        onRestart={(instanceId) =>
                          setPendingAction({ kind: 'restart', instanceId })
                        }
                        onDelete={(instanceId) => setPendingAction({ kind: 'delete', instanceId })}
                      />
                    );
                  })
                )}
              </div>
            </div>

            <div className="rounded-lg border border-cyan-900/70 bg-cyan-950/12 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-cyan-100">Strategy-managed runtimes</h3>
                  <p className="mt-1 text-xs text-cyan-300/80">
                    Hidden by default to keep Bots focused. Show them when you need a combined
                    runtime check.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setShowManagedRuntimes((current) => !current)}
                  className="rounded-xl border border-cyan-800/70 bg-cyan-950/45 px-3 py-2 text-xs font-medium text-cyan-200 transition hover:bg-cyan-900/40"
                >
                  {showManagedRuntimes
                    ? `Hide managed runtimes (${strategyManagedBots.length})`
                    : `Show managed runtimes (${strategyManagedBots.length})`}
                </button>
              </div>
              <p className="mt-2 text-[11px] text-cyan-300/70">
                Preference is saved for this browser.
              </p>

              {showManagedRuntimes ? (
                <div className="mt-4 space-y-3">
                  {strategyManagedBots.length === 0 ? (
                    <div className="rounded-lg border border-cyan-900/50 bg-slate-950/35 px-4 py-3 text-xs text-cyan-100/80">
                      No strategy-managed runtimes are currently visible.
                    </div>
                  ) : (
                    strategyManagedBots.map((bot) => {
                      const isExpanded = expandedBot === bot.instance_id;
                      return (
                        <BotCard
                          key={bot.instance_id}
                          bot={bot}
                          isExpanded={isExpanded}
                          actionLoading={actionLoading}
                          onToggleExpand={(instanceId) =>
                            setExpandedBot((current) =>
                              current === instanceId ? null : instanceId
                            )
                          }
                          onStart={(instanceId) => setPendingAction({ kind: 'start', instanceId })}
                          onStop={(instanceId) => setPendingAction({ kind: 'stop', instanceId })}
                          onRestart={(instanceId) =>
                            setPendingAction({ kind: 'restart', instanceId })
                          }
                          onDelete={(instanceId) =>
                            setPendingAction({ kind: 'delete', instanceId })
                          }
                        />
                      );
                    })
                  )}
                </div>
              ) : (
                <div className="mt-4 rounded-lg border border-cyan-900/45 bg-slate-950/35 px-4 py-3 text-xs text-cyan-100/80">
                  Managed runtimes are hidden by default to keep this desk focused.
                </div>
              )}
            </div>
          </div>
        )}
      </section>

      {pendingActionConfig && (
        <ActionDialog
          open
          title={pendingActionConfig.title}
          description={pendingActionConfig.description}
          confirmLabel={pendingActionConfig.confirmLabel}
          confirmTone={pendingActionConfig.confirmTone}
          onClose={() => setPendingAction(null)}
          onConfirm={() => void confirmPendingAction()}
          loading={actionLoading !== null}
          details={
            pendingBot && (
              <div className="space-y-2">
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                  Runtime context
                </p>
                <div className="grid gap-2 sm:grid-cols-2">
                  <div>
                    <p className="text-xs text-slate-500">Instance</p>
                    <p className="text-sm font-semibold text-white">{pendingBot.instance_id}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Status</p>
                    <p className="text-sm font-semibold text-white">{pendingBot.status}</p>
                  </div>
                </div>
              </div>
            )
          }
        />
      )}
    </>
  );

  if (embedded) {
    return <div className="space-y-6">{content}</div>;
  }

  return (
    <PageContainer size="wide" className="space-y-6">
      {content}
    </PageContainer>
  );
};

export default BotManager;
