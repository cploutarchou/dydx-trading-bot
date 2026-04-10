import {
  Activity,
  AlertCircle,
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
import React, { useEffect, useState } from 'react';
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
import { PageContainer } from './PageContainer';

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
        error_message:
          typeof record.error_message === 'string' ? record.error_message : undefined,
      };
    })
    .filter((bot) => bot.instance_id.length > 0);
};

const mapBotStats = (raw: Record<string, unknown>): BotStats => {
  const botStatistics =
    typeof raw.bot_statistics === 'object' && raw.bot_statistics
      ? (raw.bot_statistics as Record<string, unknown>)
      : {};

  const tradeStatistics =
    typeof raw.trade_statistics === 'object' && raw.trade_statistics
      ? (raw.trade_statistics as Record<string, unknown>)
      : {};

  const totalTrades = toNumber(tradeStatistics.total_trades, toNumber(botStatistics.total_trades));
  const openPositions = toNumber(raw.open_positions, toNumber(raw.total_open_positions));
  const closedPositions = toNumber(raw.closed_positions, toNumber(raw.daily_trades_closed, totalTrades));
  const totalPnl = toNumber(
    tradeStatistics.net_profit,
    toNumber(
      botStatistics.total_profit_loss,
      toNumber(raw.total_pnl, toNumber(raw.total_unrealized_pnl, toNumber(raw.daily_pnl)))
    )
  );
  const winRateRaw = toNumber(
    tradeStatistics.win_rate,
    toNumber(botStatistics.win_rate, toNumber(raw.win_rate, toNumber(raw.daily_win_rate)))
  );

  return {
    total_positions: openPositions + closedPositions,
    open_positions: openPositions,
    closed_positions: closedPositions,
    total_pnl: totalPnl,
    realized_pnl: toNumber(tradeStatistics.total_profit, toNumber(raw.realized_pnl)),
    unrealized_pnl: toNumber(raw.unrealized_pnl),
    total_trades: totalTrades,
    win_rate: Math.abs(winRateRaw) <= 1 ? winRateRaw : winRateRaw / 100,
    last_update:
      typeof raw.last_update === 'string'
        ? raw.last_update
        : typeof raw.updated_at === 'string'
          ? raw.updated_at
          : new Date().toISOString(),
    degraded: raw.degraded === true,
    warning: typeof raw.warning === 'string' ? raw.warning : undefined,
  };
};

