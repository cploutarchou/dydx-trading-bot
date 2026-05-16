import {
    Activity,
    AlertTriangle,
    Bot,
    Briefcase,
    Clock,
    RefreshCw,
    TrendingUp,
    Zap,
} from 'lucide-react';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import api from '../api';
import { useBotJobs } from '../api/hooks';
import type { BotJob } from '../api/types';
import BotManager from '../components/BotManager';
import { JobDetailsPanel } from '../components/JobDetailsPanel';
import { StatusBadge } from '../components/StatusBadge';

type TabType = 'overview' | 'manager' | 'positions' | 'alerts' | 'jobs';

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
  if (Array.isArray(value)) return value as T[];
  return [];
};

const asRecord = (value: unknown): Record<string, unknown> =>
  typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : {};

const getStatusBadge = (status: string): string => {
  const styles: Record<string, string> = {
    RUNNING: 'bg-green-900 text-green-300 border border-green-700',
    STOPPED: 'bg-slate-700 text-slate-300 border border-slate-600',
    FAILED: 'bg-red-900 text-red-300 border border-red-700',
    ERROR: 'bg-red-900 text-red-300 border border-red-700',
    PAUSED: 'bg-yellow-900 text-yellow-300 border border-yellow-700',
  };
  return styles[status] || 'bg-slate-700 text-slate-300 border border-slate-600';
};

function formatExecTime(ms: number | undefined): string {
  if (ms === undefined) return '—';
  if (ms < 1_000) return `${ms}ms`;
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const parts: string[] = [];
  if (h > 0) parts.push(`${h}h`);
  if (m > 0) parts.push(`${m}m`);
  if (sec > 0 || parts.length === 0) parts.push(`${sec}s`);
  return parts.join(' ');
}

function formatRelative(iso: string | undefined): string {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  if (Number.isNaN(diff)) return iso;
  const abs = Math.abs(diff);
  if (abs < 60_000) return 'just now';
  if (abs < 3_600_000) return `${Math.floor(abs / 60_000)}m ago`;
  if (abs < 86_400_000) return `${Math.floor(abs / 3_600_000)}h ago`;
  return `${Math.floor(abs / 86_400_000)}d ago`;
}

const getPositionStatusBadge = (status: string): string => {
  const styles: Record<string, string> = {
    OPEN: 'bg-blue-900 text-blue-300',
    CLOSED: 'bg-slate-700 text-slate-300',
    PARTIAL: 'bg-yellow-900 text-yellow-300',
  };
  return styles[status.toUpperCase()] || 'bg-slate-700 text-slate-300';
};

