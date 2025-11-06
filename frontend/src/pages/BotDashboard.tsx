import React, { useState, useEffect, useCallback } from 'react';/**/**

import { RefreshCw, TrendingUp, Activity, AlertTriangle, Zap } from 'lucide-react';

import api from '../api'; * Bot Dashboard Page - Real-time Bot Monitoring & Management * Bot Dashboard Page - Real-time Bot Monitoring & Management

import BotManager from '../components/BotManager';

 */ * 

interface BotStatsData {

  instance_id: string; * Displays:

  status: string;

  total_pnl: number;import React, { useState, useEffect, useCallback } from 'react'; * - Active bot instances with status

  realized_pnl: number;

  unrealized_pnl: number;import { RefreshCw, TrendingUp, Activity, AlertTriangle, Zap } from 'lucide-react'; * - Open positions and trades

  total_positions: number;

  open_positions: number;import api from '../api'; * - Real-time P&L and statistics

  total_trades: number;

  win_rate: number;import BotManager from '../components/BotManager'; * - Bot alerts and execution history

  last_update: string;

} * - WebSocket real-time updates



interface PositionData {interface BotStats { */

  position_id: string;

  market_1: string;  instance_id: string;

  market_2: string;

  entry_time: string;  status: string;import React, { useState, useEffect, useCallback } from 'react';

  z_score: number;

  status: string;  total_pnl: number;import { RefreshCw, TrendingUp, Activity, AlertTriangle, Zap } from 'lucide-react';

  entry_price_1: number;

  entry_price_2: number;  realized_pnl: number;import api from '../api';

}

  unrealized_pnl: number;import BotManager from '../components/BotManager';

interface AlertDataType {

  timestamp: string;  total_positions: number;

  title?: string;

  message?: string;  open_positions: number;interface BotStats {

  description?: string;

}  total_trades: number;  instance_id: string;



type TabType = 'overview' | 'manager' | 'positions' | 'alerts';  win_rate: number;  status: string;



const BotDashboard: React.FC = () => {  last_update: string;  total_pnl: number;

  const [activeTab, setActiveTab] = useState<TabType>('overview');

  const [botList, setBotList] = useState<BotStatsData[]>([]);}  realized_pnl: number;

  const [selectedBot, setSelectedBot] = useState<string | null>(null);

  const [botPositions, setBotPositions] = useState<PositionData[]>([]);  unrealized_pnl: number;

  const [botAlerts, setBotAlerts] = useState<AlertDataType[]>([]);

  const [loading, setLoading] = useState(false);interface Position {  total_positions: number;

  const [error, setError] = useState<string | null>(null);

  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);  position_id: string;  open_positions: number;



  const loadBots = useCallback(async () => {  market_1: string;  total_trades: number;

    try {

      setLoading(true);  market_2: string;  win_rate: number;

      const response = await api.listBotInstances(0, 100);

      if (response.success && response.data) {  entry_time: string;  last_update: string;

        const botData = response.data.bots || response.data;

        const instances = Array.isArray(botData) ? botData : [];  z_score: number;}

        

        const statsPromises = instances.map((bot: { instance_id: string }) =>  status: string;

          api.getBotStats(bot.instance_id).catch(() => null)

        );  entry_price_1: number;interface Position {

        const statsResponses = await Promise.all(statsPromises);

          entry_price_2: number;  position_id: string;

        const statsData: BotStatsData[] = instances.map((bot: { instance_id: string; status: string }, idx: number) => {

          const stats = statsResponses[idx]?.data || {};}  market_1: string;

          return {

            instance_id: bot.instance_id,  market_2: string;

            status: bot.status,

            total_pnl: stats.total_pnl || 0,interface AlertData {  entry_time: string;

            realized_pnl: stats.realized_pnl || 0,

            unrealized_pnl: stats.unrealized_pnl || 0,  timestamp: string;  z_score: number;

            total_positions: stats.total_positions || 0,

            open_positions: stats.open_positions || 0,  title?: string;  status: string;

            total_trades: stats.total_trades || 0,

            win_rate: stats.win_rate || 0,  message?: string;  entry_price_1: number;

            last_update: new Date().toISOString(),

          };  description?: string;  entry_price_2: number;

        });

        }}

        setBotList(statsData);

        setLastUpdated(new Date());

        

        if (statsData.length > 0 && !selectedBot) {const BotDashboard: React.FC = () => {interface Alert {

          setSelectedBot(statsData[0].instance_id);

        }  const [activeTab, setActiveTab] = useState<'overview' | 'manager' | 'positions' | 'alerts'>('overview');  timestamp: string;

        

        setError(null);  const [botList, setBotList] = useState<BotStats[]>([]);  title?: string;

      }

    } catch (err) {  const [selectedBot, setSelectedBot] = useState<string | null>(null);  message?: string;

      console.error('Failed to load bots:', err);

      setError(err instanceof Error ? err.message : 'Failed to load bots');  const [botPositions, setBotPositions] = useState<Position[]>([]);  description?: string;

    } finally {

      setLoading(false);  const [botAlerts, setBotAlerts] = useState<AlertData[]>([]);}

    }

  }, [selectedBot]);  const [loading, setLoading] = useState(false);