const isManagedStrategyRuntime = (bot: BotInstance): boolean =>
  /^strategy-\d+-\d+$/.test(bot.instance_id) || bot.strategy === 'cointegration' || bot.strategy === 'mean_reversion';

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
  const statsQuery = useBotStats(bot.instance_id, true);
  const liveStatsQuery = useBotRuntimeStatsStream(bot.instance_id, shouldStreamRuntime);
  const rawStats =
    liveStatsQuery.data && isRecord(liveStatsQuery.data)
      ? liveStatsQuery.data
      : statsQuery.data && isRecord(statsQuery.data)
        ? statsQuery.data
        : null;
  const stats = rawStats ? mapBotStats(rawStats) : { ...EMPTY_BOT_STATS };
  const statusTone = getStatusTone(bot.status, stats.degraded);
  const streamLabel = shouldStreamRuntime
    ? liveStatsQuery.isConnected
      ? 'Live runtime stream connected'
      : 'Runtime stream reconnecting'
    : 'Polling runtime state';

  return (
    <div className="operator-section-card overflow-hidden">
      <div
        className="flex cursor-pointer flex-col gap-4 p-5 transition hover:bg-slate-900/20 xl:flex-row xl:items-start xl:justify-between"
        onClick={() => onToggleExpand(bot.instance_id)}
      >
        <div className="flex flex-1 items-start gap-4">
          <button
            type="button"
            className="rounded-xl border border-slate-800 bg-slate-950/70 p-2 text-slate-400 hover:text-white"
            onClick={(e) => {
              e.stopPropagation();
              onToggleExpand(bot.instance_id);
            }}
          >
            {isExpanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
          </button>

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-semibold text-white">{bot.instance_name || bot.instance_id}</h3>
              <span className="operator-status-pill" data-tone={statusTone}>
                {bot.status}
              </span>
              {isManagedStrategyRuntime(bot) && (
                <span className="operator-status-pill" data-tone="accent">
                  Managed runtime
                </span>
              )}
            </div>
            <p className="mt-2 text-xs text-slate-500">ID: {bot.instance_id}</p>
            {isManagedStrategyRuntime(bot) && (
              <p className="mt-1 text-xs text-cyan-400">Managed by strategy runtime workflow</p>
            )}
            <p className="mt-2 text-sm text-slate-400">
              Started: {bot.started_at ? formatDateTime(bot.started_at) : 'Never'}
            </p>
            <p className={`mt-1 text-xs ${liveStatsQuery.isConnected ? 'text-emerald-400' : 'text-slate-500'}`}>
              {streamLabel}
            </p>
            {bot.error_message && <p className="mt-1 text-xs text-amber-300">{bot.error_message}</p>}
          </div>
        </div>

        <div className="grid min-w-full gap-3 xl:min-w-[360px]" onClick={(e) => e.stopPropagation()}>
          <div className="operator-mini-grid">
            <div className="metric-tile px-4 py-4">
              <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Total P&amp;L</p>
              <p className={`mt-2 text-sm font-semibold ${stats.total_pnl >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                {formatUsd(stats.total_pnl)}
              </p>
            </div>
            <div className="metric-tile px-4 py-4">
              <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Open positions</p>
              <p className="mt-2 text-sm font-semibold text-white">{stats.open_positions}</p>
            </div>
            <div className="metric-tile px-4 py-4">
              <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Win rate</p>
              <p className="mt-2 text-sm font-semibold text-white">
                {(stats.win_rate * 100).toFixed(1)}%
              </p>
            </div>
          </div>

          {(stats.degraded || liveStatsQuery.error) && (
            <div className="rounded-2xl border border-amber-700/60 bg-amber-950/25 px-4 py-3 text-xs text-amber-200">
              {stats.warning || 'Runtime stats temporarily unavailable or reconnecting.'}
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            {bot.status === 'RUNNING' ? (
              <>
                <button
                  type="button"
                  onClick={() => onStop(bot.instance_id)}
                  disabled={actionLoading === `stop:${bot.instance_id}`}
                  className="rounded-xl bg-amber-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-amber-500 disabled:opacity-60"
                  title="Stop bot"
                >
                  <span className="inline-flex items-center gap-2">
                    <Pause size={16} />
                    Stop
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => onRestart(bot.instance_id)}
                  disabled={actionLoading === `restart:${bot.instance_id}`}
                  className="rounded-xl bg-blue-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:opacity-60"
                  title="Restart bot"
                >
                  <span className="inline-flex items-center gap-2">
                    <RefreshCw size={16} />
                    Restart
                  </span>
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={() => onStart(bot.instance_id)}
                disabled={actionLoading === `start:${bot.instance_id}`}
                className="rounded-xl bg-emerald-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-emerald-500 disabled:opacity-60"
                title="Start bot"
              >
                <span className="inline-flex items-center gap-2">
                  <Play size={16} />
                  Start
                </span>
              </button>
            )}
            <button
              type="button"
              onClick={() => onDelete(bot.instance_id)}
              disabled={actionLoading === `delete:${bot.instance_id}`}
              className="rounded-xl bg-rose-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-rose-500 disabled:opacity-60"
              title="Delete bot"
            >
              <span className="inline-flex items-center gap-2">
                <Trash2 size={16} />
                Delete
              </span>
            </button>
          </div>
        </div>
      </div>

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
              <p className="text-sm font-semibold text-white">{formatDateTime(stats.last_update)}</p>
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

const BotManager: React.FC = () => {
  const [error, setError] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [expandedBot, setExpandedBot] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

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

  const handleCreateBot = async () => {
    try {
      if (!createForm.instance_id || !createForm.address || !createForm.mnemonic) {
        setError('Please fill all required fields');
        return;
      }

      setError(null);
      await createBotMutation.mutateAsync(
        {
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
          },
          instance_name: createForm.instance_id,
          strategy: 'default',
        } as Parameters<typeof createBotMutation.mutateAsync>[0]
      );

      setShowCreateForm(false);
      resetCreateForm();
      await refreshBots();
    } catch (err) {
      console.error('Failed to create bot:', err);
      setError(toOperatorErrorMessage(err, 'Failed to create bot instance'));
    }
  };

  const runBotAction = async (
    actionKey: string,
    action: () => Promise<unknown>,
    fallbackMessage: string
  ) => {
    try {
      setActionLoading(actionKey);
      setError(null);
      await action();
      await refreshBots();
    } catch (err) {
      console.error(`${actionKey} failed:`, err);
      setError(toOperatorErrorMessage(err, fallbackMessage));
    } finally {
      setActionLoading(null);
    }
  };

  const handleStartBot = async (instanceId: string) =>
    runBotAction(
      `start:${instanceId}`,
      () => startBotMutation.mutateAsync({ instanceId }),
      'Failed to start bot'
    );

  const handleStopBot = async (instanceId: string) =>
    runBotAction(
      `stop:${instanceId}`,
      () => stopBotMutation.mutateAsync(instanceId),
      'Failed to stop bot'
    );

  const handleRestartBot = async (instanceId: string) =>
    runBotAction(
      `restart:${instanceId}`,
      () => restartBotMutation.mutateAsync(instanceId),
      'Failed to restart bot'
    );

  const handleDeleteBot = async (instanceId: string) => {
    if (!window.confirm(`Are you sure you want to delete bot ${instanceId}?`)) {
      return;
    }

    await runBotAction(
      `delete:${instanceId}`,
      () => deleteBotMutation.mutateAsync(instanceId),
      'Failed to delete bot'
    );
  };

  const isCreating = createBotMutation.isPending;
  const isRefreshing = botsQuery.isFetching && bots.length > 0;
  const isInitialLoading = botsQuery.isLoading && bots.length === 0;
  const runningBots = bots.filter((bot) => bot.status === 'RUNNING').length;
  const erroredBots = bots.filter((bot) => bot.status === 'FAILED' || bot.status === 'ERROR').length;
  const transitioningBots = bots.filter(
    (bot) => bot.status === 'STARTING' || bot.status === 'STOPPING'
  ).length;
  const managedBots = bots.filter((bot) => isManagedStrategyRuntime(bot)).length;

  return (
    <PageContainer size="wide" className="space-y-6">
      <section className="operator-hero px-6 py-6 sm:px-8 sm:py-8">
        <div className="relative grid gap-6 xl:grid-cols-[1.12fr,0.88fr]">
          <div>
            <div className="surface-label">
              <Zap className="h-3.5 w-3.5" />
              Runtime desk
            </div>
            <h1 className="mt-5 text-3xl font-bold text-white sm:text-4xl">Bot manager</h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">
              Manage live instances like an operator surface, not a settings form: health and
              degraded-state signals first, actions close to each runtime, and clearer create-flow
              context before credentials are submitted.
            </p>

            <div className="mt-5 flex flex-wrap gap-3">
              <div className="operator-status-pill" data-tone={runningBots > 0 ? 'positive' : 'warning'}>
                <Activity className="h-3.5 w-3.5" />
                {runningBots > 0 ? `${runningBots} running` : 'No active bots'}
              </div>
              <div className="operator-status-pill" data-tone={erroredBots > 0 ? 'danger' : 'accent'}>
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
              <p className="mt-1 text-xs text-slate-500">Known bot runtimes</p>
            </div>
            <div className="operator-hero-panel px-4 py-4">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Transitioning</p>
              <p className="mt-2 text-xl font-semibold text-white">{transitioningBots}</p>
              <p className="mt-1 text-xs text-slate-500">Starting or stopping</p>
            </div>
            <div className="operator-hero-panel px-4 py-4">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Refresh cadence</p>
              <p className="mt-2 text-xl font-semibold text-white">30s</p>
              <p className="mt-1 text-xs text-slate-500">Automatic desk refresh</p>
            </div>
            <div className="operator-hero-panel px-4 py-4">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Boundary</p>
              <p className="mt-2 text-xl font-semibold text-white">Backend-only</p>
              <p className="mt-1 text-xs text-slate-500">No direct bot API access from the browser</p>
            </div>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <div className="operator-stat-card p-5">
          <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Running</p>
          <p className="mt-2 text-2xl font-semibold text-emerald-300">{runningBots}</p>
          <p className="mt-1 text-xs text-slate-500">Instances currently live</p>
        </div>
        <div className="operator-stat-card p-5">
          <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Managed runtimes</p>
          <p className="mt-2 text-2xl font-semibold text-cyan-300">{managedBots}</p>
          <p className="mt-1 text-xs text-slate-500">Strategy-linked operators</p>
        </div>
        <div className="operator-stat-card p-5">
          <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Transitioning</p>
          <p className="mt-2 text-2xl font-semibold text-blue-300">{transitioningBots}</p>
          <p className="mt-1 text-xs text-slate-500">Starting or stopping now</p>
        </div>
        <div className="operator-stat-card p-5">
          <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Attention needed</p>
          <p className={`mt-2 text-2xl font-semibold ${erroredBots > 0 ? 'text-rose-300' : 'text-emerald-300'}`}>
            {erroredBots}
          </p>
          <p className="mt-1 text-xs text-slate-500">Failed or error state runtimes</p>
        </div>
      </section>

      {error && (
        <div className="flex items-center gap-2 rounded-2xl border border-red-700 bg-red-950/40 px-4 py-3 text-red-100">
          <AlertCircle size={20} />
          {error}
        </div>
      )}

      <section className="grid grid-cols-1 gap-6 xl:grid-cols-[0.95fr,1.05fr]">
        <div className="operator-section-card p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-white">Runtime actions</h2>
              <p className="mt-1 text-sm text-slate-400">
                Refresh runtime state, create a new instance, or move into strategy runtime.
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
            <Link to="/strategies/manage" className="operator-action-card p-4">
              <p className="text-sm font-semibold text-white">Open strategy runtime</p>
              <p className="mt-1 text-xs text-slate-500">
                Monitor managed strategy processes beside direct bot instances.
              </p>
            </Link>
            <Link to="/settings" className="operator-action-card p-4">
              <p className="text-sm font-semibold text-white">Review credentials and settings</p>
              <p className="mt-1 text-xs text-slate-500">
                Keep operator configuration and credentials aligned before activating new bots.
              </p>
            </Link>
          </div>
        </div>

        <div className="operator-section-card p-5">
          <h2 className="text-lg font-semibold text-white">Operator notes</h2>
          <div className="mt-4 space-y-3">
            <div className="rounded-2xl border border-slate-800 bg-slate-950/45 px-4 py-4">
              <p className="text-sm font-semibold text-white">Degraded state should be explicit</p>
              <p className="mt-1 text-sm leading-6 text-slate-400">
                Live runtime stats can reconnect independently of the instance lifecycle. Treat a
                reconnecting stream as an operator signal, not a silent failure.
              </p>
            </div>
            <div className="rounded-2xl border border-slate-800 bg-slate-950/45 px-4 py-4">
              <p className="text-sm font-semibold text-white">Instance creation is operational</p>
              <p className="mt-1 text-sm leading-6 text-slate-400">
                The create flow now sits inside the runtime desk so credential, network, and
                trading-parameter choices feel part of one controlled setup workflow.
              </p>
            </div>
          </div>
        </div>
      </section>

      {showCreateForm && (
        <div className="operator-section-card p-6 space-y-4">
          <div>
            <h2 className="text-xl font-semibold text-white">Create new bot instance</h2>
            <p className="mt-1 text-sm text-slate-400">
              Configure the runtime, credentials, and basic trading parameters before the instance
              enters the desk.
            </p>
          </div>

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
              Review each instance with live stream state, action controls, and expanded runtime detail.
            </p>
          </div>
          <span className="operator-status-pill" data-tone={bots.length > 0 ? 'accent' : 'warning'}>
            {bots.length} instance{bots.length === 1 ? '' : 's'}
          </span>
        </div>

        {isInitialLoading ? (
          <div className="operator-section-card py-10 text-center text-slate-400">Loading bots...</div>
        ) : bots.length === 0 ? (
          <div className="operator-section-card p-8 text-center">
            <Zap size={32} className="mx-auto mb-2 text-slate-500" />
            <p className="text-slate-400">No bot instances yet. Create one to get started!</p>
          </div>
        ) : (
          bots.map((bot) => {
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
                onStart={(instanceId) => void handleStartBot(instanceId)}
                onStop={(instanceId) => void handleStopBot(instanceId)}
                onRestart={(instanceId) => void handleRestartBot(instanceId)}
                onDelete={(instanceId) => void handleDeleteBot(instanceId)}
              />
            );
          })
        )}
      </section>
    </PageContainer>
  );
};

export default BotManager;
