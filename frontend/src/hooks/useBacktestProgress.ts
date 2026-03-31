/**
 * Custom hook for real-time backtest progress tracking via WebSocket
 */

import { useCallback, useEffect, useState } from 'react';
import api from '../api';

interface BacktestProgressState {
  progress: number;
  status: string;
  message: string;
  details: Record<string, unknown>;
  error: string | null;
  isConnected: boolean;
}

const initialState: BacktestProgressState = {
  progress: 0,
  status: 'queued',
  message: '',
  details: {},
  error: null,
  isConnected: false,
};

export const useBacktestProgress = (runId: string, token: string | null) => {
  const [state, setState] = useState<BacktestProgressState>(initialState);

  const connect = useCallback(() => {
    if (!token) {
      return;
    }

    try {
      // Use centralized api helper which builds WS url from VITE_API_URL
      const ws = api.connectBacktestSocket(runId, token);

      ws.onopen = () => {
        setState((prev) => ({ ...prev, isConnected: true, error: null }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          setState((prev) => ({
            ...prev,
            progress: data.progress || prev.progress,
            status: data.status || prev.status,
            message: data.message || prev.message,
            details: data.details || prev.details,
          }));
        } catch (error) {
          console.error('[useBacktestProgress] Error parsing WebSocket message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('[useBacktestProgress] WebSocket error:', error);
        setState((prev) => ({
          ...prev,
          error: 'Connection error',
          isConnected: false,
        }));
      };

      ws.onclose = () => {
        setState((prev) => ({ ...prev, isConnected: false }));
      };

      return ws;
    } catch (error) {
      console.error('[useBacktestProgress] Error connecting to WebSocket:', error);
      setState((prev) => ({
        ...prev,
        error: 'Failed to connect to WebSocket',
        isConnected: false,
      }));
      return null;
    }
  }, [runId, token]);

  useEffect(() => {
    let ws: WebSocket | null = null;

    if (token && runId) {
      ws = connect() || null;
    }

    return () => {
      if (ws) {
        ws.close();
      }
    };
  }, [runId, token, connect]);

  return state;
};
