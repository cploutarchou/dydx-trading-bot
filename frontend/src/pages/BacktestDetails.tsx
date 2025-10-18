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
    results: BacktestResult[];
    all_trades: Trade[];
}

export const BacktestDetailsPage: React.FC = () => {
    const { runId } = useParams<{ runId: string }>();
    const [backtest, setBacktest] = useState<BacktestData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedResult, setSelectedResult] = useState<BacktestResult | null>(null);

    useEffect(() => {
        const fetchBacktest = async () => {
            try {
                if (runId) {
                    const response = await api.getBacktest(runId);
                    if (response.success && response.data) {
                        setBacktest(response.data);
                        // Select first result by default
                        if (response.data.results && response.data.results.length > 0) {
                            setSelectedResult(response.data.results[0]);
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

    const topMetrics = [
        { label: 'Total Trades', value: backtest.total_trades, icon: '📊' },
        {
            label: 'Win Rate',
            value: `${(backtest.win_rate * 100).toFixed(1)}%`,
            icon: '✅',
        },
        {
            label: 'Total PnL',
            value: `$${backtest.total_pnl_usd?.toFixed(2) || '0'}`,
            icon: '💰',
            color: backtest.total_pnl_usd >= 0 ? 'text-green-600' : 'text-red-600',
        },
        {
            label: 'Sharpe Ratio',
            value: backtest.sharpe_ratio?.toFixed(2) || 'N/A',
            icon: '📈',
        },
    ];

    const riskMetrics = [
        {
            label: 'Max Drawdown',
            value: `${(backtest.max_drawdown * 100).toFixed(1)}%`,
            icon: '📉',
        },
        {
            label: 'Profit Factor',
            value: backtest.profit_factor?.toFixed(2) || 'N/A',
            icon: '🎯',
        },
        {
            label: 'Profitable Trades',
            value: backtest.profitable_trades,
            icon: '💚',
        },
        {
            label: 'Duration',
            value: `${(backtest.duration_seconds / 60).toFixed(1)} min`,
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
                    </>
                )}
            </div>
        </div>
    );
};
