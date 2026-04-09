import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, Search } from 'lucide-react';
import React, { startTransition, useDeferredValue, useEffect, useMemo, useState } from 'react';

type SortDirection = 'asc' | 'desc';

export interface TerminalMetric {
  label: string;
  value: React.ReactNode;
  detail?: React.ReactNode;
  tone?: 'default' | 'positive' | 'negative' | 'accent';
}

export interface TerminalColumn<T> {
  key: string;
  label: string;
  align?: 'left' | 'center' | 'right';
  sortable?: boolean;
  render: (_row: T) => React.ReactNode;
  sortValue?: (_row: T) => string | number;
  widthClassName?: string;
}

interface TerminalDataGridProps<T> {
  title: string;
  subtitle?: string;
  rows: T[];
  columns: TerminalColumn<T>[];
  rowKey: (_row: T, _index: number) => string;
  searchPlaceholder?: string;
  getSearchText: (_row: T) => string;
  metrics?: TerminalMetric[];
  toolbarExtras?: React.ReactNode;
  emptyState: React.ReactNode;
  liveBadge?: React.ReactNode;
  filterToken?: string;
  defaultSortKey?: string;
  defaultSortDirection?: SortDirection;
  defaultPageSize?: number;
}

const toneClasses: Record<NonNullable<TerminalMetric['tone']>, string> = {
  default: 'text-slate-100',
  positive: 'text-emerald-300',
  negative: 'text-rose-300',
  accent: 'text-cyan-300',
};

