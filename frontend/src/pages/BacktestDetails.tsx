import { ArrowDown, ArrowUp, Loader } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
	Bar,
	BarChart,
	CartesianGrid,
	Line,
	LineChart,
	ResponsiveContainer,
	Scatter,
	ScatterChart,
	Tooltip,
	XAxis,
	YAxis,
} from 'recharts';
import api from '../api';
import BacktestProgress from '../components/BacktestProgress';

interface Trade {
    trade_number: number;
    entry_timestamp: string;
    exit_timestamp?: string;
    entry_price_1: number;
    entry_price_2: number;
    exit_price_1?: number;
    exit_price_2?: number;
    quantity_1: number;
    quantity_2: number;
    side_1: string;
    side_2: string;
    pnl?: number;
    pnl_usd?: number;
    entry_zscore?: number;
    exit_zscore?: number;
}

interface BacktestResult {
    market_1: string;
    market_2: string;
    total_trades: number;
    profitable_trades: number;
    win_rate: number;
    pnl: number;
    pnl_usd: number;
    sharpe_ratio?: number;
    max_drawdown?: number;
    profit_factor?: number;
    trades: Trade[];
}

interface BacktestData {
    id: number;
    run_id: string;
    status: string;
    created_at: string;
    start_date: string;
    end_date: string;
    num_pairs: number;
    total_markets: number;
    duration_seconds: number;
    total_trades: number;
    profitable_trades: number;
    win_rate: number;
    total_pnl: number;
    total_pnl_usd: number;
    sharpe_ratio: number;
    max_drawdown: number;
    profit_factor: number;
    starting_balance: number;
    ending_balance?: number;
    strategy_snapshot?: any;
    strategy_id?: number;
    results: BacktestResult[];
    all_trades: Trade[];
}