  const loadPositions = useCallback(async () => {  const [error, setError] = useState<string | null>(null);const BotDashboard: React.FC = () => {

    if (!selectedBot) return;

      const [lastUpdated, setLastUpdated] = useState<Date | null>(null);  const [activeTab, setActiveTab] = useState<'overview' | 'manager' | 'positions' | 'alerts'>('overview');

    try {

      const response = await api.getBotCurrentPositions(selectedBot);  const [botList, setBotList] = useState<BotStats[]>([]);

      if (response.success && response.data) {

        const positions = response.data.positions || response.data;  // Load bots list  const [selectedBot, setSelectedBot] = useState<string | null>(null);

        setBotPositions(Array.isArray(positions) ? positions : []);

      }  const loadBots = useCallback(async () => {  const [botPositions, setBotPositions] = useState<Position[]>([]);

    } catch (err) {

      console.error('Failed to load positions:', err);    try {  const [botAlerts, setBotAlerts] = useState<Alert[]>([]);

    }

  }, [selectedBot]);      setLoading(true);  const [loading, setLoading] = useState(false);



  const loadAlerts = useCallback(async () => {      const response = await api.listBotInstances(0, 100);  const [error, setError] = useState<string | null>(null);

    if (!selectedBot) return;

          if (response.success && response.data) {  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

    try {

      const response = await api.getBotAlerts(selectedBot, 0, 50);        const botData = response.data.bots || response.data;

      if (response.success && response.data) {

        const alerts = response.data.alerts || response.data;        const instances = Array.isArray(botData) ? botData : [];  // Load bots list

        setBotAlerts(Array.isArray(alerts) ? alerts : []);

      }          const loadBots = useCallback(async () => {

    } catch (err) {

      console.error('Failed to load alerts:', err);        // Load stats for each bot    try {

    }

  }, [selectedBot]);        const statsPromises = instances.map((bot: { instance_id: string }) =>      setLoading(true);



  useEffect(() => {          api.getBotStats(bot.instance_id).catch(() => null)      const response = await api.listBotInstances(0, 100);

    loadBots();

  }, [loadBots]);        );      const [schemaResponse, settingsResponse] = await Promise.all([



  useEffect(() => {        const statsResponses = await Promise.all(statsPromises);        apiClient.getSettingsSchema(),

    if (activeTab === 'positions') {

      loadPositions();                apiClient.getSettings(),

    } else if (activeTab === 'alerts') {

      loadAlerts();        const statsData: BotStats[] = instances.map((bot: { instance_id: string; status: string }, idx: number) => {      ]);

    }

  }, [activeTab, selectedBot, loadPositions, loadAlerts]);          const stats = statsResponses[idx]?.data || {};



  useEffect(() => {          return {      const schemaData = schemaResponse.data as SettingsSchema;

    const interval = setInterval(loadBots, 10000);

    return () => clearInterval(interval);            instance_id: bot.instance_id,      const settingsData = settingsResponse.data as SavedSettings;

  }, [loadBots]);

            status: bot.status,

  const getStatusBadge = (status: string) => {

    const styles: Record<string, string> = {            total_pnl: stats.total_pnl || 0,      setSchema(schemaData);

      RUNNING: 'bg-green-100 text-green-800',

      STOPPED: 'bg-yellow-100 text-yellow-800',            realized_pnl: stats.realized_pnl || 0,      setSettings(settingsData);

      FAILED: 'bg-red-100 text-red-800',

      ERROR: 'bg-red-100 text-red-800',            unrealized_pnl: stats.unrealized_pnl || 0,

    };

    return styles[status] || 'bg-gray-100 text-gray-800';            total_positions: stats.total_positions || 0,      // Build formValues from saved settings

  };

            open_positions: stats.open_positions || 0,      const formVals: Record<string, Record<string, unknown>> = {};

  return (

    <div className="min-h-screen bg-slate-900">            total_trades: stats.total_trades || 0,      settingsData.sections.forEach((section) => {

      <div className="border-b border-slate-700 bg-slate-800">

        <div className="max-w-7xl mx-auto flex gap-8 px-6">            win_rate: stats.win_rate || 0,        formVals[section.section] = {};

          <button

            onClick={() => setActiveTab('overview')}            last_update: new Date().toISOString(),        section.settings.forEach((setting) => {

            className={`py-4 px-1 border-b-2 font-medium transition ${

              activeTab === 'overview'          };          // Parse JSON values

                ? 'border-blue-500 text-white'

                : 'border-transparent text-slate-400 hover:text-white'        });          let value = setting.value;

            }`}

          >                  if (typeof value === 'string') {

            <div className="flex items-center gap-2">

              <TrendingUp size={18} />        setBotList(statsData);            try {

              Overview

            </div>        setLastUpdated(new Date());              value = JSON.parse(value);

          </button>

          <button                    } catch {

            onClick={() => setActiveTab('manager')}

            className={`py-4 px-1 border-b-2 font-medium transition ${        if (statsData.length > 0 && !selectedBot) {              // Not JSON, keep as string

              activeTab === 'manager'

                ? 'border-blue-500 text-white'          setSelectedBot(statsData[0].instance_id);            }

                : 'border-transparent text-slate-400 hover:text-white'

            }`}        }          }

          >

            <div className="flex items-center gap-2">                  formVals[section.section][setting.key] = value !== undefined ? value : setting.default_value;

              <Zap size={18} />

              Bot Manager        setError(null);          const stats = statsResponses[idx]?.data || {};

            </div>

          </button>      }          return {

          <button

            onClick={() => setActiveTab('positions')}    } catch (err) {            instance_id: bot.instance_id,

            className={`py-4 px-1 border-b-2 font-medium transition ${

              activeTab === 'positions'      console.error('Failed to load bots:', err);            status: bot.status,

                ? 'border-blue-500 text-white'

                : 'border-transparent text-slate-400 hover:text-white'      setError(err instanceof Error ? err.message : 'Failed to load bots');            total_pnl: stats.total_pnl || 0,

            }`}

          >    } finally {            realized_pnl: stats.realized_pnl || 0,

            <div className="flex items-center gap-2">

              <Activity size={18} />      setLoading(false);            unrealized_pnl: stats.unrealized_pnl || 0,

              Positions

            </div>    }            total_positions: stats.total_positions || 0,

          </button>

          <button  }, [selectedBot]);            open_positions: stats.open_positions || 0,

            onClick={() => setActiveTab('alerts')}

            className={`py-4 px-1 border-b-2 font-medium transition ${            total_trades: stats.total_trades || 0,

              activeTab === 'alerts'

                ? 'border-blue-500 text-white'  // Load positions for selected bot            win_rate: stats.win_rate || 0,

                : 'border-transparent text-slate-400 hover:text-white'

            }`}  const loadPositions = useCallback(async () => {            last_update: new Date().toISOString(),

          >

            <div className="flex items-center gap-2">    if (!selectedBot) return;          };

              <AlertTriangle size={18} />

              Alerts            });

            </div>

          </button>    try {        

        </div>

      </div>      const response = await api.getBotCurrentPositions(selectedBot);        setBotList(statsData);



      <div className="max-w-7xl mx-auto px-6 py-8">      if (response.success && response.data) {        setLastUpdated(new Date());

        {activeTab !== 'manager' && (

          <div className="flex items-center justify-between mb-8">        const positions = response.data.positions || response.data;        

            <div>

              <h1 className="text-3xl font-bold text-white">Bot Dashboard</h1>        setBotPositions(Array.isArray(positions) ? positions : []);        // Auto-select first bot

              <p className="text-slate-400 mt-1">

                {lastUpdated ? `Last updated: ${lastUpdated.toLocaleTimeString()}` : 'Loading...'}      }        if (statsData.length > 0 && !selectedBot) {

              </p>

            </div>    } catch (err) {          setSelectedBot(statsData[0].instance_id);

            <button

              onClick={loadBots}      console.error('Failed to load positions:', err);        }

              disabled={loading}

              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white px-4 py-2 rounded-lg transition"    }        

            >

              <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />  }, [selectedBot]);        setError(null);

              Refresh

            </button>      }

          </div>

        )}  // Load alerts for selected bot    } catch (err) {



        {error && (  const loadAlerts = useCallback(async () => {      console.error('Failed to load bots:', err);

          <div className="bg-red-900 border border-red-700 text-red-100 px-4 py-3 rounded-lg mb-6 flex items-center gap-2">

            <AlertTriangle size={20} />    if (!selectedBot) return;      setError(err instanceof Error ? err.message : 'Failed to load bots');

            {error}

          </div>        } finally {

        )}

    try {      setLoading(false);

        {activeTab === 'overview' && (

          <div className="space-y-6">      const response = await api.getBotAlerts(selectedBot, 0, 50);    }

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">

              {botList.map((bot) => (      if (response.success && response.data) {  }, [selectedBot]);

                <div

                  key={bot.instance_id}        const alerts = response.data.alerts || response.data;

                  onClick={() => setSelectedBot(bot.instance_id)}

                  className={`bg-slate-800 border rounded-lg p-4 cursor-pointer transition ${        setBotAlerts(Array.isArray(alerts) ? alerts : []);  // Load positions for selected bot

                    selectedBot === bot.instance_id

                      ? 'border-blue-500 ring-1 ring-blue-500'      }  const loadPositions = useCallback(async () => {

                      : 'border-slate-700 hover:border-slate-600'

                  }`}    } catch (err) {    if (!selectedBot) return;

                >

                  <div className="flex items-start justify-between mb-2">      console.error('Failed to load alerts:', err);    

                    <h3 className="font-semibold text-white truncate">{bot.instance_id}</h3>

                    <span className={`px-2 py-1 rounded text-xs font-medium ${getStatusBadge(bot.status)}`}>    }    try {

                      {bot.status}

                    </span>  }, [selectedBot]);      const response = await api.getBotCurrentPositions(selectedBot);

                  </div>

                        if (response.success && response.data) {

                  <div className="space-y-1 text-sm">

                    <div className="flex justify-between">  // Initial load        const positions = response.data.positions || response.data;

                      <span className="text-slate-400">P&L</span>

                      <span className={bot.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}>  useEffect(() => {        setBotPositions(Array.isArray(positions) ? positions : []);

                        ${bot.total_pnl.toFixed(2)}

                      </span>    loadBots();      }

                    </div>

                    <div className="flex justify-between">  }, [loadBots]);    } catch (err) {

                      <span className="text-slate-400">Positions</span>

                      <span className="text-white">{bot.open_positions} open</span>      console.error('Failed to load positions:', err);

                    </div>

                    <div className="flex justify-between">  // Load data when tab or selected bot changes    }

                      <span className="text-slate-400">Trades</span>

                      <span className="text-white">{bot.total_trades}</span>  useEffect(() => {  }, [selectedBot]);

                    </div>

                    <div className="flex justify-between">    if (activeTab === 'positions') {

                      <span className="text-slate-400">Win Rate</span>

                      <span className="text-white">{(bot.win_rate * 100).toFixed(1)}%</span>      loadPositions();  // Load alerts for selected bot

                    </div>

                  </div>    } else if (activeTab === 'alerts') {  const loadAlerts = useCallback(async () => {

                </div>

              ))}      loadAlerts();    if (!selectedBot) return;

            </div>

          </div>    }    

        )}

  }, [activeTab, selectedBot, loadPositions, loadAlerts]);    try {

        {activeTab === 'manager' && <BotManager />}

      const response = await api.getBotAlerts(selectedBot, 0, 50);

        {activeTab === 'positions' && (

          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">  // Auto-refresh stats every 10 seconds      if (response.success && response.data) {

            <h2 className="text-xl font-bold text-white mb-6">

              Open Positions - {selectedBot || 'No bot selected'}  useEffect(() => {        const alerts = response.data.alerts || response.data;

            </h2>

                const interval = setInterval(loadBots, 10000);        setBotAlerts(Array.isArray(alerts) ? alerts : []);

            {botPositions.length === 0 ? (

              <p className="text-slate-400 text-center py-8">No open positions</p>    return () => clearInterval(interval);      }

            ) : (

              <div className="overflow-x-auto">  }, [loadBots]);    } catch (err) {

                <table className="w-full text-sm">

                  <thead>      console.error('Failed to load alerts:', err);

                    <tr className="border-b border-slate-700">

                      <th className="px-4 py-2 text-left text-slate-400">Market 1</th>  const getStatusBadge = (status: string) => {    }

                      <th className="px-4 py-2 text-left text-slate-400">Market 2</th>

                      <th className="px-4 py-2 text-left text-slate-400">Entry Time</th>    const styles: Record<string, string> = {  }, [selectedBot]);

                      <th className="px-4 py-2 text-left text-slate-400">Z-Score</th>

                      <th className="px-4 py-2 text-left text-slate-400">Status</th>      RUNNING: 'bg-green-100 text-green-800',

                    </tr>

                  </thead>      STOPPED: 'bg-yellow-100 text-yellow-800',  // Initial load

                  <tbody>

                    {botPositions.map((pos) => (      FAILED: 'bg-red-100 text-red-800',  useEffect(() => {

                      <tr key={pos.position_id} className="border-b border-slate-700 hover:bg-slate-750">

                        <td className="px-4 py-2 text-white">{pos.market_1}</td>      ERROR: 'bg-red-100 text-red-800',    loadBots();

                        <td className="px-4 py-2 text-white">{pos.market_2}</td>

                        <td className="px-4 py-2 text-slate-400">    };  }, [loadBots]);

                          {new Date(pos.entry_time).toLocaleString()}

                        </td>    return styles[status] || 'bg-gray-100 text-gray-800';

                        <td className="px-4 py-2 text-white">{pos.z_score.toFixed(3)}</td>

                        <td className="px-4 py-2">  };  // Load data when tab or selected bot changes

                          <span className="px-2 py-1 rounded text-xs font-medium bg-green-100 text-green-800">

                            {pos.status}  useEffect(() => {

                          </span>

                        </td>  return (    if (activeTab === 'positions') {

                      </tr>

                    ))}    <div className="min-h-screen bg-slate-900">      loadPositions();

                  </tbody>

                </table>      {/* Navigation Tabs */}    } else if (activeTab === 'alerts') {

              </div>

            )}      <div className="border-b border-slate-700 bg-slate-800">      loadAlerts();

          </div>

        )}        <div className="max-w-7xl mx-auto flex gap-8 px-6">    }



        {activeTab === 'alerts' && (          <button  }, [activeTab, selectedBot, loadPositions, loadAlerts]);

          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">

            <h2 className="text-xl font-bold text-white mb-6">            onClick={() => setActiveTab('overview')}

              Alerts - {selectedBot || 'No bot selected'}

            </h2>            className={`py-4 px-1 border-b-2 font-medium transition ${  // Auto-refresh stats every 10 seconds

            

            {botAlerts.length === 0 ? (              activeTab === 'overview'  useEffect(() => {

              <p className="text-slate-400 text-center py-8">No alerts</p>

            ) : (                ? 'border-blue-500 text-white'    const interval = setInterval(loadBots, 10000);

              <div className="space-y-3">

                {botAlerts.map((alert, idx) => (                : 'border-transparent text-slate-400 hover:text-white'    return () => clearInterval(interval);

                  <div key={idx} className="bg-slate-700 rounded p-4 flex items-start gap-3">

                    <AlertTriangle size={20} className="text-yellow-400 flex-shrink-0 mt-0.5" />            }`}  }, [loadBots]);

                    <div className="flex-1">

                      <p className="text-white font-medium">{alert.title || 'Alert'}</p>          >

                      <p className="text-slate-300 text-sm mt-1">{alert.message || alert.description}</p>

                      <p className="text-slate-500 text-xs mt-2">            <div className="flex items-center gap-2">  const getStatusBadge = (status: string) => {

                        {new Date(alert.timestamp).toLocaleString()}

                      </p>              <TrendingUp size={18} />    const styles: Record<string, string> = {

                    </div>

                  </div>              Overview      RUNNING: 'bg-green-100 text-green-800',

                ))}

              </div>            </div>      STOPPED: 'bg-yellow-100 text-yellow-800',

            )}

          </div>          </button>      FAILED: 'bg-red-100 text-red-800',

        )}

      </div>          <button      ERROR: 'bg-red-100 text-red-800',

    </div>

  );            onClick={() => setActiveTab('manager')}    };

};

            className={`py-4 px-1 border-b-2 font-medium transition ${    return styles[status] || 'bg-gray-100 text-gray-800';

export default BotDashboard;

              activeTab === 'manager'  };

                ? 'border-blue-500 text-white'

                : 'border-transparent text-slate-400 hover:text-white'  return (

            }`}    <div className="min-h-screen bg-slate-900">

          >      {/* Navigation Tabs */}

            <div className="flex items-center gap-2">      <div className="border-b border-slate-700 bg-slate-800">

              <Zap size={18} />        <div className="max-w-7xl mx-auto flex gap-8 px-6">

              Bot Manager          <button

            </div>            onClick={() => setActiveTab('overview')}

          </button>            className={`py-4 px-1 border-b-2 font-medium transition ${

          <button              activeTab === 'overview'

            onClick={() => setActiveTab('positions')}                ? 'border-blue-500 text-white'

            className={`py-4 px-1 border-b-2 font-medium transition ${                : 'border-transparent text-slate-400 hover:text-white'

              activeTab === 'positions'            }`}

                ? 'border-blue-500 text-white'          >

                : 'border-transparent text-slate-400 hover:text-white'            <div className="flex items-center gap-2">

            }`}              <TrendingUp size={18} />

          >              Overview

            <div className="flex items-center gap-2">            </div>

              <Activity size={18} />          </button>

              Positions          <button

            </div>            onClick={() => setActiveTab('manager')}

          </button>            className={`py-4 px-1 border-b-2 font-medium transition ${

          <button              activeTab === 'manager'

            onClick={() => setActiveTab('alerts')}                ? 'border-blue-500 text-white'

            className={`py-4 px-1 border-b-2 font-medium transition ${                : 'border-transparent text-slate-400 hover:text-white'

              activeTab === 'alerts'            }`}

                ? 'border-blue-500 text-white'          >

                : 'border-transparent text-slate-400 hover:text-white'            <div className="flex items-center gap-2">

            }`}              <Zap size={18} />

          >              Bot Manager

            <div className="flex items-center gap-2">            </div>

              <AlertTriangle size={18} />          </button>

              Alerts          <button

            </div>            onClick={() => setActiveTab('positions')}

          </button>            className={`py-4 px-1 border-b-2 font-medium transition ${

        </div>              activeTab === 'positions'

      </div>                ? 'border-blue-500 text-white'

                : 'border-transparent text-slate-400 hover:text-white'

      {/* Content Area */}            }`}

      <div className="max-w-7xl mx-auto px-6 py-8">          >

        {/* Header */}            <div className="flex items-center gap-2">

        {activeTab !== 'manager' && (              <Activity size={18} />

          <div className="flex items-center justify-between mb-8">              Positions

            <div>            </div>

              <h1 className="text-3xl font-bold text-white">Bot Dashboard</h1>          </button>

              <p className="text-slate-400 mt-1">          <button

                {lastUpdated ? `Last updated: ${lastUpdated.toLocaleTimeString()}` : 'Loading...'}            onClick={() => setActiveTab('alerts')}

              </p>            className={`py-4 px-1 border-b-2 font-medium transition ${

            </div>              activeTab === 'alerts'

            <button                ? 'border-blue-500 text-white'

              onClick={loadBots}                : 'border-transparent text-slate-400 hover:text-white'

              disabled={loading}            }`}

              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white px-4 py-2 rounded-lg transition"          >

            >            <div className="flex items-center gap-2">

              <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />              <AlertTriangle size={18} />

              Refresh              Alerts

            </button>            </div>

          </div>          </button>

        )}        </div>

      </div>

        {/* Error Message */}

        {error && (      {/* Content Area */}

          <div className="bg-red-900 border border-red-700 text-red-100 px-4 py-3 rounded-lg mb-6 flex items-center gap-2">      <div className="max-w-7xl mx-auto px-6 py-8">

            <AlertTriangle size={20} />        {/* Header */}

            {error}        {activeTab !== 'manager' && (

          </div>          <div className="flex items-center justify-between mb-8">

        )}            <div>

              <h1 className="text-3xl font-bold text-white">Bot Dashboard</h1>

        {/* Tab Content */}              <p className="text-slate-400 mt-1">

        {activeTab === 'overview' && (                {lastUpdated ? `Last updated: ${lastUpdated.toLocaleTimeString()}` : 'Loading...'}

          <div className="space-y-6">              </p>

            {/* Bot Summary Cards */}            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">            <button

              {botList.map((bot) => (              onClick={loadBots}

                <div              disabled={loading}

                  key={bot.instance_id}              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white px-4 py-2 rounded-lg transition"

                  onClick={() => setSelectedBot(bot.instance_id)}            >

                  className={`bg-slate-800 border rounded-lg p-4 cursor-pointer transition ${              <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />

                    selectedBot === bot.instance_id              Refresh

                      ? 'border-blue-500 ring-1 ring-blue-500'            </button>

                      : 'border-slate-700 hover:border-slate-600'          </div>

                  }`}        )}

                >

                  <div className="flex items-start justify-between mb-2">        {/* Error Message */}

                    <h3 className="font-semibold text-white truncate">{bot.instance_id}</h3>        {error && (

                    <span className={`px-2 py-1 rounded text-xs font-medium ${getStatusBadge(bot.status)}`}>          <div className="bg-red-900 border border-red-700 text-red-100 px-4 py-3 rounded-lg mb-6 flex items-center gap-2">

                      {bot.status}            <AlertTriangle size={20} />

                    </span>            {error}

                  </div>          </div>

                          )}

                  <div className="space-y-1 text-sm">

                    <div className="flex justify-between">        {/* Tab Content */}

                      <span className="text-slate-400">P&L</span>        {activeTab === 'overview' && (

                      <span className={bot.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}>          <div className="space-y-6">

                        ${bot.total_pnl.toFixed(2)}            {/* Bot Summary Cards */}

                      </span>            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">

                    </div>              {botList.map((bot) => (

                    <div className="flex justify-between">                <div

                      <span className="text-slate-400">Positions</span>                  key={bot.instance_id}

                      <span className="text-white">{bot.open_positions} open</span>                  onClick={() => setSelectedBot(bot.instance_id)}

                    </div>                  className={`bg-slate-800 border rounded-lg p-4 cursor-pointer transition ${

                    <div className="flex justify-between">                    selectedBot === bot.instance_id

                      <span className="text-slate-400">Trades</span>                      ? 'border-blue-500 ring-1 ring-blue-500'

                      <span className="text-white">{bot.total_trades}</span>                      : 'border-slate-700 hover:border-slate-600'

                    </div>                  }`}

                    <div className="flex justify-between">                >

                      <span className="text-slate-400">Win Rate</span>                  <div className="flex items-start justify-between mb-2">

                      <span className="text-white">{(bot.win_rate * 100).toFixed(1)}%</span>                    <h3 className="font-semibold text-white truncate">{bot.instance_id}</h3>

                    </div>                    <span className={`px-2 py-1 rounded text-xs font-medium ${getStatusBadge(bot.status)}`}>

                  </div>                      {bot.status}

                </div>                    </span>

              ))}                  </div>

            </div>                  

                  <div className="space-y-1 text-sm">

            {/* Selected Bot Details */}                    <div className="flex justify-between">

            {selectedBot && botList.find((b) => b.instance_id === selectedBot) && (                      <span className="text-slate-400">P&L</span>

              <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">                      <span className={bot.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}>

                <h2 className="text-xl font-bold text-white mb-6">                        ${bot.total_pnl.toFixed(2)}

                  {selectedBot} - Detailed Stats                      </span>

                </h2>                    </div>

                                    <div className="flex justify-between">

                <div className="grid grid-cols-2 md:grid-cols-3 gap-6">                      <span className="text-slate-400">Positions</span>

                  {Object.entries(botList.find((b) => b.instance_id === selectedBot) || {}).map(                      <span className="text-white">{bot.open_positions} open</span>

                    ([key, value]) => {                    </div>

                      if (key === 'instance_id' || key === 'status') return null;                    <div className="flex justify-between">

                                            <span className="text-slate-400">Trades</span>

                      return (                      <span className="text-white">{bot.total_trades}</span>

                        <div key={key}>                    </div>

                          <p className="text-sm text-slate-400 capitalize mb-1">                    <div className="flex justify-between">

                            {key.replace(/_/g, ' ')}                      <span className="text-slate-400">Win Rate</span>

                          </p>                      <span className="text-white">{(bot.win_rate * 100).toFixed(1)}%</span>

                          <p className={`text-2xl font-semibold ${                    </div>

                            typeof value === 'number' && value < 0 ? 'text-red-400' : 'text-white'                  </div>

                          }`}>                </div>

                            {typeof value === 'number' ? value.toFixed(2) : value}              ))}

                          </p>            </div>

                        </div>

                      );            {/* Selected Bot Details */}

                    }            {selectedBot && botList.find((b) => b.instance_id === selectedBot) && (

                  )}              <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">

                </div>                <h2 className="text-xl font-bold text-white mb-6">

              </div>                  {selectedBot} - Detailed Stats

            )}                </h2>

          </div>                

        )}                <div className="grid grid-cols-2 md:grid-cols-3 gap-6">

                  {Object.entries(botList.find((b) => b.instance_id === selectedBot) || {}).map(

        {activeTab === 'manager' && <BotManager />}                    ([key, value]) => {

                      if (key === 'instance_id' || key === 'status') return null;

        {activeTab === 'positions' && (                      

          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">                      return (

            <h2 className="text-xl font-bold text-white mb-6">                        <div key={key}>

              Open Positions - {selectedBot || 'No bot selected'}                          <p className="text-sm text-slate-400 capitalize mb-1">

            </h2>                            {key.replace(/_/g, ' ')}

                                      </p>

            {botPositions.length === 0 ? (                          <p className={`text-2xl font-semibold ${

              <p className="text-slate-400 text-center py-8">No open positions</p>                            typeof value === 'number' && value < 0 ? 'text-red-400' : 'text-white'

            ) : (                          }`}>

              <div className="overflow-x-auto">                            {typeof value === 'number' ? value.toFixed(2) : value}

                <table className="w-full text-sm">                          </p>

                  <thead>                        </div>

                    <tr className="border-b border-slate-700">                      );

                      <th className="px-4 py-2 text-left text-slate-400">Market 1</th>                    }

                      <th className="px-4 py-2 text-left text-slate-400">Market 2</th>                  )}

                      <th className="px-4 py-2 text-left text-slate-400">Entry Time</th>                </div>

                      <th className="px-4 py-2 text-left text-slate-400">Z-Score</th>              </div>

                      <th className="px-4 py-2 text-left text-slate-400">Status</th>            )}

                    </tr>          </div>

                  </thead>        )}

                  <tbody>

                    {botPositions.map((pos) => (        {activeTab === 'manager' && <BotManager />}

                      <tr key={pos.position_id} className="border-b border-slate-700 hover:bg-slate-750">

                        <td className="px-4 py-2 text-white">{pos.market_1}</td>        {activeTab === 'positions' && (

                        <td className="px-4 py-2 text-white">{pos.market_2}</td>          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">

                        <td className="px-4 py-2 text-slate-400">            <h2 className="text-xl font-bold text-white mb-6">

                          {new Date(pos.entry_time).toLocaleString()}              Open Positions - {selectedBot || 'No bot selected'}

                        </td>            </h2>

                        <td className="px-4 py-2 text-white">{pos.z_score.toFixed(3)}</td>            

                        <td className="px-4 py-2">            {botPositions.length === 0 ? (

                          <span className="px-2 py-1 rounded text-xs font-medium bg-green-100 text-green-800">              <p className="text-slate-400 text-center py-8">No open positions</p>

                            {pos.status}            ) : (

                          </span>              <div className="overflow-x-auto">

                        </td>                <table className="w-full text-sm">

                      </tr>                  <thead>

                    ))}                    <tr className="border-b border-slate-700">

                  </tbody>                      <th className="px-4 py-2 text-left text-slate-400">Market 1</th>

                </table>                      <th className="px-4 py-2 text-left text-slate-400">Market 2</th>

              </div>                      <th className="px-4 py-2 text-left text-slate-400">Entry Time</th>

            )}                      <th className="px-4 py-2 text-left text-slate-400">Z-Score</th>

          </div>                      <th className="px-4 py-2 text-left text-slate-400">Status</th>

        )}                    </tr>

                  </thead>

        {activeTab === 'alerts' && (                  <tbody>

          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">                    {botPositions.map((pos) => (

            <h2 className="text-xl font-bold text-white mb-6">                      <tr key={pos.position_id} className="border-b border-slate-700 hover:bg-slate-750">

              Alerts - {selectedBot || 'No bot selected'}                        <td className="px-4 py-2 text-white">{pos.market_1}</td>

            </h2>                        <td className="px-4 py-2 text-white">{pos.market_2}</td>

                                    <td className="px-4 py-2 text-slate-400">

            {botAlerts.length === 0 ? (                          {new Date(pos.entry_time).toLocaleString()}

              <p className="text-slate-400 text-center py-8">No alerts</p>                        </td>

            ) : (                        <td className="px-4 py-2 text-white">{pos.z_score.toFixed(3)}</td>

              <div className="space-y-3">                        <td className="px-4 py-2">

                {botAlerts.map((alert, idx) => (                          <span className="px-2 py-1 rounded text-xs font-medium bg-green-100 text-green-800">

                  <div key={idx} className="bg-slate-700 rounded p-4 flex items-start gap-3">                            {pos.status}

                    <AlertTriangle size={20} className="text-yellow-400 flex-shrink-0 mt-0.5" />                          </span>

                    <div className="flex-1">                        </td>

                      <p className="text-white font-medium">{alert.title || 'Alert'}</p>                      </tr>

                      <p className="text-slate-300 text-sm mt-1">{alert.message || alert.description}</p>                    ))}

                      <p className="text-slate-500 text-xs mt-2">                  </tbody>

                        {new Date(alert.timestamp).toLocaleString()}                </table>

                      </p>              </div>

                    </div>            )}

                  </div>          </div>

                ))}        )}

              </div>

            )}        {activeTab === 'alerts' && (

          </div>          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">

        )}            <h2 className="text-xl font-bold text-white mb-6">

      </div>              Alerts - {selectedBot || 'No bot selected'}

    </div>            </h2>

  );            

};            {botAlerts.length === 0 ? (

              <p className="text-slate-400 text-center py-8">No alerts</p>

export default BotDashboard;            ) : (

              <div className="space-y-3">
                {botAlerts.map((alert, idx) => (
                  <div key={idx} className="bg-slate-700 rounded p-4 flex items-start gap-3">
                    <AlertTriangle size={20} className="text-yellow-400 flex-shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <p className="text-white font-medium">{alert.title || 'Alert'}</p>
                      <p className="text-slate-300 text-sm mt-1">{alert.message || alert.description}</p>
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
