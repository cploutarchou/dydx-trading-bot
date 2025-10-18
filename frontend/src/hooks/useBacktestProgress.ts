/**
 * Custom hook for real-time backtest progress tracking via WebSocket
 */

import { useCallback, useEffect, useState } from 'react';

interface BacktestProgressState {
  progress: number;
  status: string;
  message: string;
  details: Record<string, any>;
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
      console.log('[useBacktestProgress] No token available, cannot connect');
      return;
    }

    try {
      // Determine WebSocket protocol and backend host
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      
      // Extract backend host from API base URL
      // API_BASE_URL is like http://localhost:8888, we need localhost:8888
      const apiBaseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8888';
      const apiUrl = new URL(apiBaseUrl);
      const backendHost = apiUrl.host; // This gives us "localhost:8888"
      
      const wsUrl = `${wsProtocol}//${backendHost}/ws/backtest/${runId}?token=${token}`;

      console.log('[useBacktestProgress] Connecting to WebSocket:', wsUrl);
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log('[useBacktestProgress] WebSocket connected');
        setState((prev) => ({ ...prev, isConnected: true, error: null }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('[useBacktestProgress] Received message:', data);

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
        console.log('[useBacktestProgress] WebSocket disconnected');
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
