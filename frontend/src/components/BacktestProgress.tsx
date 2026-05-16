/**
 * Real-time backtest progress display component.
 * Shows progress bar, status, and detailed metrics during backtest execution.
 */

import React from 'react';
import { useBacktestProgress } from '../api/hooks';
import {
  LiveStateBadge,
  formatBacktestProgressSourceLabel,
  resolveBacktestStreamBadge,
} from './ui/LiveState';

interface BacktestProgressProps {
  runId: string;
  onComplete?: () => void;
  onError?: (_error: string) => void;
}

export const BacktestProgress: React.FC<BacktestProgressProps> = ({
  runId,
  onComplete,
  onError,
}) => {
  const progressQuery = useBacktestProgress(runId);
  const completionHandledRef = React.useRef(false);
  const failureHandledRef = React.useRef(false);

  const status =
    typeof progressQuery.data?.status === 'string' && progressQuery.data.status.length > 0
      ? progressQuery.data.status
      : 'PENDING';
  const details = (progressQuery.data ?? {}) as Record<string, unknown>;
  const message = typeof details.message === 'string' ? details.message : '';
  const progressPercent = progressQuery.progressPercent || 0;
  const progressSource = formatBacktestProgressSourceLabel(progressQuery.progressSource);
  const errorMessage =
    (progressQuery.error as Error | null)?.message ||
    (progressQuery.isError ? 'Failed to fetch backtest progress' : null);
  const isConnected = progressQuery.isConnected ?? !progressQuery.isError;
  const streamBadge = resolveBacktestStreamBadge(progressQuery.progressSource, isConnected);

  React.useEffect(() => {
    completionHandledRef.current = false;
    failureHandledRef.current = false;
  }, [runId]);

  React.useEffect(() => {
    if (progressQuery.isComplete && !completionHandledRef.current) {
      completionHandledRef.current = true;
      onComplete?.();
    }

    if (
      (progressQuery.isFailed ||
        progressQuery.isTimedOut ||
        progressQuery.isStalled ||
        progressQuery.isCancelled) &&
      !failureHandledRef.current
    ) {
      failureHandledRef.current = true;
      onError?.(
        message ||
          (progressQuery.isCancelled
            ? 'Backtest cancelled'
            : progressQuery.isTimedOut
              ? 'Backtest timed out'
              : progressQuery.isStalled
                ? 'Backtest stalled'
                : 'Backtest failed')
      );
    }
  }, [
    message,
    onComplete,
    onError,
    progressQuery.isCancelled,
    progressQuery.isComplete,
    progressQuery.isFailed,
    progressQuery.isStalled,
    progressQuery.isTimedOut,
  ]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending':
      case 'queued':
        return 'bg-yellow-900 text-yellow-300';
      case 'running':
        return 'bg-blue-900 text-blue-300';
      case 'completed':
        return 'bg-green-900 text-green-300';
      case 'cancelled':
        return 'bg-slate-700 text-slate-300';
      case 'timeout':
      case 'timed_out':
        return 'bg-orange-900 text-orange-300';
      case 'stale':
      case 'stalled':
        return 'bg-amber-900 text-amber-300';
      case 'failed':
        return 'bg-red-900 text-red-300';
      default:
        return 'bg-slate-700 text-slate-300';
    }
  };

  const getProgressBarColor = () => {
    switch (status.toLowerCase()) {
      case 'completed':
        return 'bg-green-500';
      case 'failed':
        return 'bg-red-500';
      case 'running':
        return 'bg-blue-500';
      case 'cancelled':
        return 'bg-slate-500';
      case 'timeout':
      case 'timed_out':
        return 'bg-orange-500';
      case 'stale':
      case 'stalled':
        return 'bg-amber-500';
      default:
        return 'bg-gray-500';
    }
  };

  return (
    <div className="w-full space-y-4 p-4 bg-slate-800 rounded-lg border border-slate-700">
      {/* Status Badge */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white">Backtest Progress</h3>
        <div className="flex items-center gap-2">
          <LiveStateBadge
            tone={streamBadge.tone}
            label={streamBadge.label}
            className="rounded-full px-3 py-1 normal-case"
          />
          <span
            className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(status.toLowerCase())}`}
          >
            {status.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="space-y-1">
        <div className="flex justify-between text-xs text-slate-400">
          <span>Overall Progress</span>
          <span>{Math.round(progressPercent)}%</span>
        </div>
        <div className="w-full bg-slate-700 rounded-full h-2 overflow-hidden">
          <div
            className={`h-full ${getProgressBarColor()} transition-all duration-300`}
            style={{ width: `${Math.min(progressPercent, 100)}%` }}
          />
        </div>
      </div>

      {/* Status Message */}
      {message && (
        <div className="text-sm text-slate-300">
          <p className="font-medium">{message}</p>
        </div>
      )}

      {/* Details */}
      {Object.keys(details).length > 0 && (
        <div className="bg-slate-900 rounded p-3 text-xs text-slate-400 space-y-1">
          {Object.entries(details).map(([key, value]) => (
            <div key={key} className="flex justify-between">
              <span className="font-medium">{key.replace(/_/g, ' ').toUpperCase()}:</span>
              <span className="text-slate-200">
                {typeof value === 'object' ? JSON.stringify(value) : String(value)}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Connection Status */}
      <div className="flex items-center gap-2 text-xs text-slate-400">
        <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
        <span>
          {isConnected ? 'Connected to server' : 'Disconnected (reconnecting...)'} · source{' '}
          {progressSource}
        </span>
      </div>

      {/* Error Display */}
      {errorMessage && (
        <div className="bg-red-900 border border-red-700 rounded p-3 text-xs text-red-200">
          <p className="font-medium">Error: {errorMessage}</p>
        </div>
      )}
    </div>
  );
};

export default BacktestProgress;
