import { ArrowDownRight, ArrowUpRight, CircleDot } from 'lucide-react';
import React, { startTransition, useMemo, useState } from 'react';
import { TerminalDataGrid, type TerminalColumn, type TerminalMetric } from './TerminalDataGrid';

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

interface BacktestTradesPanelProps {
  trades: Trade[];
  isConnected: boolean;
  liveLabel: string;
}

const formatDateValue = (value: string): string => {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? '-'
    : parsed.toLocaleString([], {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
};

const formatCurrency = (value: number): string =>
  `$${value.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;

const normalizePercentValue = (value: number): number =>
  Math.abs(value) <= 1 ? value * 100 : value;

export const BacktestTradesPanel: React.FC<BacktestTradesPanelProps> = ({
  trades,
  isConnected,
  liveLabel,
}) => {
  const [outcomeFilter, setOutcomeFilter] = useState<'all' | 'wins' | 'losses'>('all');
  const [durationFilter, setDurationFilter] = useState<'all' | 'intraday' | 'swing'>('all');

  const filteredRows = useMemo(() => {
    return trades.filter((trade) => {
      const outcomeMatches =
        outcomeFilter === 'all' || (outcomeFilter === 'wins' ? trade.win : !trade.win);
      const durationMatches =
        durationFilter === 'all' ||
        (durationFilter === 'intraday' ? trade.duration_hours <= 24 : trade.duration_hours > 24);
      return outcomeMatches && durationMatches;
    });
  }, [durationFilter, outcomeFilter, trades]);

  const winners = trades.filter((trade) => trade.win).length;
  const losers = Math.max(trades.length - winners, 0);
  const netPnl = trades.reduce((sum, trade) => sum + trade.pnl_usd, 0);
  const avgDuration =
    trades.length > 0
      ? trades.reduce((sum, trade) => sum + trade.duration_hours, 0) / trades.length
      : 0;
  const avgReturn =
    trades.length > 0
      ? trades.reduce((sum, trade) => sum + normalizePercentValue(trade.pnl_pct), 0) / trades.length
      : 0;

  const metrics: TerminalMetric[] = [
    {
      label: 'Trades',
      value: trades.length,
      detail: `${winners} wins / ${losers} losses`,
    },
    {
      label: 'Net PnL',
      value: formatCurrency(netPnl),
      detail: 'Live cumulative execution',
      tone: netPnl >= 0 ? 'positive' : 'negative',
    },
    {
      label: 'Avg Duration',
      value: `${avgDuration.toFixed(1)}h`,
      detail: 'Mean hold time',
      tone: 'accent',
    },
    {
      label: 'Avg Return',
      value: `${avgReturn >= 0 ? '+' : ''}${avgReturn.toFixed(2)}%`,
      detail: 'Per-trade return',
      tone: avgReturn >= 0 ? 'positive' : 'negative',
    },
  ];

  const columns: TerminalColumn<Trade>[] = [
    {
      key: 'pair',
      label: 'Pair',
      sortable: true,
      sortValue: (row) => `${row.market_1}/${row.market_2}`,
      render: (row) => (
        <div>
          <p className="font-medium text-slate-100">
            {row.market_1}/{row.market_2}
          </p>
          <p className="mt-1 text-xs text-slate-500">{row.trade_id || 'Trade'}</p>
        </div>
      ),
    },
    {
      key: 'timing',
      label: 'Timing',
      sortable: true,
      sortValue: (row) => new Date(row.entry_timestamp).getTime(),
      render: (row) => (
        <div className="space-y-1 text-xs">
          <p className="text-slate-200">In {formatDateValue(row.entry_timestamp)}</p>
          <p className="text-slate-500">Out {formatDateValue(row.exit_timestamp)}</p>
        </div>
      ),
    },
    {
      key: 'signal',
      label: 'Signal',
      align: 'right',
      sortable: true,
      sortValue: (row) => row.entry_zscore,
      render: (row) => (
        <div className="space-y-1 text-right text-xs">
          <p className="font-medium text-slate-100">{row.entry_zscore.toFixed(3)}</p>
          <p className="text-slate-500">Exit {row.exit_zscore.toFixed(3)}</p>
        </div>
      ),
    },
    {
      key: 'duration',
      label: 'Duration',
      align: 'right',
      sortable: true,
      sortValue: (row) => row.duration_hours,
      render: (row) => <span className="text-slate-300">{row.duration_hours.toFixed(1)}h</span>,
    },
    {
      key: 'pnl',
      label: 'PnL',
      align: 'right',
      sortable: true,
      sortValue: (row) => row.pnl_usd,
      render: (row) => (
        <div className="text-right">
          <p className={`font-semibold ${row.pnl_usd >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
            {formatCurrency(row.pnl_usd)}
          </p>
          <p
            className={`mt-1 text-xs ${row.pnl_pct >= 0 ? 'text-emerald-400/80' : 'text-rose-400/80'}`}
          >
            {normalizePercentValue(row.pnl_pct).toFixed(2)}%
          </p>
        </div>
      ),
    },
    {
      key: 'outcome',
      label: 'Outcome',
      align: 'center',
      sortable: true,
      sortValue: (row) => (row.win ? 1 : 0),
      render: (row) => (
        <div className="inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em]">
          {row.win ? (
            <>
              <ArrowUpRight className="h-3.5 w-3.5 text-emerald-300" />
              <span className="text-emerald-200">Win</span>
            </>
          ) : (
            <>
              <ArrowDownRight className="h-3.5 w-3.5 text-rose-300" />
              <span className="text-rose-200">Loss</span>
            </>
          )}
        </div>
      ),
    },
  ];

  return (
    <TerminalDataGrid
      title="Trade Tape"
      subtitle="Execution log with live filtering, pagination, and pair-level trade intelligence."
      rows={filteredRows}
      columns={columns}
      rowKey={(row, index) => `${row.trade_id || `${row.market_1}-${row.market_2}`}-${index}`}
      getSearchText={(row) =>
        `${row.trade_id} ${row.market_1} ${row.market_2} ${row.win ? 'win' : 'loss'}`.toLowerCase()
      }
      searchPlaceholder="Search trade id, pair, or outcome"
      metrics={metrics}
      liveBadge={
        <span className="inline-flex items-center gap-1 rounded-full border border-slate-800 bg-slate-950/70 px-2.5 py-1 text-[11px] text-slate-400">
          <CircleDot
            className={`h-3.5 w-3.5 ${isConnected ? 'text-cyan-400' : 'text-amber-400'}`}
          />
          {liveLabel}
        </span>
      }
      toolbarExtras={
        <div className="flex flex-wrap items-center gap-2">
          {(['all', 'wins', 'losses'] as const).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => {
                startTransition(() => {
                  setOutcomeFilter(value);
                });
              }}
              className={`rounded-xl px-3 py-1.5 text-xs font-medium transition ${
                outcomeFilter === value
                  ? 'bg-cyan-500/15 text-cyan-200 shadow-[inset_0_0_0_1px_rgba(34,211,238,0.24)]'
                  : 'bg-slate-950 text-slate-400 hover:bg-slate-900 hover:text-slate-200'
              }`}
            >
              {value === 'all' ? 'All outcomes' : value}
            </button>
          ))}
          {(['all', 'intraday', 'swing'] as const).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => {
                startTransition(() => {
                  setDurationFilter(value);
                });
              }}
              className={`rounded-xl px-3 py-1.5 text-xs font-medium transition ${
                durationFilter === value
                  ? 'bg-slate-100 text-slate-950'
                  : 'bg-slate-950 text-slate-400 hover:bg-slate-900 hover:text-slate-200'
              }`}
            >
              {value === 'all' ? 'All durations' : value}
            </button>
          ))}
        </div>
      }
      filterToken={`${outcomeFilter}:${durationFilter}`}
      defaultSortKey="timing"
      emptyState={
        <div className="rounded-2xl border border-dashed border-slate-800 px-4 py-8 text-center text-sm text-slate-500">
          No trades match the active filters yet.
        </div>
      }
    />
  );
};