const formatCurrency = (value: number): string =>
  `${value >= 0 ? '' : '-'}$${Math.abs(value).toFixed(2)}`;

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
  const [selectedJob, setSelectedJob] = useState<BotJob | null>(null);

  const jobsQuery = useBotJobs(selectedBot ?? '', 7, !!selectedBot && activeTab === 'jobs');

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
            return await api.getBotSummary(bot.instance_id, 'stats', 20);
          } catch {
            return null;
          }
        })
      );

      const statsData: BotStatsData[] = instances.map((bot, index) => {
        const rawSummary = statsResponses[index]?.data;
        const summaryRecord = asRecord(rawSummary);
        const rawStats = asRecord(summaryRecord.stats);
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
      if (statsData.length > 0 && !selectedBot) setSelectedBot(statsData[0].instance_id);
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
      setBotPositions(
        asArray<PositionData>((rawData as { positions?: unknown })?.positions ?? rawData)
      );
    } catch (err) {
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
      setBotAlerts(asArray<AlertDataType>((rawData as { alerts?: unknown })?.alerts ?? rawData));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load alerts');
    }
  }, [selectedBot]);

  useEffect(() => {
    void loadBots();
  }, [loadBots]);
  useEffect(() => {
    if (activeTab === 'positions') void loadPositions();
    else if (activeTab === 'alerts') void loadAlerts();
  }, [activeTab, loadAlerts, loadPositions]);
  useEffect(() => {
    const interval = window.setInterval(() => void loadBots(), 10000);
    return () => window.clearInterval(interval);
  }, [loadBots]);

  const tabs: { id: TabType; label: string; icon: React.ReactNode }[] = [
    { id: 'overview', label: 'Overview', icon: <TrendingUp size={16} /> },
    { id: 'manager', label: 'Bot Manager', icon: <Zap size={16} /> },
    { id: 'positions', label: 'Positions', icon: <Activity size={16} /> },
    { id: 'alerts', label: 'Alerts', icon: <AlertTriangle size={16} /> },
    { id: 'jobs', label: 'Jobs', icon: <Briefcase size={16} /> },
  ];

  return (
    <>
      <div className="min-h-screen bg-slate-900">
        {/* Tab Bar */}
        <div className="border-b border-slate-700 bg-slate-800/80 backdrop-blur-sm sticky top-0 z-30">
          <div className="max-w-7xl mx-auto flex gap-1 px-4 overflow-x-auto">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 py-3.5 px-4 text-sm font-medium border-b-2 transition whitespace-nowrap ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-white'
                    : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-600'
                }`}
              >
                <span className={activeTab === tab.id ? 'text-blue-400' : ''}>{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
          {/* Page header */}
          {activeTab !== 'manager' && (
            <div className="flex items-center justify-between mb-8">
              <div>
                <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                  <div className="p-2 bg-blue-500/15 rounded-lg">
                    <Bot className="w-5 h-5 text-blue-400" />
                  </div>
                  Bot Dashboard
                </h1>
                <p className="text-slate-400 mt-1 ml-12 text-sm">
                  {lastUpdated
                    ? `Last updated ${lastUpdated.toLocaleTimeString()}`
                    : 'Loading bot data…'}
                </p>
              </div>
              <button
                onClick={() => void loadBots()}
                disabled={loading}
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:text-slate-400 text-white px-4 py-2 rounded-lg transition text-sm font-medium"
              >
                <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                Refresh
              </button>
            </div>
          )}

          {/* Error banner */}
          {error && (
            <div className="bg-red-900/50 border border-red-700 text-red-100 px-4 py-3 rounded-lg mb-6 flex items-center gap-2 text-sm">
              <AlertTriangle size={16} className="shrink-0" />
              {error}
            </div>
          )}

          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {botList.length === 0 && !loading ? (
                <div className="bg-slate-800 border border-slate-700 rounded-xl p-16 text-center animate-fade-in">
                  <div className="w-20 h-20 bg-slate-700/60 rounded-full flex items-center justify-center mx-auto mb-5">
                    <Bot className="w-10 h-10 text-slate-500" />
                  </div>
                  <h3 className="text-xl font-semibold text-white mb-2">No Bots Running</h3>
                  <p className="text-slate-400 text-sm max-w-sm mx-auto leading-relaxed">
                    No bot instances found. Open Bot Manager to create and start your first
                    automated trading bot.
                  </p>
                  <button
                    onClick={() => setActiveTab('manager')}
                    className="mt-6 inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition"
                  >
                    <Zap size={16} />
                    Open Bot Manager
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                  {botList.map((bot) => (
                    <button
                      type="button"
                      key={bot.instance_id}
                      onClick={() => setSelectedBot(bot.instance_id)}
                      className={`bg-slate-800 border rounded-xl p-4 text-left cursor-pointer transition-all ${
                        selectedBot === bot.instance_id
                          ? 'border-blue-500 ring-1 ring-blue-500/40 shadow-xl shadow-blue-500/10'
                          : 'border-slate-700 hover:border-slate-600 hover:bg-slate-700/50'
                      }`}
                    >
                      <div className="flex items-start justify-between mb-3 gap-2">
                        <div className="min-w-0">
                          <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-0.5">
                            Instance
                          </p>
                          <h3 className="font-semibold text-white truncate text-sm">
                            {bot.instance_id.substring(0, 16)}
                            {bot.instance_id.length > 16 ? '…' : ''}
                          </h3>
                        </div>
                        <span
                          className={`flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold uppercase whitespace-nowrap ${getStatusBadge(bot.status)}`}
                        >
                          {bot.status === 'RUNNING' && (
                            <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
                          )}
                          {bot.status}
                        </span>
                      </div>
                      <div className="space-y-1.5 text-xs">
                        <div className="flex justify-between items-center">
                          <span className="text-slate-400">P&amp;L</span>
                          <span
                            className={`font-semibold ${bot.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}
                          >
                            {formatCurrency(bot.total_pnl)}
                          </span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-slate-400">Open Positions</span>
                          <span className="text-white font-medium">{bot.open_positions}</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-slate-400">Total Trades</span>
                          <span className="text-white font-medium">{bot.total_trades}</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-slate-400">Win Rate</span>
                          <span className="text-white font-medium">
                            {formatWinRate(bot.win_rate)}
                          </span>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}

              {selectedBotStats && (
                <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 animate-fade-slide-up">
                  <div className="flex items-center gap-3 mb-6">
                    <div className="p-2 bg-blue-500/15 rounded-lg">
                      <Bot className="w-5 h-5 text-blue-400" />
                    </div>
                    <div>
                      <h2 className="text-lg font-bold text-white">
                        {selectedBotStats.instance_id}
                      </h2>
                      <p className="text-xs text-slate-400">Detailed performance statistics</p>
                    </div>
                    <div className="ml-auto">
                      <span
                        className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold ${getStatusBadge(selectedBotStats.status)}`}
                      >
                        {selectedBotStats.status === 'RUNNING' && (
                          <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
                        )}
                        {selectedBotStats.status}
                      </span>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                    {[
                      {
                        label: 'Total P&L',
                        value: formatCurrency(selectedBotStats.total_pnl),
                        colored: true,
                        positive: selectedBotStats.total_pnl >= 0,
                      },
                      {
                        label: 'Realized P&L',
                        value: formatCurrency(selectedBotStats.realized_pnl),
                        colored: false,
                        positive: false,
                      },
                      {
                        label: 'Unrealized P&L',
                        value: formatCurrency(selectedBotStats.unrealized_pnl),
                        colored: false,
                        positive: false,
                      },
                      {
                        label: 'Open Positions',
                        value: String(selectedBotStats.open_positions),
                        colored: false,
                        positive: false,
                      },
                      {
                        label: 'Total Trades',
                        value: String(selectedBotStats.total_trades),
                        colored: false,
                        positive: false,
                      },
                      {
                        label: 'Win Rate',
                        value: formatWinRate(selectedBotStats.win_rate),
                        colored: false,
                        positive: false,
                      },
                    ].map((stat) => (
                      <div key={stat.label} className="bg-slate-900/50 rounded-lg p-3 text-center">
                        <p className="text-xs text-slate-400 mb-1">{stat.label}</p>
                        <p
                          className={`text-lg font-bold ${stat.colored ? (stat.positive ? 'text-green-400' : 'text-red-400') : 'text-white'}`}
                        >
                          {stat.value}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'manager' && <BotManager />}

          {activeTab === 'jobs' && (
            <div className="bg-slate-800 border border-slate-700 rounded-xl p-6">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-2 bg-indigo-500/15 rounded-lg">
                  <Briefcase className="w-5 h-5 text-indigo-400" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-white">Job History</h2>
                  <p className="text-xs text-slate-400">
                    {selectedBot ? `Bot: ${selectedBot}` : 'No bot selected'} · last 7 days
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => void jobsQuery.refetch()}
                  disabled={jobsQuery.isFetching}
                  className="ml-auto flex items-center gap-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg transition text-xs font-medium"
                >
                  <RefreshCw size={13} className={jobsQuery.isFetching ? 'animate-spin' : ''} />
                  Refresh
                </button>
              </div>

              {jobsQuery.isLoading ? (
                <div className="flex justify-center py-16">
                  <RefreshCw size={24} className="animate-spin text-slate-500" />
                </div>
              ) : jobsQuery.isError ? (
                <div className="bg-red-900/40 border border-red-700 text-red-200 p-4 rounded-lg text-sm flex items-center gap-2">
                  <AlertTriangle size={16} />
                  Failed to load jobs:{' '}
                  {jobsQuery.error instanceof Error ? jobsQuery.error.message : 'Unknown error'}
                </div>
              ) : !jobsQuery.data || jobsQuery.data.length === 0 ? (
                <div className="text-center py-16">
                  <div className="w-14 h-14 bg-slate-700/60 rounded-full flex items-center justify-center mx-auto mb-4">
                    <Briefcase className="w-7 h-7 text-slate-500" />
                  </div>
                  <p className="text-slate-400 text-sm">No jobs found</p>
                  <p className="text-slate-500 text-xs mt-1">
                    Jobs will appear here when the bot executes tasks.
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-700">
                        {['Type', 'Status', 'Progress', 'Started', 'Completed', 'Duration', ''].map(
                          (h) => (
                            <th
                              key={h}
                              className="px-3 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider whitespace-nowrap"
                            >
                              {h}
                            </th>
                          )
                        )}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700/60">
                      {jobsQuery.data.map((job) => {
                        const pct = Math.min(100, Math.max(0, job.progress_pct ?? 0));
                        const isRunning = job.status === 'running';
                        return (
                          <tr
                            key={job.job_id}
                            className="hover:bg-slate-700/30 transition-colors cursor-pointer"
                            onClick={() => setSelectedJob(job)}
                          >
                            <td className="px-3 py-3 text-white font-mono text-xs whitespace-nowrap">
                              {job.job_type}
                            </td>
                            <td className="px-3 py-3">
                              <StatusBadge status={job.status} />
                            </td>
                            <td className="px-3 py-3 min-w-25">
                              {isRunning ? (
                                <div className="flex items-center gap-2">
                                  <div className="flex-1 bg-slate-700 rounded-full h-1.5 overflow-hidden min-w-15">
                                    <div
                                      className="h-full bg-blue-500 rounded-full transition-all"
                                      style={{ width: `${pct}%` }}
                                    />
                                  </div>
                                  <span className="text-xs text-slate-300 shrink-0">
                                    {pct.toFixed(0)}%
                                  </span>
                                </div>
                              ) : (
                                <span className="text-xs text-slate-400">{pct.toFixed(0)}%</span>
                              )}
                            </td>
                            <td className="px-3 py-3 text-slate-400 text-xs whitespace-nowrap">
                              <span title={job.started_at}>
                                <Clock size={11} className="inline mr-1 opacity-60" />
                                {formatRelative(job.started_at)}
                              </span>
                            </td>
                            <td className="px-3 py-3 text-slate-400 text-xs whitespace-nowrap">
                              {job.completed_at ? (
                                <span title={job.completed_at}>
                                  {formatRelative(job.completed_at)}
                                </span>
                              ) : (
                                '—'
                              )}
                            </td>
                            <td className="px-3 py-3 text-slate-300 text-xs whitespace-nowrap font-mono">
                              {formatExecTime(job.execution_time_ms)}
                            </td>
                            <td className="px-3 py-3 text-right">
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setSelectedJob(job);
                                }}
                                className="text-[10px] text-blue-400 hover:text-blue-300 transition"
                              >
                                Details
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {activeTab === 'positions' && (
            <div className="bg-slate-800 border border-slate-700 rounded-xl p-6">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-2 bg-cyan-500/15 rounded-lg">
                  <Activity className="w-5 h-5 text-cyan-400" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-white">Open Positions</h2>
                  <p className="text-xs text-slate-400">
                    {selectedBot ? `Bot: ${selectedBot}` : 'No bot selected'}
                  </p>
                </div>
              </div>
              {botPositions.length === 0 ? (
                <div className="text-center py-16">
                  <div className="w-14 h-14 bg-slate-700/60 rounded-full flex items-center justify-center mx-auto mb-4">
                    <Activity className="w-7 h-7 text-slate-500" />
                  </div>
                  <p className="text-slate-400 text-sm">No open positions</p>
                  <p className="text-slate-500 text-xs mt-1">
                    Active positions will appear here when trades are live.
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-700">
                        {['Market 1', 'Market 2', 'Entry Time', 'Z-Score', 'Status'].map((h) => (
                          <th
                            key={h}
                            className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider"
                          >
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700/60">
                      {botPositions.map((position) => (
                        <tr
                          key={position.position_id}
                          className="hover:bg-slate-700/30 transition-colors"
                        >
                          <td className="px-4 py-3 text-white font-mono text-xs">
                            {position.market_1}
                          </td>
                          <td className="px-4 py-3 text-white font-mono text-xs">
                            {position.market_2}
                          </td>
                          <td className="px-4 py-3 text-slate-400 text-xs">
                            {new Date(position.entry_time).toLocaleString()}
                          </td>
                          <td className="px-4 py-3 text-white font-mono text-xs">
                            {position.z_score.toFixed(3)}
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${getPositionStatusBadge(position.status)}`}
                            >
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
            <div className="bg-slate-800 border border-slate-700 rounded-xl p-6">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-2 bg-yellow-500/15 rounded-lg">
                  <AlertTriangle className="w-5 h-5 text-yellow-400" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-white">Alerts</h2>
                  <p className="text-xs text-slate-400">
                    {selectedBot ? `Bot: ${selectedBot}` : 'No bot selected'}
                  </p>
                </div>
                {botAlerts.length > 0 && (
                  <span className="ml-auto text-xs bg-yellow-900/50 border border-yellow-700 text-yellow-300 px-2 py-0.5 rounded-full">
                    {botAlerts.length} alert{botAlerts.length !== 1 ? 's' : ''}
                  </span>
                )}
              </div>
              {botAlerts.length === 0 ? (
                <div className="text-center py-16">
                  <div className="w-14 h-14 bg-slate-700/60 rounded-full flex items-center justify-center mx-auto mb-4">
                    <AlertTriangle className="w-7 h-7 text-slate-500" />
                  </div>
                  <p className="text-slate-400 text-sm">No alerts</p>
                  <p className="text-slate-500 text-xs mt-1">
                    System alerts will appear here when they occur.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {botAlerts.map((alert, index) => (
                    <div
                      key={`${alert.timestamp}-${index}`}
                      className="bg-slate-700/50 border border-slate-600 rounded-lg p-4 flex items-start gap-3"
                    >
                      <div className="p-1.5 bg-yellow-900/50 rounded-lg shrink-0 mt-0.5">
                        <AlertTriangle size={14} className="text-yellow-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-white text-sm font-semibold">{alert.title || 'Alert'}</p>
                        <p className="text-slate-300 text-sm mt-1 leading-relaxed">
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

      {selectedJob && <JobDetailsPanel job={selectedJob} onClose={() => setSelectedJob(null)} />}
    </>
  );
};

export default BotDashboard;
