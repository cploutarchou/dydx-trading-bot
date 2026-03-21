/**
 * Real-time backtest progress display component.
 * Shows progress bar, status, and detailed metrics during backtest execution.
 */

import React from 'react';
import { useBacktestProgress } from '../api/hooks';

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

  const status = progressQuery.data?.status || 'PENDING';
  const message = progressQuery.data?.message || '';
  const details = progressQuery.data || {};
  const progressPercent = progressQuery.progressPercent || 0;
  const errorMessage =
    (progressQuery.error as Error | null)?.message ||
    (progressQuery.isError ? 'Failed to fetch backtest progress' : null);
  const isConnected = !progressQuery.isError;

  React.useEffect(() => {
    if (progressQuery.isComplete) {
      onComplete?.();
    } else if (progressQuery.isFailed) {
      onError?.(message || 'Backtest failed');
    }
  }, [progressQuery.isComplete, progressQuery.isFailed, message, onComplete, onError]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'queued':
        return 'bg-blue-100 text-blue-800';
      case 'running':
        return 'bg-yellow-100 text-yellow-800';
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
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
      default:
        return 'bg-gray-500';
    }
  };

  return (
    <div className="w-full space-y-4 p-4 bg-white rounded-lg border border-gray-200">
      {/* Status Badge */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-700">Backtest Progress</h3>
        <span
          className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(status.toLowerCase())}`}
        >
          {status.toUpperCase()}
        </span>
      </div>

      {/* Progress Bar */}
      <div className="space-y-1">
        <div className="flex justify-between text-xs text-gray-600">
          <span>Overall Progress</span>
          <span>{Math.round(progressPercent)}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
          <div
            className={`h-full ${getProgressBarColor()} transition-all duration-300`}
            style={{ width: `${Math.min(progressPercent, 100)}%` }}
          />
        </div>
      </div>

      {/* Status Message */}
      {message && (
        <div className="text-sm text-gray-700">
          <p className="font-medium">{message}</p>
        </div>
      )}

      {/* Details */}
      {Object.keys(details).length > 0 && (
        <div className="bg-gray-50 rounded p-3 text-xs text-gray-600 space-y-1">
          {Object.entries(details).map(([key, value]) => (
            <div key={key} className="flex justify-between">
              <span className="font-medium">{key.replace(/_/g, ' ').toUpperCase()}:</span>
              <span className="text-gray-800">
                {typeof value === 'object' ? JSON.stringify(value) : String(value)}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Connection Status */}
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
        <span>{isConnected ? 'Connected to server' : 'Disconnected (reconnecting...)'}</span>
      </div>

      {/* Error Display */}
      {errorMessage && (
        <div className="bg-red-50 border border-red-200 rounded p-3 text-xs text-red-700">
          <p className="font-medium">Error: {errorMessage}</p>
        </div>
      )}
    </div>
  );
};

export default BacktestProgress;
