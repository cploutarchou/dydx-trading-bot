/**
 * Real-time backtest progress display component.
 * Shows progress bar, status, and detailed metrics during backtest execution.
 */

import React from "react";
import { useBacktestProgress } from "../hooks/useBacktestProgress";

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
  // Get token directly from localStorage instead of state
  const getToken = React.useCallback(() => {
    const token = localStorage.getItem("access_token");
    console.log("[BacktestProgress] Token from localStorage:", {
      hasToken: !!token,
      tokenLength: token?.length,
      tokenPrefix: token?.substring(0, 20),
    });
    return token;
  }, []);

  const [token, setToken] = React.useState<string | null>(getToken());

  // Refresh token on component mount and when localStorage changes
  React.useEffect(() => {
    const storedToken = getToken();
    setToken(storedToken);

    // Also set up a listener for storage changes
    const handleStorageChange = () => {
      const updatedToken = getToken();
      setToken(updatedToken);
    };

    window.addEventListener("storage", handleStorageChange);
    return () => window.removeEventListener("storage", handleStorageChange);
  }, [getToken]);

  const progress = useBacktestProgress(runId, token);

  React.useEffect(() => {
    if (progress.status === "completed") {
      onComplete?.();
    } else if (progress.status === "failed") {
      onError?.(progress.message || "Backtest failed");
    }
  }, [progress.status, progress.message, onComplete, onError]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "queued":
        return "bg-blue-100 text-blue-800";
      case "running":
        return "bg-yellow-100 text-yellow-800";
      case "completed":
        return "bg-green-100 text-green-800";
      case "failed":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const getProgressBarColor = () => {
    switch (progress.status) {
      case "completed":
        return "bg-green-500";
      case "failed":
        return "bg-red-500";
      case "running":
        return "bg-blue-500";
      default:
        return "bg-gray-500";
    }
  };

  return (
    <div className="w-full space-y-4 p-4 bg-white rounded-lg border border-gray-200">
      {/* Status Badge */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-700">
          Backtest Progress
        </h3>
        <span
          className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(progress.status)}`}
        >
          {progress.status.toUpperCase()}
        </span>
      </div>

      {/* Progress Bar */}
      <div className="space-y-1">
        <div className="flex justify-between text-xs text-gray-600">
          <span>Overall Progress</span>
          <span>{Math.round(progress.progress)}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
          <div
            className={`h-full ${getProgressBarColor()} transition-all duration-300`}
            style={{ width: `${Math.min(progress.progress, 100)}%` }}
          />
        </div>
      </div>

      {/* Status Message */}
      {progress.message && (
        <div className="text-sm text-gray-700">
          <p className="font-medium">{progress.message}</p>
        </div>
      )}

      {/* Details */}
      {Object.keys(progress.details).length > 0 && (
        <div className="bg-gray-50 rounded p-3 text-xs text-gray-600 space-y-1">
          {Object.entries(progress.details).map(([key, value]) => (
            <div key={key} className="flex justify-between">
              <span className="font-medium">
                {key.replace(/_/g, " ").toUpperCase()}:
              </span>
              <span className="text-gray-800">
                {typeof value === "object" ? JSON.stringify(value) : String(value)}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Connection Status */}
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <div
          className={`w-2 h-2 rounded-full ${progress.isConnected ? "bg-green-500" : "bg-red-500"}`}
        />
        <span>
          {progress.isConnected
            ? "Connected to server"
            : "Disconnected (reconnecting...)"}
        </span>
      </div>

      {/* Error Display */}
      {progress.error && (
        <div className="bg-red-50 border border-red-200 rounded p-3 text-xs text-red-700">
          <p className="font-medium">Error: {progress.error}</p>
        </div>
      )}
    </div>
  );
};

export default BacktestProgress;
