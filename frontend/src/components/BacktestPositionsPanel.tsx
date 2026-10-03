import { CircleDot } from 'lucide-react';
import React, { startTransition, useMemo, useState } from 'react';
import { TerminalDataGrid, type TerminalColumn, type TerminalMetric } from './TerminalDataGrid';

interface Position {
  position_id: number;
  market_1: string;
  market_2: string;
  entry_timestamp: string;
  exit_timestamp: string | null;
  entry_price_m1: number;
  exit_price_m1: number | null;
  entry_price_m2: number;
  exit_price_m2: number | null;
  hedge_ratio: number;
  entry_zscore: number;
  exit_zscore: number | null;
  pnl_m1_usd: number;
  pnl_m2_usd: number;
  total_pnl_usd: number;
  status: string;
}

interface BacktestPositionsPanelProps {
  positions: Position[];
  isConnected: boolean;
  liveLabel: string;
}

const formatDateValue = (value: string | null | undefined): string => {
  if (!value) return 'Open';
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

const normalizeStatus = (value: string): 'open' | 'closed' | 'other' => {
  const normalized = value.trim().toLowerCase();
  if (normalized === 'open' || normalized === 'running') return 'open';
  if (normalized === 'closed' || normalized === 'completed') return 'closed';
  return 'other';
};

export const BacktestPositionsPanel: React.FC<BacktestPositionsPanelProps> = ({
  positions,
  isConnected,
  liveLabel,
}) => {
  const [statusFilter, setStatusFilter] = useState<'all' | 'open' | 'closed'>('all');
  const [pnlFilter, setPnlFilter] = useState<'all' | 'positive' | 'negative'>('all');

  const filteredRows = useMemo(() => {
    return positions.filter((position) => {
      const normalizedStatus = normalizeStatus(position.status);
      const statusMatches = statusFilter === 'all' || normalizedStatus === statusFilter;
      const pnlMatches =
        pnlFilter === 'all' ||
        (pnlFilter === 'positive' ? position.total_pnl_usd >= 0 : position.total_pnl_usd < 0);
      return statusMatches && pnlMatches;
    });
  }, [pnlFilter, positions, statusFilter]);

  const openCount = positions.filter(
    (position) => normalizeStatus(position.status) === 'open'
  ).length;
  const netPnl = positions.reduce((sum, position) => sum + position.total_pnl_usd, 0);
  const avgEntryZScore =
    positions.length > 0
      ? positions.reduce((sum, position) => sum + position.entry_zscore, 0) / positions.length
      : 0;
  const avgHedgeRatio =
    positions.length > 0
      ? positions.reduce((sum, position) => sum + position.hedge_ratio, 0) / positions.length
      : 0;

  const metrics: TerminalMetric[] = [
    {
      label: 'Positions',
      value: positions.length,
      detail: `${openCount} open / ${Math.max(positions.length - openCount, 0)} closed`,
    },
    {
      label: 'Net PnL',
      value: formatCurrency(netPnl),
      detail: 'Across all snapshots',
      tone: netPnl >= 0 ? 'positive' : 'negative',
    },
    {
      label: 'Avg Entry Z',
      value: avgEntryZScore.toFixed(3),
      detail: 'Entry signal intensity',
      tone: 'accent',
    },
    {
      label: 'Avg Hedge',
      value: avgHedgeRatio.toFixed(3),
      detail: 'Mean hedge ratio',
    },
  ];

  const columns: TerminalColumn<Position>[] = [
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
          <p className="mt-1 text-xs text-slate-500">Position #{row.position_id || '—'}</p>
        </div>
      ),
    },
    {
      key: 'lifecycle',
      label: 'Lifecycle',
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
      key: 'zscore',
      label: 'Signal',
      align: 'right',
      sortable: true,
      sortValue: (row) => row.entry_zscore,
      render: (row) => (
        <div className="space-y-1 text-right text-xs">
          <p className="font-medium text-slate-100">{row.entry_zscore.toFixed(3)}</p>
          <p className="text-slate-500">
            Exit {row.exit_zscore !== null ? row.exit_zscore.toFixed(3) : '—'}
          </p>
        </div>
      ),
    },
    {
      key: 'hedge',
      label: 'Hedge',
      align: 'right',
      sortable: true,
      sortValue: (row) => row.hedge_ratio,
      render: (row) => (
        <span className="font-mono text-slate-300">{row.hedge_ratio.toFixed(3)}</span>
      ),
    },
    {
      key: 'pnl',
      label: 'PnL',
      align: 'right',
      sortable: true,
      sortValue: (row) => row.total_pnl_usd,
      render: (row) => (
        <div className="text-right">
          <p
            className={`font-semibold ${row.total_pnl_usd >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}
          >
            {formatCurrency(row.total_pnl_usd)}
          </p>
        </div>
      ),
    },
    {
      key: 'status',
      label: 'Status',
      align: 'center',
      sortable: true,
      sortValue: (row) => row.status,
      render: (row) => {
        const normalized = normalizeStatus(row.status);
        return (
          <span
            className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${
              normalized === 'open'
                ? 'bg-cyan-500/12 text-cyan-200'
                : normalized === 'closed'
                  ? 'bg-emerald-500/12 text-emerald-200'
                  : 'bg-slate-700 text-slate-300'
            }`}
          >
            {row.status}
          </span>
        );
      },
    },
  ];

  return (
    <TerminalDataGrid
      title="Positions Matrix"
      subtitle="Snapshot-by-snapshot exposure view with live filters and terminal-grade density."
      rows={filteredRows}
      columns={columns}
      rowKey={(row, index) => `${row.position_id}-${row.entry_timestamp}-${index}`}
      getSearchText={(row) =>
        `${row.market_1} ${row.market_2} ${row.status} ${row.position_id}`.toLowerCase()
      }
      searchPlaceholder="Search pair, status, or position id"
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
          {(['all', 'open', 'closed'] as const).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => {
                startTransition(() => {
                  setStatusFilter(value);
                });
              }}
              className={`rounded-xl px-3 py-1.5 text-xs font-medium transition ${
                statusFilter === value
                  ? 'bg-cyan-500/15 text-cyan-200 shadow-[inset_0_0_0_1px_rgba(34,211,238,0.24)]'
                  : 'bg-slate-950 text-slate-400 hover:bg-slate-900 hover:text-slate-200'
              }`}
            >
              {value === 'all' ? 'All statuses' : value}
            </button>
          ))}
          {(['all', 'positive', 'negative'] as const).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => {
                startTransition(() => {
                  setPnlFilter(value);
                });
              }}
              className={`rounded-xl px-3 py-1.5 text-xs font-medium transition ${
                pnlFilter === value
                  ? 'bg-slate-100 text-slate-950'
                  : 'bg-slate-950 text-slate-400 hover:bg-slate-900 hover:text-slate-200'
              }`}
            >
              {value === 'all' ? 'All PnL' : value === 'positive' ? 'Winners' : 'Losers'}
            </button>
          ))}
        </div>
      }
      filterToken={`${statusFilter}:${pnlFilter}`}
      defaultSortKey="pnl"
      emptyState={
        <div className="rounded-2xl border border-dashed border-slate-800 px-4 py-8 text-center text-sm text-slate-500">
          No positions match the active filters yet.
        </div>
      }
    />
  );
};
