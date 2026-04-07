import {
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Trash2,
  Zap,
} from 'lucide-react';
import { useQueries, useQueryClient } from '@tanstack/react-query';
import React, { useEffect, useState } from 'react';
import { classifyApiError } from '../api';
import {
  useBotInstances,
  useCreateBotInstance,
  useDeleteBotInstance,
  useRestartBotInstance,
  useStartBotInstance,
  useStopBotInstance,
} from '../api/hooks';
import { enhancedApiClient } from '../api/enhancedClient';
import { queryKeys } from '../api/queryClient';

interface BotInstance {
  instance_id: string;
  status: 'CREATED' | 'RUNNING' | 'STOPPED' | 'FAILED' | 'ERROR' | 'STARTING' | 'STOPPING';
  process_id?: number;
  configuration?: Record<string, unknown>;
  created_at?: string;
  started_at?: string;
  instance_name?: string;
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

  return {
    total_positions: totalTrades,
    open_positions: toNumber(raw.open_positions),
    closed_positions: totalTrades,
    total_pnl: toNumber(
      tradeStatistics.net_profit,
      toNumber(botStatistics.total_profit_loss, toNumber(raw.total_pnl))
    ),
    realized_pnl: toNumber(tradeStatistics.total_profit, toNumber(raw.realized_pnl)),
    unrealized_pnl: toNumber(raw.unrealized_pnl),
    total_trades: totalTrades,
    win_rate: toNumber(tradeStatistics.win_rate, toNumber(botStatistics.win_rate)) / 100,
    last_update:
      typeof raw.last_update === 'string' ? raw.last_update : new Date().toISOString(),
  };
};

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