export const BacktestDetailsPage: React.FC = () => {
    const { runId } = useParams<{ runId: string }>();
    const navigate = useNavigate();
    const [backtest, setBacktest] = useState<BacktestData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedResult, setSelectedResult] = useState<BacktestResult | null>(null);
    const [logs, setLogs] = useState<Array<{ id: number; message: string; level: string; created_at: string }>>([]);
    const [activeTab, setActiveTab] = useState<'summary' | 'performance' | 'trades' | 'logs' | 'results'>('summary');
    const [selectedTradeId, setSelectedTradeId] = useState<number | null>(null);
    const [showTradeModal, setShowTradeModal] = useState(false);

    useEffect(() => {
        const fetchBacktest = async () => {
            try {
                if (runId) {
                    const response = await api.getBacktest(runId);
                    console.log('📊 API Response:', response);
                    
                    // api.getBacktest returns the ApiResponse wrapper
                    // response.data contains the actual backtest data
                    const backtestData = response?.data || response;
                    console.log('📊 Backtest data:', backtestData);
                    console.log('📊 Strategy snapshot:', backtestData?.strategy_snapshot);
                    
                    if (backtestData) {
                        setBacktest(backtestData);
                        // Select first result by default
                        if (backtestData.results && backtestData.results.length > 0) {
                            setSelectedResult(backtestData.results[0]);
                        }
                    }
                }
            } catch (err: any) {
                setError(err.message || 'Failed to fetch backtest');
            } finally {
                setLoading(false);
            }
        };

        fetchBacktest();
    }, [runId]);

    // Fetch logs for the backtest
    useEffect(() => {
        const fetchLogs = async () => {
            if (!runId) return;
            try {
                const response = await api.getBacktestLogs(runId);
                if (response.success && response.data?.logs) {
                    setLogs(response.data.logs);
                }
            } catch (err: any) {
                console.error('Failed to fetch backtest logs:', err);
            }
        };

        // Fetch logs immediately and then every 5 seconds if backtest is running
        fetchLogs();
        const interval = setInterval(fetchLogs, 5000);

        return () => clearInterval(interval);
    }, [runId]);

    // Generate equity curve data from trades
    const generateEquityCurveData = () => {
        if (!backtest?.all_trades) return [];

        let balance = backtest.starting_balance || 1000;
        const data = [{ timestamp: 'Start', balance, trades: 0 }];

        backtest.all_trades.forEach((trade, idx) => {
            if (trade.pnl_usd !== undefined) {
                balance += trade.pnl_usd;
                data.push({
                    timestamp: `Trade ${idx + 1}`,
                    balance,
                    trades: idx + 1,
                });
            }
        });

        return data;
    };

    // Generate P&L by pair data
    const generatePnlByPairData = () => {
        if (!backtest?.results) return [];

        return backtest.results.map((result) => ({
            pair: `${result.market_1.split('-')[0]}/${result.market_2.split('-')[0]}`,
            pnl: result.pnl_usd || 0,
            trades: result.total_trades,
        }));
    };

    // Generate trade performance scatter plot
    const generateTradeScatterData = () => {
        if (!selectedResult?.trades) return [];

        return selectedResult.trades.map((trade, idx) => ({
            tradeNumber: idx + 1,
            pnl: trade.pnl_usd || 0,
            zscore: trade.entry_zscore || 0,
        }));
    };

    const equityData = generateEquityCurveData();
    const pnlByPairData = generatePnlByPairData();
    const tradeScatterData = generateTradeScatterData();

    // Handler to create a new strategy using current settings
    const handleCreateStrategy = () => {
        if (!backtest || !backtest.strategy_snapshot) {
            alert('No strategy configuration available');
            return;
        }

        // Store the strategy config in sessionStorage to pass to the strategy creation page
        sessionStorage.setItem('strategyConfig', JSON.stringify(backtest.strategy_snapshot));
        
        // Navigate to strategy creation page
        navigate('/strategies/new', {
            state: {
                configSnapshot: backtest.strategy_snapshot,
                backtestRunId: backtest.run_id,
            }
        });
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-screen">
                <Loader className="w-8 h-8 animate-spin text-blue-600" />
            </div>
        );
    }

    if (error || !backtest) {
        return (
            <div className="p-8 text-center text-red-600">
                {error || 'Backtest not found'}
            </div>
        );
    }

    // Ensure all numeric values are valid before using toFixed()
    const safeWinRate = typeof backtest.win_rate === 'number' ? backtest.win_rate : null;
    const safeMaxDrawdown = typeof backtest.max_drawdown === 'number' ? backtest.max_drawdown : null;
    const safeSharpeRatio = typeof backtest.sharpe_ratio === 'number' ? backtest.sharpe_ratio : null;
    const safeProfitFactor = typeof backtest.profit_factor === 'number' ? backtest.profit_factor : null;
    const safeDurationSeconds = typeof backtest.duration_seconds === 'number' ? backtest.duration_seconds : 0;
    const safeTotalPnlUsd = typeof backtest.total_pnl_usd === 'number' ? backtest.total_pnl_usd : 0;

    const topMetrics = [
        { label: 'Total Trades', value: backtest.total_trades || 0, icon: '📊' },
        {
            label: 'Win Rate',
            value: safeWinRate !== null ? `${safeWinRate.toFixed(1)}%` : 'N/A',
            icon: '✅',
        },
        {
            label: 'Total PnL',
            value: `$${safeTotalPnlUsd.toFixed(2)}`,
            icon: '💰',
            color: safeTotalPnlUsd >= 0 ? 'text-green-600' : 'text-red-600',
        },
        {
            label: 'Sharpe Ratio',
            value: safeSharpeRatio !== null ? safeSharpeRatio.toFixed(2) : 'N/A',
            icon: '📈',
        },
    ];

    const riskMetrics = [
        {
            label: 'Max Drawdown',
            value: safeMaxDrawdown !== null ? `${safeMaxDrawdown.toFixed(1)}%` : 'N/A',
            icon: '📉',
        },
        {
            label: 'Profit Factor',
            value: safeProfitFactor !== null ? safeProfitFactor.toFixed(2) : 'N/A',
            icon: '🎯',
        },
        {
            label: 'Profitable Trades',
            value: backtest.profitable_trades || 0,
            icon: '💚',
        },
        {
            label: 'Duration',
            value: `${(safeDurationSeconds / 60).toFixed(1)} min`,
            icon: '⏱️',
        },
    ];

    return (
        <div className="min-h-screen bg-slate-50">
            <div className="max-w-7xl mx-auto p-8">
                {/* Header */}
                <div className="mb-8">
                    <h1 className="text-3xl font-bold mb-2 text-slate-900">
                        Backtest Results
                    </h1>
                    <div className="flex items-center gap-4">
                        <span className="text-slate-600">
                            {backtest.start_date} to {backtest.end_date}
                        </span>
                        <span
                            className={`px-3 py-1 rounded-full text-sm font-medium ${
                                backtest.status === 'completed'
                                    ? 'bg-green-100 text-green-700'
                                    : 'bg-yellow-100 text-yellow-700'
                            }`}
                        >
                            {backtest.status}
                        </span>
                        <span className="text-slate-600 text-sm">
                            Run ID: {backtest.run_id.substring(0, 8)}...
                        </span>
                    </div>
                </div>

                {/* Progress Tracker (for running backtests) */}
                {backtest.status === 'running' && (
                    <div className="mb-8">
                        <BacktestProgress runId={backtest.run_id} />
                    </div>
                )}

                {/* Top Metrics */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                    {topMetrics.map((metric) => (
                        <div
                            key={metric.label}
                            className="bg-white p-6 rounded-lg shadow hover:shadow-md transition"
                        >
                            <p className="text-3xl mb-2">{metric.icon}</p>
                            <p className="text-sm text-slate-600 mb-2">{metric.label}</p>
                            <p
                                className={`text-2xl font-bold ${
                                    metric.color ? metric.color : 'text-slate-900'
                                }`}
                            >
                                {metric.value}
                            </p>
                        </div>
                    ))}
                </div>

                {/* Charts Section */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
                    {/* Equity Curve */}
                    <div className="bg-white p-6 rounded-lg shadow">
                        <h2 className="text-xl font-bold mb-4 text-slate-900">
                            Equity Curve
                        </h2>
                        <ResponsiveContainer width="100%" height={300}>
                            <LineChart data={equityData}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis dataKey="timestamp" />
                                <YAxis />
                                <Tooltip formatter={(value: any) => `$${(value as number).toFixed(2)}`} />
                                <Line
                                    type="monotone"
                                    dataKey="balance"
                                    stroke="#2563eb"
                                    dot={false}
                                    isAnimationActive={false}
                                />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>

                    {/* P&L by Pair */}
                    <div className="bg-white p-6 rounded-lg shadow">
                        <h2 className="text-xl font-bold mb-4 text-slate-900">
                            P&L by Pair
                        </h2>
                        <ResponsiveContainer width="100%" height={300}>
                            <BarChart data={pnlByPairData}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis dataKey="pair" />
                                <YAxis />
                                <Tooltip formatter={(value: any) => `$${(value as number).toFixed(2)}`} />
                                <Bar dataKey="pnl" fill="#10b981" />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Risk Metrics */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                    {riskMetrics.map((metric) => (
                        <div
                            key={metric.label}
                            className="bg-white p-4 rounded-lg shadow"
                        >
                            <p className="text-2xl mb-2">{metric.icon}</p>
                            <p className="text-sm text-slate-600 mb-1">{metric.label}</p>
                            <p className="text-lg font-bold text-slate-900">
                                {metric.value}
                            </p>
                        </div>
                    ))}
                </div>

                {/* Strategy Configuration Section */}
                {backtest.strategy_snapshot && (
                    <div className="bg-white p-6 rounded-lg shadow mb-8">
                        <div className="flex justify-between items-center mb-4">
                            <h2 className="text-xl font-bold text-slate-900">
                                ⚙️ Strategy Configuration
                            </h2>
                            <div className="group relative">
                                <button
                                    onClick={handleCreateStrategy}
                                    className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition flex items-center gap-2"
                                    title="Create a new strategy using these parameters"
                                >
                                    ✨ Create Strategy
                                </button>
                                {/* Tooltip on hover */}
                                <div className="absolute bottom-full right-0 mb-2 hidden group-hover:block bg-slate-900 text-white text-sm rounded px-2 py-1 whitespace-nowrap z-10">
                                    Create a new strategy with these settings
                                </div>
                            </div>
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                            {Object.entries(backtest.strategy_snapshot).map(([key, value]) => (
                                <div key={key} className="bg-slate-50 p-3 rounded border border-slate-200">
                                    <p className="text-xs text-slate-600 font-medium mb-1">
                                        {key.replace(/_/g, ' ').toUpperCase()}
                                    </p>
                                    <p className="text-sm font-bold text-slate-900">
                                        {typeof value === 'boolean' ? (value ? '✓' : '✗') : String(value)}
                                    </p>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Pair Results Selection */}
                {backtest.results && backtest.results.length > 0 && (
                    <div className="bg-white p-6 rounded-lg shadow mb-8">
                        <h2 className="text-xl font-bold mb-4 text-slate-900">
                            Pair Results
                        </h2>
                        <div className="flex flex-wrap gap-2">
                            {backtest.results.map((result, idx) => (
                                <button
                                    key={idx}
                                    onClick={() => setSelectedResult(result)}
                                    className={`px-4 py-2 rounded-lg font-medium transition ${
                                        selectedResult === result
                                            ? 'bg-blue-600 text-white'
                                            : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                                    }`}
                                >
                                    {result.market_1.split('-')[0]}/
                                    {result.market_2.split('-')[0]}
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {/* Selected Pair Details */}
                {selectedResult && (
                    <>
                        {/* Trade Performance Scatter */}
                        {tradeScatterData.length > 0 && (
                            <div className="bg-white p-6 rounded-lg shadow mb-8">
                                <h2 className="text-xl font-bold mb-4 text-slate-900">
                                    Trade Performance - {selectedResult.market_1} /
                                    {selectedResult.market_2}
                                </h2>
                                <ResponsiveContainer width="100%" height={300}>
                                    <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                                        <CartesianGrid strokeDasharray="3 3" />
                                        <XAxis dataKey="tradeNumber" name="Trade #" />
                                        <YAxis dataKey="pnl" name="P&L ($)" />
                                        <Tooltip
                                            cursor={{ strokeDasharray: '3 3' }}
                                            formatter={(value: any) => `$${(value as number).toFixed(2)}`}
                                        />
                                        <Scatter
                                            name="Trades"
                                            data={tradeScatterData}
                                            fill="#8b5cf6"
                                        />
                                    </ScatterChart>
                                </ResponsiveContainer>
                            </div>
                        )}

                        {/* Trade Breakdown Table */}
                        <div className="bg-white p-6 rounded-lg shadow">
                            <h2 className="text-xl font-bold mb-4 text-slate-900">
                                Trade Details
                            </h2>
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead className="bg-slate-50 border-b">
                                        <tr>
                                            <th className="px-4 py-3 text-left font-semibold text-slate-700">
                                                #
                                            </th>
                                            <th className="px-4 py-3 text-left font-semibold text-slate-700">
                                                Entry Time
                                            </th>
                                            <th className="px-4 py-3 text-left font-semibold text-slate-700">
                                                Exit Time
                                            </th>
                                            <th className="px-4 py-3 text-right font-semibold text-slate-700">
                                                Entry Z-Score
                                            </th>
                                            <th className="px-4 py-3 text-right font-semibold text-slate-700">
                                                Exit Z-Score
                                            </th>
                                            <th className="px-4 py-3 text-right font-semibold text-slate-700">
                                                P&L ($)
                                            </th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {selectedResult.trades.map((trade, idx) => (
                                            <tr
                                                key={idx}
                                                className={`border-b hover:bg-slate-50 ${
                                                    (trade.pnl_usd || 0) >= 0
                                                        ? 'bg-green-50'
                                                        : 'bg-red-50'
                                                }`}
                                            >
                                                <td className="px-4 py-3 font-medium text-slate-900">
                                                    {trade.trade_number}
                                                </td>
                                                <td className="px-4 py-3 text-slate-700">
                                                    {new Date(
                                                        trade.entry_timestamp
                                                    ).toLocaleString()}
                                                </td>
                                                <td className="px-4 py-3 text-slate-700">
                                                    {trade.exit_timestamp
                                                        ? new Date(
                                                            trade.exit_timestamp
                                                        ).toLocaleString()
                                                        : '-'}
                                                </td>
                                                <td className="px-4 py-3 text-right text-slate-700">
                                                    {trade.entry_zscore?.toFixed(3) || '-'}
                                                </td>
                                                <td className="px-4 py-3 text-right text-slate-700">
                                                    {trade.exit_zscore?.toFixed(3) || '-'}
                                                </td>
                                                <td
                                                    className={`px-4 py-3 text-right font-bold ${
                                                        (trade.pnl_usd || 0) >= 0
                                                            ? 'text-green-700'
                                                            : 'text-red-700'
                                                    }`}
                                                >
                                                    <div className="flex items-center justify-end gap-2">
                                                        {(trade.pnl_usd || 0) >= 0 ? (
                                                            <ArrowUp className="w-4 h-4" />
                                                        ) : (
                                                            <ArrowDown className="w-4 h-4" />
                                                        )}
                                                        ${(trade.pnl_usd || 0).toFixed(2)}
                                                    </div>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        {/* Backtest Logs Section */}
                        <div className="bg-white p-6 rounded-lg shadow">
                            <h2 className="text-xl font-bold mb-4 text-slate-900">
                                Backtest Logs
                            </h2>
                            {logs.length === 0 ? (
                                <p className="text-slate-600">No logs available</p>
                            ) : (
                                <div className="bg-slate-900 rounded p-4 font-mono text-sm text-slate-100 max-h-96 overflow-y-auto">
                                    {logs.map((log, idx) => (
                                        <div
                                            key={idx}
                                            className={`py-1 ${
                                                log.level === 'error'
                                                    ? 'text-red-400'
                                                    : log.level === 'warning'
                                                    ? 'text-yellow-400'
                                                    : log.level === 'debug'
                                                    ? 'text-blue-400'
                                                    : 'text-green-400'
                                            }`}
                                        >
                                            <span className="text-slate-500">
                                                {new Date(log.created_at).toLocaleTimeString()}
                                            </span>
                                            {' '}
                                            <span className="text-slate-400">
                                                [{log.level.toUpperCase()}]
                                            </span>
                                            {' '}
                                            {log.message}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};