export function TerminalDataGrid<T>({
  title,
  subtitle,
  rows,
  columns,
  rowKey,
  searchPlaceholder = 'Search',
  getSearchText,
  metrics = [],
  toolbarExtras,
  emptyState,
  liveBadge,
  filterToken,
  defaultSortKey,
  defaultSortDirection = 'desc',
  defaultPageSize = 12,
}: TerminalDataGridProps<T>) {
  const initialSortableColumn = columns.find((column) => column.sortable)?.key || columns[0]?.key || '';
  const [searchTerm, setSearchTerm] = useState('');
  const deferredSearchTerm = useDeferredValue(searchTerm);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(defaultPageSize);
  const [sortKey, setSortKey] = useState(defaultSortKey || initialSortableColumn);
  const [sortDirection, setSortDirection] = useState<SortDirection>(defaultSortDirection);

  useEffect(() => {
    setPage(1);
  }, [filterToken, deferredSearchTerm, pageSize]);

  useEffect(() => {
    if (!columns.some((column) => column.key === sortKey && column.sortable)) {
      setSortKey(defaultSortKey || initialSortableColumn);
      setSortDirection(defaultSortDirection);
    }
  }, [columns, defaultSortDirection, defaultSortKey, initialSortableColumn, sortKey]);

  const filteredRows = useMemo(() => {
    const normalizedQuery = deferredSearchTerm.trim().toLowerCase();
    if (!normalizedQuery) {
      return rows;
    }

    return rows.filter((row) => getSearchText(row).toLowerCase().includes(normalizedQuery));
  }, [deferredSearchTerm, getSearchText, rows]);

  const sortedRows = useMemo(() => {
    const sortableColumn = columns.find((column) => column.key === sortKey && column.sortable);
    if (!sortableColumn?.sortValue) {
      return filteredRows;
    }

    const nextRows = [...filteredRows];
    nextRows.sort((left, right) => {
      const leftValue = sortableColumn.sortValue?.(left);
      const rightValue = sortableColumn.sortValue?.(right);

      if (typeof leftValue === 'string' && typeof rightValue === 'string') {
        return sortDirection === 'asc'
          ? leftValue.localeCompare(rightValue)
          : rightValue.localeCompare(leftValue);
      }

      const leftNumber = typeof leftValue === 'number' ? leftValue : Number(leftValue || 0);
      const rightNumber = typeof rightValue === 'number' ? rightValue : Number(rightValue || 0);
      return sortDirection === 'asc' ? leftNumber - rightNumber : rightNumber - leftNumber;
    });

    return nextRows;
  }, [columns, filteredRows, sortDirection, sortKey]);

  const pageCount = Math.max(1, Math.ceil(sortedRows.length / pageSize));
  const safePage = Math.min(page, pageCount);
  const pagedRows = useMemo(() => {
    const start = (safePage - 1) * pageSize;
    return sortedRows.slice(start, start + pageSize);
  }, [pageSize, safePage, sortedRows]);

  useEffect(() => {
    if (page !== safePage) {
      setPage(safePage);
    }
  }, [page, safePage]);

  const rangeStart = sortedRows.length === 0 ? 0 : (safePage - 1) * pageSize + 1;
  const rangeEnd = Math.min(safePage * pageSize, sortedRows.length);

  const toggleSort = (column: TerminalColumn<T>) => {
    if (!column.sortable) {
      return;
    }
    startTransition(() => {
      setPage(1);
      setSortDirection((currentDirection) =>
        sortKey === column.key ? (currentDirection === 'asc' ? 'desc' : 'asc') : 'desc'
      );
      setSortKey(column.key);
    });
  };

  return (
    <div className="rounded-[24px] border border-slate-800 bg-slate-900/80 shadow-[0_16px_60px_rgba(2,6,23,0.3)]">
      <div className="border-b border-slate-800 px-4 py-4 sm:px-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-xl font-semibold text-slate-100">{title}</h2>
              {liveBadge}
            </div>
            {subtitle && <p className="mt-1 text-sm text-slate-400">{subtitle}</p>}
          </div>
          <div className="flex min-w-full flex-col gap-3 lg:min-w-[360px] lg:max-w-[520px]">
            <label className="relative block">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
              <input
                value={searchTerm}
                onChange={(event) => {
                  const nextValue = event.target.value;
                  startTransition(() => {
                    setSearchTerm(nextValue);
                  });
                }}
                placeholder={searchPlaceholder}
                className="w-full rounded-2xl border border-slate-800 bg-slate-950/80 py-2.5 pl-10 pr-4 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-cyan-500/40 focus:ring-2 focus:ring-cyan-500/10"
              />
            </label>
            {toolbarExtras}
          </div>
        </div>
      </div>

      {metrics.length > 0 && (
        <div className="grid grid-cols-2 gap-3 border-b border-slate-800 px-4 py-4 sm:grid-cols-4 sm:px-5">
          {metrics.map((metric) => (
            <div key={metric.label} className="rounded-2xl border border-slate-800 bg-slate-950/70 p-3">
              <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{metric.label}</p>
              <p className={`mt-2 text-lg font-semibold ${toneClasses[metric.tone || 'default']}`}>
                {metric.value}
              </p>
              {metric.detail && <p className="mt-1 text-xs text-slate-500">{metric.detail}</p>}
            </div>
          ))}
        </div>
      )}

      {sortedRows.length === 0 ? (
        <div className="px-4 py-10 sm:px-5">{emptyState}</div>
      ) : (
        <>
          <div className="overflow-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr>
                  {columns.map((column) => {
                    const alignClass =
                      column.align === 'right'
                        ? 'text-right'
                        : column.align === 'center'
                          ? 'text-center'
                          : 'text-left';
                    const isActiveSort = column.key === sortKey;
                    return (
                      <th
                        key={column.key}
                        className={`sticky top-0 z-10 border-b border-slate-800 bg-slate-950/95 px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500 backdrop-blur ${alignClass} ${column.widthClassName || ''}`}
                      >
                        <button
                          type="button"
                          onClick={() => toggleSort(column)}
                          className={`inline-flex w-full items-center gap-2 ${column.align === 'right' ? 'justify-end' : column.align === 'center' ? 'justify-center' : 'justify-start'} ${column.sortable ? 'cursor-pointer' : 'cursor-default'}`}
                        >
                          <span>{column.label}</span>
                          {column.sortable ? (
                            isActiveSort ? (
                              sortDirection === 'asc' ? (
                                <ArrowUp className="h-3.5 w-3.5 text-cyan-300" />
                              ) : (
                                <ArrowDown className="h-3.5 w-3.5 text-cyan-300" />
                              )
                            ) : (
                              <ArrowUpDown className="h-3.5 w-3.5 text-slate-600" />
                            )
                          ) : null}
                        </button>
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {pagedRows.map((row, index) => (
                  <tr
                    key={rowKey(row, index)}
                    className="border-b border-slate-800/80 bg-slate-900/50 transition hover:bg-slate-900/85"
                  >
                    {columns.map((column) => {
                      const alignClass =
                        column.align === 'right'
                          ? 'text-right'
                          : column.align === 'center'
                            ? 'text-center'
                            : 'text-left';
                      return (
                        <td key={column.key} className={`px-4 py-3 align-top ${alignClass}`}>
                          {column.render(row)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-col gap-3 border-t border-slate-800 px-4 py-4 text-sm sm:flex-row sm:items-center sm:justify-between sm:px-5">
            <div className="flex flex-wrap items-center gap-3 text-slate-400">
              <span>
                Showing {rangeStart}-{rangeEnd} of {sortedRows.length}
              </span>
              <label className="inline-flex items-center gap-2">
                <span className="text-slate-500">Rows</span>
                <select
                  value={pageSize}
                  onChange={(event) => {
                    startTransition(() => {
                      setPageSize(Number(event.target.value));
                    });
                  }}
                  className="rounded-xl border border-slate-800 bg-slate-950 px-2 py-1 text-slate-200 outline-none"
                >
                  {[10, 20, 50, 100].map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setPage((current) => Math.max(1, current - 1))}
                disabled={safePage === 1}
                className="inline-flex items-center gap-1 rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-slate-300 transition hover:border-slate-700 hover:text-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <ChevronLeft className="h-4 w-4" />
                Prev
              </button>
              <span className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-slate-300">
                Page {safePage} / {pageCount}
              </span>
              <button
                type="button"
                onClick={() => setPage((current) => Math.min(pageCount, current + 1))}
                disabled={safePage >= pageCount}
                className="inline-flex items-center gap-1 rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-slate-300 transition hover:border-slate-700 hover:text-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Next
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default TerminalDataGrid;