const BotManager: React.FC = () => {
  const queryClient = useQueryClient();
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

  const statsQueries = useQueries({
    queries: bots.map((bot) => ({
      queryKey: queryKeys.botStats(bot.instance_id),
      queryFn: () => enhancedApiClient.getBotStats(bot.instance_id),
      enabled: !!bot.instance_id,
      staleTime: 30 * 1000,
      gcTime: 5 * 60 * 1000,
    })),
  });

  const statsByBotId = bots.reduce<Record<string, BotStats>>((acc, bot, index) => {
    const raw = statsQueries[index]?.data;
    if (raw && isRecord(raw)) {
      acc[bot.instance_id] = mapBotStats(raw);
    } else {
      acc[bot.instance_id] = { ...EMPTY_BOT_STATS };
    }
    return acc;
  }, {});

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
      void queryClient.invalidateQueries({ queryKey: ['bots'] });
    }, 10000);

    return () => {
      clearInterval(interval);
    };
  }, [queryClient]);

  const refreshBots = async () => {
    setError(null);
    await queryClient.invalidateQueries({ queryKey: ['bots'] });
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

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'RUNNING':
        return 'bg-green-100 text-green-800';
      case 'STOPPED':
        return 'bg-yellow-100 text-yellow-800';
      case 'STARTING':
      case 'STOPPING':
        return 'bg-blue-100 text-blue-800';
      case 'FAILED':
      case 'ERROR':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Bot Manager</h1>
          <p className="text-slate-400 mt-1">Create, run, and monitor trading bot instances</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => void refreshBots()}
            disabled={botsQuery.isFetching}
            className="flex items-center gap-2 bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-lg transition disabled:opacity-60"
          >
            <RefreshCw size={18} className={botsQuery.isFetching ? 'animate-spin' : ''} />
            {isRefreshing ? 'Refreshing...' : 'Refresh'}
          </button>
          <button
            onClick={() => setShowCreateForm(!showCreateForm)}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition"
          >
            <Plus size={20} />
            New Bot
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-900 border border-red-700 text-red-100 px-4 py-3 rounded-lg flex items-center gap-2">
          <AlertCircle size={20} />
          {error}
        </div>
      )}

      {showCreateForm && (
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-6 space-y-4">
          <h2 className="text-xl font-semibold text-white">Create New Bot Instance</h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Instance ID *</label>
              <input
                type="text"
                placeholder="e.g., btc-eth-bot-01"
                value={createForm.instance_id}
                onChange={(e) => setCreateForm({ ...createForm, instance_id: e.target.value })}
                className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white placeholder-slate-400"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Chain ID</label>
              <select
                value={createForm.chain_id}
                onChange={(e) => setCreateForm({ ...createForm, chain_id: e.target.value })}
                className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white"
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
                className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white placeholder-slate-400"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Mnemonic *</label>
              <input
                type="password"
                placeholder="Your seed phrase..."
                value={createForm.mnemonic}
                onChange={(e) => setCreateForm({ ...createForm, mnemonic: e.target.value })}
                className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white placeholder-slate-400"
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
                className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white"
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
                className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white"
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
                className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white"
              />
            </div>

            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-slate-300 mt-6">
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
              onClick={() => void handleCreateBot()}
              disabled={isCreating}
              className="flex-1 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white px-4 py-2 rounded-lg transition"
            >
              {isCreating ? 'Creating...' : 'Create Bot'}
            </button>
            <button
              onClick={() => setShowCreateForm(false)}
              className="flex-1 bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-lg transition"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="space-y-4">
        {isInitialLoading ? (
          <div className="text-center text-slate-400 py-8">Loading bots...</div>
        ) : bots.length === 0 ? (
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-8 text-center">
            <Zap size={32} className="mx-auto mb-2 text-slate-500" />
            <p className="text-slate-400">No bot instances yet. Create one to get started!</p>
          </div>
        ) : (
          bots.map((bot) => {
            const stats = statsByBotId[bot.instance_id];
            const isExpanded = expandedBot === bot.instance_id;

            return (
              <div
                key={bot.instance_id}
                className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden"
              >
                <div
                  className="p-4 flex items-center justify-between hover:bg-slate-750 transition cursor-pointer"
                  onClick={() => setExpandedBot(isExpanded ? null : bot.instance_id)}
                >
                  <div className="flex items-center gap-4 flex-1">
                    <button
                      className="text-slate-400 hover:text-white"
                      onClick={(e) => {
                        e.stopPropagation();
                        setExpandedBot(isExpanded ? null : bot.instance_id);
                      }}
                    >
                      {isExpanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                    </button>

                    <div>
                      <h3 className="font-semibold text-white">
                        {bot.instance_name || bot.instance_id}
                      </h3>
                      <p className="text-xs text-slate-500">ID: {bot.instance_id}</p>
                      <p className="text-sm text-slate-400">
                        Started: {bot.started_at ? new Date(bot.started_at).toLocaleString() : 'Never'}
                      </p>
                    </div>

                    <span
                      className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(bot.status)}`}
                    >
                      {bot.status}
                    </span>

                    {stats && (
                      <div className="ml-auto text-right">
                        <p className="text-sm font-semibold text-white">
                          P&amp;L:{' '}
                          <span
                            className={stats.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}
                          >
                            ${stats.total_pnl.toFixed(2)}
                          </span>
                        </p>
                        <p className="text-xs text-slate-400">
                          Positions: {stats.open_positions} open, {stats.closed_positions} closed
                        </p>
                      </div>
                    )}
                  </div>

                  <div className="flex gap-2 ml-4" onClick={(e) => e.stopPropagation()}>
                    {bot.status === 'RUNNING' ? (
                      <>
                        <button
                          onClick={() => void handleStopBot(bot.instance_id)}
                          disabled={actionLoading === `stop:${bot.instance_id}`}
                          className="p-2 bg-yellow-600 hover:bg-yellow-700 text-white rounded transition disabled:opacity-60"
                          title="Stop bot"
                        >
                          <Pause size={18} />
                        </button>
                        <button
                          onClick={() => void handleRestartBot(bot.instance_id)}
                          disabled={actionLoading === `restart:${bot.instance_id}`}
                          className="p-2 bg-blue-600 hover:bg-blue-700 text-white rounded transition disabled:opacity-60"
                          title="Restart bot"
                        >
                          <RefreshCw size={18} />
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => void handleStartBot(bot.instance_id)}
                        disabled={actionLoading === `start:${bot.instance_id}`}
                        className="p-2 bg-green-600 hover:bg-green-700 text-white rounded transition disabled:opacity-60"
                        title="Start bot"
                      >
                        <Play size={18} />
                      </button>
                    )}
                    <button
                      onClick={() => void handleDeleteBot(bot.instance_id)}
                      disabled={actionLoading === `delete:${bot.instance_id}`}
                      className="p-2 bg-red-600 hover:bg-red-700 text-white rounded transition disabled:opacity-60"
                      title="Delete bot"
                    >
                      <Trash2 size={18} />
                    </button>
                  </div>
                </div>

                {isExpanded && (
                  <div className="bg-slate-750 border-t border-slate-700 p-4 space-y-3">
                    {stats && (
                      <div className="grid grid-cols-3 gap-4">
                        <div className="bg-slate-800 p-3 rounded">
                          <p className="text-xs text-slate-400">Total P&amp;L</p>
                          <p
                            className={`text-lg font-semibold ${stats.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}
                          >
                            ${stats.total_pnl.toFixed(2)}
                          </p>
                        </div>
                        <div className="bg-slate-800 p-3 rounded">
                          <p className="text-xs text-slate-400">Win Rate</p>
                          <p className="text-lg font-semibold text-white">
                            {(stats.win_rate * 100).toFixed(1)}%
                          </p>
                        </div>
                        <div className="bg-slate-800 p-3 rounded">
                          <p className="text-xs text-slate-400">Total Trades</p>
                          <p className="text-lg font-semibold text-white">{stats.total_trades}</p>
                        </div>
                      </div>
                    )}

                    {bot.configuration && (
                      <div className="bg-slate-800 p-3 rounded">
                        <p className="text-xs text-slate-400 mb-2">Configuration</p>
                        <pre className="text-xs text-slate-300 overflow-auto max-h-32">
                          {JSON.stringify(bot.configuration, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default BotManager;
