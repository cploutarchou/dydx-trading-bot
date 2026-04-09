/**
 * P1.10: Reusable table control patterns for terminal-grade data tables.
 * Provides filtering, pagination, density controls, and export actions.
 */

import { ChevronLeft, ChevronRight, Download } from 'lucide-react';

export type TableDensity = 'comfortable' | 'compact' | 'dense';

export interface TableFilters {
  [key: string]: string | boolean | number | undefined;
}

export interface TableControlsProps {
  onFiltersChange?: (filters: TableFilters) => void;
  onDensityChange?: (density: TableDensity) => void;
  onExport?: () => void;
  density?: TableDensity;
  showExport?: boolean;
  columnNames?: string[];
}

export interface PaginationProps {
  currentPage: number;
  totalPages: number;
  pageSize: number;
  totalItems: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
  pageSizeOptions?: number[];
}

/**
 * P1.10: Table header with density selector and export action
 */
export function TableHeader({
  title,
  density = 'comfortable',
  onDensityChange,
  onExport,
  showExport = true,
}: {
  title: string;
  density?: TableDensity;
  onDensityChange?: (d: TableDensity) => void;
  onExport?: () => void;
  showExport?: boolean;
}) {
  return (
    <div className="flex items-center justify-between px-4 py-3 bg-slate-900/50 border-b border-slate-800">
      <h3 className="text-sm font-semibold text-white">{title}</h3>
      <div className="flex items-center gap-2">
        {onDensityChange && (
          <div className="flex gap-1 border border-slate-700 rounded p-1">
            {(['comfortable', 'compact', 'dense'] as TableDensity[]).map((d) => (
              <button
                key={d}
                onClick={() => onDensityChange(d)}
                className={`px-2 py-1 text-xs rounded transition ${
                  density === d
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                }`}
              >
                {d.charAt(0).toUpperCase()}
              </button>
            ))}
          </div>
        )}
        {showExport && onExport && (
          <button
            onClick={onExport}
            className="p-2 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
            title="Export data"
          >
            <Download className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
}

/**
 * P1.10: Quick filter row for table column searches
 */
export function TableFilterRow({
  columns,
  onFilter,
}: {
  columns: string[];
  onFilter: (col: string, value: string) => void;
}) {
  return (
    <tr className="bg-slate-800/30 border-b border-slate-700">
      {columns.map((col) => (
        <td key={col} className="px-4 py-2">
          <input
            type="text"
            placeholder={`Filter ${col}...`}
            onChange={(e) => onFilter(col, e.target.value)}
            className="w-full px-2 py-1 text-xs bg-slate-900 border border-slate-700 rounded text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none"
          />
        </td>
      ))}
    </tr>
  );
}

/**
 * P1.10: Pagination controls for large datasets
 */
export function PaginationControls({
  currentPage,
  totalPages,
  pageSize,
  totalItems,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 25, 50, 100],
}: PaginationProps) {
  return (
    <div className="flex items-center justify-between px-4 py-3 bg-slate-900/30 border-t border-slate-800">
      <div className="flex items-center gap-4">
        <label className="text-xs text-slate-400">
          Rows per page:
          <select
            value={pageSize}
            onChange={(e) => onPageSizeChange(parseInt(e.target.value))}
            className="ml-2 px-2 py-1 bg-slate-800 border border-slate-700 rounded text-white text-xs focus:outline-none"
          >
            {pageSizeOptions.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>
        <span className="text-xs text-slate-500">
          {(currentPage - 1) * pageSize + 1}–{Math.min(currentPage * pageSize, totalItems)} of{' '}
          {totalItems}
        </span>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage <= 1}
          className="p-2 rounded hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed text-slate-400 hover:text-slate-200 transition"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
        <span className="text-xs text-slate-400">
          Page {currentPage} of {totalPages}
        </span>
        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= totalPages}
          className="p-2 rounded hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed text-slate-400 hover:text-slate-200 transition"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

/**
 * P1.10: Get CSS density class for compact/comfortable/dense spacing
 */
export function getDensityClass(density: TableDensity) {
  return {
    comfortable: 'py-3 px-4',
    compact: 'py-2 px-3',
    dense: 'py-1 px-2',
  }[density];
}

/**
 * P1.10: Export table data as CSV
 */
export function exportTableAsCSV(data: any[], columns: string[], filename: string = 'export.csv') {
  const headers = columns.join(',');
  const rows = data.map((row) =>
    columns
      .map((col) => {
        const val = row[col];
        if (typeof val === 'string' && val.includes(',')) {
          return `"${val}"`;
        }
        return val ?? '';
      })
      .join(',')
  );

  const csv = [headers, ...rows].join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  window.URL.revokeObjectURL(url);
}
