import { AlertCircle, ChevronDown, ChevronUp, Pause, Play, Plus, RefreshCw, Trash2, Zap } from 'lucide-react';
import React, { useCallback, useEffect, useState } from 'react';
import api from '../api';

interface BotInstance {
  instance_id: string;
  status: 'CREATED' | 'RUNNING' | 'STOPPED' | 'FAILED' | 'ERROR';
  process_id?: number;
  configuration?: Record<string, unknown>;
  created_at?: string;
  started_at?: string;
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

const BotManager: React.FC = () => {
  const [bots, setBots] = useState<BotInstance[]>([]);
  const [selectedBot, setSelectedBot] = useState<BotInstance | null>(null);
  const [botStats, setBotStats] = useState<Record<string, BotStats>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [expandedBot, setExpandedBot] = useState<string | null>(null);

  // Form state
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

  // Load bot instances
  const loadBots = useCallback(async () => {
    try {
      setLoading(true);
      const response = await api.listBotInstances(0, 100);
      if (response.success && response.data) {
        const botList = response.data.bots || response.data;
        setBots(Array.isArray(botList) ? botList : []);
        setError(null);
      }
    } catch (err) {
      console.error('Failed to load bots:', err);
      setError(err instanceof Error ? err.message : 'Failed to load bot instances');
    } finally {
      setLoading(false);
    }
  }, []);

  // Load stats for all bots
  const loadAllStats = useCallback(async () => {
    const statsMap: Record<string, BotStats> = {};
    for (const bot of bots) {
      try {
        const response = await api.getBotStats(bot.instance_id);
        if (response.success && response.data && typeof response.data === 'object') {
          statsMap[bot.instance_id] = response.data as unknown as BotStats;
        }
      } catch (err) {
        console.warn(`Failed to load stats for bot ${bot.instance_id}:`, err);
      }
    }
    setBotStats(statsMap);
  }, [bots]);

  // Initial load and set up refresh interval
  useEffect(() => {
    loadBots();
  }, [loadBots]);

  // Auto-refresh bots and stats every 10 seconds
  useEffect(() => {
    loadAllStats();
    const interval = setInterval(() => {
      loadBots();
      loadAllStats();
    }, 10000);

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [bots.length, loadBots, loadAllStats]);

  // Create new bot instance
  const handleCreateBot = async () => {
    try {
      if (!createForm.instance_id || !createForm.address || !createForm.mnemonic) {
        setError('Please fill all required fields');
        return;
      }

      setLoading(true);
      const response = await api.createBotInstance({
        instance_id: createForm.instance_id,
        credentials: {
          chain_id: createForm.chain_id,
          address: createForm.address,
          mnemonic: createForm.mnemonic,
        },
        trading_params: {
          is_testnet: createForm.is_testnet,
          zscore_threshold: createForm.zscore_threshold,
          max_half_life: createForm.max_half_life,
          usd_per_trade: createForm.usd_per_trade,
        },
      });

      if (response.success) {
        setShowCreateForm(false);
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
        loadBots();
        setError(null);
      }
    } catch (err) {
      console.error('Failed to create bot:', err);
      const message = err instanceof Error ? err.message : 'Failed to create bot instance';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  // Start bot instance
  const handleStartBot = async (instanceId: string) => {
    try {
      setLoading(true);
      const response = await api.startBotInstance(instanceId);
      if (response.success) {
        loadBots();
        setError(null);
      }
    } catch (err) {
      console.error('Failed to start bot:', err);
      const message = err instanceof Error ? err.message : 'Failed to start bot';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  // Stop bot instance
  const handleStopBot = async (instanceId: string) => {
    try {
      setLoading(true);
      const response = await api.stopBotInstance(instanceId);
      if (response.success) {
        loadBots();
        setError(null);
      }
    } catch (err) {
      console.error('Failed to stop bot:', err);
      const message = err instanceof Error ? err.message : 'Failed to stop bot';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  // Restart bot instance
  const handleRestartBot = async (instanceId: string) => {
    try {
      setLoading(true);
      const response = await api.restartBotInstance(instanceId);
      if (response.success) {
        loadBots();
        setError(null);
      }
    } catch (err) {
      console.error('Failed to restart bot:', err);
      const message = err instanceof Error ? err.message : 'Failed to restart bot';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  // Delete bot instance
  const handleDeleteBot = async (instanceId: string) => {
    if (!window.confirm(`Are you sure you want to delete bot ${instanceId}?`)) {
      return;
    }

    try {
      setLoading(true);
      const response = await api.deleteBotInstance(instanceId);
      if (response.success) {
        loadBots();
        if (selectedBot?.instance_id === instanceId) {
          setSelectedBot(null);
        }
        setError(null);
      }
    } catch (err) {
      console.error('Failed to delete bot:', err);
      const message = err instanceof Error ? err.message : 'Failed to delete bot';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  // Get status badge color
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'RUNNING':
        return 'bg-green-100 text-green-800';
      case 'STOPPED':
        return 'bg-yellow-100 text-yellow-800';
      case 'FAILED':
      case 'ERROR':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Bot Manager</h1>
          <p className="text-slate-400 mt-1">Create and manage trading bot instances</p>
        </div>
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition"
        >
          <Plus size={20} />
          New Bot
        </button>
      </div>

      {/* Error message */}
      {error && (
        <div className="bg-red-900 border border-red-700 text-red-100 px-4 py-3 rounded-lg flex items-center gap-2">
          <AlertCircle size={20} />
          {error}
        </div>
      )}

      {/* Create Bot Form */}
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
              <label className="block text-sm font-medium text-slate-300 mb-1">Z-Score Threshold</label>
              <input
                type="number"
                step="0.1"
                value={createForm.zscore_threshold}
                onChange={(e) => setCreateForm({ ...createForm, zscore_threshold: parseFloat(e.target.value) })}
                className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Max Half-Life (hours)</label>
              <input
                type="number"
                value={createForm.max_half_life}
                onChange={(e) => setCreateForm({ ...createForm, max_half_life: parseInt(e.target.value) })}
                className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">USD Per Trade</label>
              <input
                type="number"
                step="0.01"
                value={createForm.usd_per_trade}
                onChange={(e) => setCreateForm({ ...createForm, usd_per_trade: parseFloat(e.target.value) })}
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
              onClick={handleCreateBot}
              disabled={loading}
              className="flex-1 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white px-4 py-2 rounded-lg transition"
            >
              {loading ? 'Creating...' : 'Create Bot'}
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

      {/* Bot List */}
      <div className="space-y-4">
        {loading && bots.length === 0 ? (
          <div className="text-center text-slate-400 py-8">Loading bots...</div>
        ) : bots.length === 0 ? (
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-8 text-center">
            <Zap size={32} className="mx-auto mb-2 text-slate-500" />
            <p className="text-slate-400">No bot instances yet. Create one to get started!</p>
          </div>
        ) : (
          bots.map((bot) => {
            const stats = botStats[bot.instance_id];
            const isExpanded = expandedBot === bot.instance_id;

            return (
              <div key={bot.instance_id} className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
                {/* Bot Header */}
                <div className="p-4 flex items-center justify-between hover:bg-slate-750 transition cursor-pointer"
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
                      <h3 className="font-semibold text-white">{bot.instance_id}</h3>
                      <p className="text-sm text-slate-400">
                        Started: {bot.started_at ? new Date(bot.started_at).toLocaleString() : 'Never'}
                      </p>
                    </div>

                    <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(bot.status)}`}>
                      {bot.status}
                    </span>

                    {stats && (
                      <div className="ml-auto text-right">
                        <p className="text-sm font-semibold text-white">
                          P&L: <span className={stats.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}>
                            ${stats.total_pnl.toFixed(2)}
                          </span>
                        </p>
                        <p className="text-xs text-slate-400">
                          Positions: {stats.open_positions} open, {stats.closed_positions} closed
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Action Buttons */}
                  <div className="flex gap-2 ml-4" onClick={(e) => e.stopPropagation()}>
                    {bot.status === 'RUNNING' ? (
                      <>
                        <button
                          onClick={() => handleStopBot(bot.instance_id)}
                          className="p-2 bg-yellow-600 hover:bg-yellow-700 text-white rounded transition"
                          title="Stop bot"
                        >
                          <Pause size={18} />
                        </button>
                        <button
                          onClick={() => handleRestartBot(bot.instance_id)}
                          className="p-2 bg-blue-600 hover:bg-blue-700 text-white rounded transition"
                          title="Restart bot"
                        >
                          <RefreshCw size={18} />
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => handleStartBot(bot.instance_id)}
                        className="p-2 bg-green-600 hover:bg-green-700 text-white rounded transition"
                        title="Start bot"
                      >
                        <Play size={18} />
                      </button>
                    )}
                    <button
                      onClick={() => handleDeleteBot(bot.instance_id)}
                      className="p-2 bg-red-600 hover:bg-red-700 text-white rounded transition"
                      title="Delete bot"
                    >
                      <Trash2 size={18} />
                    </button>
                  </div>
                </div>

                {/* Expanded Details */}
                {isExpanded && (
                  <div className="bg-slate-750 border-t border-slate-700 p-4 space-y-3">
                    {stats && (
                      <div className="grid grid-cols-3 gap-4">
                        <div className="bg-slate-800 p-3 rounded">
                          <p className="text-xs text-slate-400">Total P&L</p>
                          <p className={`text-lg font-semibold ${stats.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            ${stats.total_pnl.toFixed(2)}
                          </p>
                        </div>
                        <div className="bg-slate-800 p-3 rounded">
                          <p className="text-xs text-slate-400">Win Rate</p>
                          <p className="text-lg font-semibold text-white">{(stats.win_rate * 100).toFixed(1)}%</p>
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
