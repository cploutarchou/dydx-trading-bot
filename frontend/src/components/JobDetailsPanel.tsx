import { AlertTriangle, ChevronDown, ChevronUp, Clock, Cpu, RotateCcw, X } from 'lucide-react';
import React, { useState } from 'react';
import type { BotJob } from '../api/types';
import { StatusBadge } from './StatusBadge';

interface JobDetailsPanelProps {
  job: BotJob;
  onClose: () => void;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

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

function formatTimestamp(iso: string | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

function formatExecTime(ms: number | undefined): string {
  if (ms === undefined || ms === null) return '—';
  if (ms < 1_000) return `${ms}ms`;
  const totalSec = Math.floor(ms / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  const parts: string[] = [];
  if (h > 0) parts.push(`${h}h`);
  if (m > 0) parts.push(`${m}m`);
  if (s > 0 || parts.length === 0) parts.push(`${s}s`);
  return parts.join(' ');
}

// ── Sub-components ────────────────────────────────────────────────────────────

const Row: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div className="flex flex-col sm:flex-row sm:items-start gap-1 sm:gap-3 py-2 border-b border-slate-700/60 last:border-0">
    <span className="text-xs text-slate-400 sm:w-40 shrink-0 font-medium uppercase tracking-wide mt-0.5">
      {label}
    </span>
    <span className="text-sm text-slate-100 break-all">{children}</span>
  </div>
);

const ExpandableBlock: React.FC<{ label: string; content: string }> = ({ label, content }) => {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 transition font-medium"
      >
        {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        {label}
      </button>
      {open && (
        <pre className="mt-2 p-3 bg-slate-950 border border-slate-700 rounded-lg text-[11px] text-slate-300 overflow-auto max-h-64 whitespace-pre-wrap leading-relaxed">
          {content}
        </pre>
      )}
    </div>
  );
};

const JsonBlock: React.FC<{ label: string; data: Record<string, unknown> }> = ({ label, data }) => {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-300 transition font-medium"
      >
        {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        {label}
      </button>
      {open && (
        <pre className="mt-2 p-3 bg-slate-950 border border-slate-700 rounded-lg text-[11px] text-slate-300 overflow-auto max-h-64 leading-relaxed">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
};

// ── Main Component ────────────────────────────────────────────────────────────

export const JobDetailsPanel: React.FC<JobDetailsPanelProps> = ({ job, onClose }) => {
  const pct = Math.min(100, Math.max(0, job.progress_pct ?? 0));
  const isFailed = job.status === 'failed';
  const isCancelled = job.status === 'cancelled';
  const isRunning = job.status === 'running';

  return (
    // Backdrop dismiss is a pointer-only convenience (presentation role is the
    // jsx-a11y-sanctioned pattern); the dialog below owns the real semantics
    // and closes on Escape.
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      role="presentation"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      {/* Escape-to-dismiss on the dialog is the WAI-ARIA APG pattern;
            the rule reads any listener on a non-interactive role as a smell. */}
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions */}
      <div
        className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto bg-slate-800 border border-slate-700 rounded-2xl shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-label="Job details"
        onKeyDown={(e) => {
          if (e.key === 'Escape') onClose();
        }}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-4 p-5 border-b border-slate-700 sticky top-0 bg-slate-800 z-10">
          <div className="min-w-0">
            <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-0.5">
              Job Details
            </p>
            <h2 className="text-base font-bold text-white font-mono truncate">{job.job_id}</h2>
            <p className="text-xs text-slate-400 mt-0.5">{job.job_type}</p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <StatusBadge status={job.status} size="md" />
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition"
              aria-label="Close"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        <div className="p-5 space-y-1">
          {/* Progress bar (running jobs) */}
          {isRunning && (
            <div className="mb-4 p-4 bg-blue-900/20 border border-blue-800/40 rounded-xl">
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs font-medium text-blue-300 flex items-center gap-1.5">
                  <Clock size={12} />
                  Progress
                </span>
                <span className="text-xs font-bold text-white">{pct.toFixed(1)}%</span>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-2 overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full transition-all duration-500"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          )}

          {/* Core fields */}
          <Row label="Status">
            <StatusBadge status={job.status} size="md" />
          </Row>

          {!isRunning && pct > 0 && <Row label="Progress">{pct.toFixed(1)}%</Row>}

          <Row label="Created">
            {formatTimestamp(job.created_at)} ({formatRelative(job.created_at)})
          </Row>

          {job.started_at && (
            <Row label="Started">
              {formatTimestamp(job.started_at)} ({formatRelative(job.started_at)})
            </Row>
          )}

          {job.completed_at && (
            <Row label="Completed">
              {formatTimestamp(job.completed_at)} ({formatRelative(job.completed_at)})
            </Row>
          )}

          {job.execution_time_ms !== undefined && (
            <Row label="Execution Time">
              <span className="flex items-center gap-1.5">
                <Clock size={12} className="text-slate-400" />
                {formatExecTime(job.execution_time_ms)}
              </span>
            </Row>
          )}

          {job.process_id !== undefined && (
            <Row label="Process ID">
              <span className="flex items-center gap-1.5">
                <Cpu size={12} className="text-slate-400" />
                {job.process_id}
              </span>
            </Row>
          )}

          {/* Retry info */}
          {(job.retry_count !== undefined || job.max_retries !== undefined) && (
            <Row label="Retries">
              <span className="flex items-center gap-1.5">
                <RotateCcw size={12} className="text-slate-400" />
                {job.retry_count ?? 0} / {job.max_retries ?? '—'}
              </span>
            </Row>
          )}

          {/* Cancellation reason */}
          {isCancelled && job.cancellation_reason && (
            <div className="mt-3 p-3 bg-slate-700/50 border border-slate-600 rounded-lg">
              <p className="text-xs font-semibold text-slate-300 mb-1">Cancellation Reason</p>
              <p className="text-sm text-slate-200">{job.cancellation_reason}</p>
            </div>
          )}

          {/* Error section */}
          {isFailed && (
            <div className="mt-3 p-4 bg-rose-900/20 border border-rose-800/40 rounded-xl">
              <p className="text-xs font-semibold text-rose-300 flex items-center gap-1.5 mb-2">
                <AlertTriangle size={12} />
                Error Details
              </p>
              {job.error_message && (
                <p className="text-sm text-rose-200 mb-2">{job.error_message}</p>
              )}
              {job.error_traceback && (
                <ExpandableBlock label="Show traceback" content={job.error_traceback} />
              )}
            </div>
          )}

          {/* Metadata / Result / Config */}
          {job.result && Object.keys(job.result).length > 0 && (
            <div className="mt-3">
              <JsonBlock label="Result" data={job.result} />
            </div>
          )}

          {job.metadata && Object.keys(job.metadata).length > 0 && (
            <div className="mt-1">
              <JsonBlock label="Metadata" data={job.metadata} />
            </div>
          )}

          {job.config && Object.keys(job.config).length > 0 && (
            <div className="mt-1">
              <JsonBlock label="Config" data={job.config} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
