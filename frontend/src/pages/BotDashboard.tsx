import { Activity, AlertTriangle, RefreshCw, TrendingUp, Zap } from 'lucide-react';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import api from '../api';
import BotManager from '../components/BotManager';

type TabType = 'overview' | 'manager' | 'positions' | 'alerts';

interface BotListItem {
  instance_id: string;
  status: string;
}

interface BotStatsData {
  instance_id: string;
  status: string;
  total_pnl: number;
  realized_pnl: number;
  unrealized_pnl: number;
  total_positions: number;
  open_positions: number;
  total_trades: number;
  win_rate: number;
  last_update: string;
}

interface PositionData {
  position_id: string;
  market_1: string;
  market_2: string;
  entry_time: string;
  z_score: number;
  status: string;
  entry_price_1?: number;
  entry_price_2?: number;
}

interface AlertDataType {
  timestamp: string;
  title?: string;
  message?: string;
  description?: string;
}

const asArray = <T,>(value: unknown): T[] => {
  if (Array.isArray(value)) {
    return value as T[];
  }
  return [];
};

const getStatusBadge = (status: string): string => {
  const styles: Record<string, string> = {
    RUNNING: 'bg-green-100 text-green-800',
    STOPPED: 'bg-yellow-100 text-yellow-800',
    FAILED: 'bg-red-100 text-red-800',
    ERROR: 'bg-red-100 text-red-800',
    PAUSED: 'bg-orange-100 text-orange-800',
  };

  return styles[status] || 'bg-gray-100 text-gray-800';
};

const formatCurrency = (value: number): string => {
  return `${value >= 0 ? '' : '-'}$${Math.abs(value).toFixed(2)}`;
};

const formatWinRate = (value: number): string => {
  const normalized = value <= 1 ? value * 100 : value;
  return `${normalized.toFixed(1)}%`;
};

const BotDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [botList, setBotList] = useState<BotStatsData[]>([]);
  const [selectedBot, setSelectedBot] = useState<string | null>(null);
  const [botPositions, setBotPositions] = useState<PositionData[]>([]);
  const [botAlerts, setBotAlerts] = useState<AlertDataType[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const selectedBotStats = useMemo(
    () => botList.find((bot) => bot.instance_id === selectedBot) ?? null,
    [botList, selectedBot]
  );

  const loadBots = useCallback(async () => {
    try {
      setLoading(true);

      const response = await api.listBotInstances(0, 100);
      const rawBotData = response.data as { bots?: unknown } | unknown;
      const instances = asArray<BotListItem>(
        (rawBotData as { bots?: unknown })?.bots ?? rawBotData
      );

      const statsResponses = await Promise.all(
        instances.map(async (bot) => {
          try {
            return await api.getBotStats(bot.instance_id);
          } catch {
            return null;
          }
        })
      );

      const statsData: BotStatsData[] = instances.map((bot, index) => {
        const rawStats = statsResponses[index]?.data as Record<string, unknown> | undefined;
        return {
          instance_id: bot.instance_id,
          status: bot.status || String(rawStats?.status || 'UNKNOWN'),
          total_pnl: Number(rawStats?.total_pnl || 0),
          realized_pnl: Number(rawStats?.realized_pnl || 0),
          unrealized_pnl: Number(rawStats?.unrealized_pnl || 0),
          total_positions: Number(rawStats?.total_positions || 0),
          open_positions: Number(rawStats?.open_positions || 0),
          total_trades: Number(rawStats?.total_trades || 0),
          win_rate: Number(rawStats?.win_rate || 0),
          last_update: String(rawStats?.last_update || new Date().toISOString()),
        };
      });

      setBotList(statsData);
      setLastUpdated(new Date());
      if (statsData.length > 0 && !selectedBot) {
        setSelectedBot(statsData[0].instance_id);
      }
      setError(null);
    } catch (err) {
      console.error('Failed to load bots:', err);
      setError(err instanceof Error ? err.message : 'Failed to load bots');
    } finally {
      setLoading(false);
    }
  }, [selectedBot]);

  const loadPositions = useCallback(async () => {
    if (!selectedBot) {
      setBotPositions([]);
      return;
    }

    try {
      const response = await api.getBotCurrentPositions(selectedBot);
      const rawData = response.data as { positions?: unknown } | unknown;
      const positions = asArray<PositionData>(
        (rawData as { positions?: unknown })?.positions ?? rawData
      );
      setBotPositions(positions);
    } catch (err) {
      console.error('Failed to load positions:', err);
      setError(err instanceof Error ? err.message : 'Failed to load positions');
    }
  }, [selectedBot]);

  const loadAlerts = useCallback(async () => {
    if (!selectedBot) {
      setBotAlerts([]);
      return;
    }

    try {
      const response = await api.getBotAlerts(selectedBot, 0, 50);
      const rawData = response.data as { alerts?: unknown } | unknown;
      const alerts = asArray<AlertDataType>((rawData as { alerts?: unknown })?.alerts ?? rawData);
      setBotAlerts(alerts);
    } catch (err) {
      console.error('Failed to load alerts:', err);
      setError(err instanceof Error ? err.message : 'Failed to load alerts');
    }
  }, [selectedBot]);

  useEffect(() => {
    void loadBots();
  }, [loadBots]);

  useEffect(() => {
    if (activeTab === 'positions') {
      void loadPositions();
    } else if (activeTab === 'alerts') {
      void loadAlerts();
    }
  }, [activeTab, loadAlerts, loadPositions]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      void loadBots();
    }, 10000);

    return () => {
      window.clearInterval(interval);
    };
  }, [loadBots]);

  return (
    <div className="min-h-screen bg-slate-900">
      <div className="border-b border-slate-700 bg-slate-800">
        <div className="max-w-7xl mx-auto flex gap-8 px-6 overflow-x-auto">
          <button
            onClick={() => setActiveTab('overview')}
            className={`py-4 px-1 border-b-2 font-medium transition ${
              activeTab === 'overview'
                ? 'border-blue-500 text-white'
                : 'border-transparent text-slate-400 hover:text-white'
            }`}
          >
            <div className="flex items-center gap-2">
              <TrendingUp size={18} />
              Overview
            </div>
          </button>
          <button
            onClick={() => setActiveTab('manager')}
            className={`py-4 px-1 border-b-2 font-medium transition ${
              activeTab === 'manager'
                ? 'border-blue-500 text-white'
                : 'border-transparent text-slate-400 hover:text-white'
            }`}
          >
            <div className="flex items-center gap-2">
              <Zap size={18} />
              Bot Manager
            </div>
          </button>
          <button
            onClick={() => setActiveTab('positions')}
            className={`py-4 px-1 border-b-2 font-medium transition ${
              activeTab === 'positions'
                ? 'border-blue-500 text-white'
                : 'border-transparent text-slate-400 hover:text-white'
            }`}
          >
            <div className="flex items-center gap-2">
              <Activity size={18} />
              Positions
            </div>
          </button>
          <button
            onClick={() => setActiveTab('alerts')}
            className={`py-4 px-1 border-b-2 font-medium transition ${
              activeTab === 'alerts'
                ? 'border-blue-500 text-white'
                : 'border-transparent text-slate-400 hover:text-white'
            }`}
          >
            <div className="flex items-center gap-2">
              <AlertTriangle size={18} />
              Alerts
            </div>
          </button>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {activeTab !== 'manager' && (
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="text-3xl font-bold text-white">Bot Dashboard</h1>
              <p className="text-slate-400 mt-1">
                {lastUpdated ? `Last updated: ${lastUpdated.toLocaleTimeString()}` : 'Loading...'}
              </p>
            </div>
            <button
              onClick={() => void loadBots()}
              disabled={loading}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white px-4 py-2 rounded-lg transition"
            >
              <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
              Refresh
            </button>
          </div>
        )}

        {error && (
          <div className="bg-red-900 border border-red-700 text-red-100 px-4 py-3 rounded-lg mb-6 flex items-center gap-2">
            <AlertTriangle size={20} />
            {error}
          </div>
        )}

        {activeTab === 'overview' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {botList.map((bot) => (
                <button
                  type="button"
                  key={bot.instance_id}
                  onClick={() => setSelectedBot(bot.instance_id)}
                  className={`bg-slate-800 border rounded-lg p-4 text-left cursor-pointer transition ${
                    selectedBot === bot.instance_id
                      ? 'border-blue-500 ring-1 ring-blue-500'
                      : 'border-slate-700 hover:border-slate-600'
                  }`}
                >
                  <div className="flex items-start justify-between mb-2 gap-2">
                    <h3 className="font-semibold text-white truncate">{bot.instance_id}</h3>
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${getStatusBadge(bot.status)}`}
                    >
                      {bot.status}
                    </span>
                  </div>

                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between gap-3">
                      <span className="text-slate-400">P&amp;L</span>
                      <span className={bot.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}>
                        {formatCurrency(bot.total_pnl)}
                      </span>
                    </div>
                    <div className="flex justify-between gap-3">
                      <span className="text-slate-400">Positions</span>
                      <span className="text-white">{bot.open_positions} open</span>
                    </div>
                    <div className="flex justify-between gap-3">
                      <span className="text-slate-400">Trades</span>
                      <span className="text-white">{bot.total_trades}</span>
                    </div>
                    <div className="flex justify-between gap-3">
                      <span className="text-slate-400">Win Rate</span>
                      <span className="text-white">{formatWinRate(bot.win_rate)}</span>
                    </div>
                  </div>
                </button>
              ))}
            </div>

            {selectedBotStats && (
              <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
                <h2 className="text-xl font-bold text-white mb-6">
                  {selectedBotStats.instance_id} - Detailed Stats
                </h2>

                <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
                  <div>
                    <p className="text-sm text-slate-400 mb-1">Total P&amp;L</p>
                    <p
                      className={`text-2xl font-semibold ${
                        selectedBotStats.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}
                    >
                      {formatCurrency(selectedBotStats.total_pnl)}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-slate-400 mb-1">Realized P&amp;L</p>
                    <p className="text-2xl font-semibold text-white">
                      {formatCurrency(selectedBotStats.realized_pnl)}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-slate-400 mb-1">Unrealized P&amp;L</p>
                    <p className="text-2xl font-semibold text-white">
                      {formatCurrency(selectedBotStats.unrealized_pnl)}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-slate-400 mb-1">Open Positions</p>
                    <p className="text-2xl font-semibold text-white">
                      {selectedBotStats.open_positions}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-slate-400 mb-1">Total Trades</p>
                    <p className="text-2xl font-semibold text-white">
                      {selectedBotStats.total_trades}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-slate-400 mb-1">Win Rate</p>
                    <p className="text-2xl font-semibold text-white">
                      {formatWinRate(selectedBotStats.win_rate)}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'manager' && <BotManager />}

        {activeTab === 'positions' && (
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
            <h2 className="text-xl font-bold text-white mb-6">
              Open Positions - {selectedBot || 'No bot selected'}
            </h2>

            {botPositions.length === 0 ? (
              <p className="text-slate-400 text-center py-8">No open positions</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-700">
                      <th className="px-4 py-2 text-left text-slate-400">Market 1</th>
                      <th className="px-4 py-2 text-left text-slate-400">Market 2</th>
                      <th className="px-4 py-2 text-left text-slate-400">Entry Time</th>
                      <th className="px-4 py-2 text-left text-slate-400">Z-Score</th>
                      <th className="px-4 py-2 text-left text-slate-400">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {botPositions.map((position) => (
                      <tr
                        key={position.position_id}
                        className="border-b border-slate-700 hover:bg-slate-750"
                      >
                        <td className="px-4 py-2 text-white">{position.market_1}</td>
                        <td className="px-4 py-2 text-white">{position.market_2}</td>
                        <td className="px-4 py-2 text-slate-400">
                          {new Date(position.entry_time).toLocaleString()}
                        </td>
                        <td className="px-4 py-2 text-white">{position.z_score.toFixed(3)}</td>
                        <td className="px-4 py-2">
                          <span className="px-2 py-1 rounded text-xs font-medium bg-green-100 text-green-800">
                            {position.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {activeTab === 'alerts' && (
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
            <h2 className="text-xl font-bold text-white mb-6">
              Alerts - {selectedBot || 'No bot selected'}
            </h2>

            {botAlerts.length === 0 ? (
              <p className="text-slate-400 text-center py-8">No alerts</p>
            ) : (
              <div className="space-y-3">
                {botAlerts.map((alert, index) => (
                  <div
                    key={`${alert.timestamp}-${index}`}
                    className="bg-slate-700 rounded p-4 flex items-start gap-3"
                  >
                    <AlertTriangle size={20} className="text-yellow-400 shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <p className="text-white font-medium">{alert.title || 'Alert'}</p>
                      <p className="text-slate-300 text-sm mt-1">
                        {alert.message || alert.description || 'No description'}
                      </p>
                      <p className="text-slate-500 text-xs mt-2">
                        {new Date(alert.timestamp).toLocaleString()}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default BotDashboard;
