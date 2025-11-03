// Frontend API Client for dYdX Trading Bot Backend
// This provides a complete TypeScript client for the React frontend to interact with all backend APIs

import axios, { AxiosError, AxiosInstance } from 'axios';

// API Response Types
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  expires_in: number;
}

export interface User {
  id: string;
  username: string;
  email: string;
  profile?: {
    first_name?: string;
    last_name?: string;
  };
  created_at: string;
}

// Bot Instance Types
export interface BotInstance {
  instance_id: string;
  name: string;
  status: 'RUNNING' | 'STOPPED' | 'ERROR' | 'CREATED';
  credentials: {
    address: string;
  };
  trading_params: {
    is_testnet: boolean;
    zscore_threshold: number;
    max_half_life: number;
    usd_per_trade: number;
  };
  stats?: BotStats;
  last_heartbeat?: string;
  uptime_seconds?: number;
  total_trades?: number;
  win_rate?: number;
  pnl?: number;
  created_at: string;
}

export interface BotStats {
  total_trades: number;
  win_rate: number;
  total_pnl: number;
  daily_pnl: number;
  open_positions: number;
  daily_volume: number;
  uptime_seconds: number;
  average_trade_duration_minutes: number;
  sharpe_ratio: number;
  sortino_ratio: number;
}

export interface BotTrade {
  trade_id: string;
  market_1: string;
  market_2: string;
  side_1: 'BUY' | 'SELL';
  side_2: 'BUY' | 'SELL';
  size_1: number;
  size_2: number;
  status: 'FILLED' | 'PENDING' | 'CANCELLED';
  entry_z_score: number;
  exit_z_score?: number;
  pnl?: number;
  pnl_percent?: number;
  entry_time: string;
  exit_time?: string;
  duration_minutes?: number;
}

export interface BotPosition {
  position_id: string;
  market_1: string;
  market_2: string;
  side_1: 'BUY' | 'SELL';
  side_2: 'BUY' | 'SELL';
  size_1: number;
  size_2: number;
  entry_price_1: number;
  entry_price_2: number;
  current_price_1: number;
  current_price_2: number;
  unrealized_pnl: number;
  unrealized_pnl_percent: number;
  entry_time: string;
  current_z_score: number;
  mark_price_1: number;
  mark_price_2: number;
  status: 'LIVE' | 'CLOSED' | 'ERROR';
}

export interface BotAlert {
  alert_id: string;
  severity: 'ERROR' | 'WARNING' | 'INFO';
  message: string;
  timestamp: string;
  acknowledged: boolean;
}

export interface BotRealtimeStats {
  uptime_seconds: number;
  total_trades: number;
  trades_today: number;
  open_positions: number;
  total_pnl: number;
  daily_pnl: number;
  pnl_percent: number;
  win_rate: number;
  average_trade_duration_minutes: number;
  last_trade_time?: string;
  last_error?: string;
  last_error_time?: string;
  api_latency_ms: number;
  db_latency_ms: number;
}

// Backtest Types
export interface BacktestConfig {
  name: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  strategy: string;
  pairs: Array<{
    base_market: string;
    quote_market: string;
    hedge_ratio: number;
    half_life: number;
  }>;
  trading_params: {
    zscore_threshold: number;
    usd_per_trade: number;
    max_half_life: number;
    slippage_percent: number;
  };
}

export interface Backtest {
  run_id: string;
  name: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
  start_date: string;
  end_date: string;
  total_pnl: number;
  total_pnl_percent: number;
  total_trades: number;
  win_rate: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown_percent: number;
  calmar_ratio: number;
  created_at: string;
  completed_at?: string;
}

export interface BacktestProgress {
  run_id: string;
  status: string;
  progress_percent: number;
  trades_completed: number;
  trades_total: number;
  current_date: string;
  estimated_completion_seconds: number;
}

export interface BacktestMetrics {
  total_return: number;
  annualized_return: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  max_drawdown: number;
  max_drawdown_percent: number;
  win_rate: number;
  profit_factor: number;
  recovery_factor: number;
  trade_count: number;
  average_trade_pnl: number;
  average_winning_trade: number;
  average_losing_trade: number;
  consecutive_wins: number;
  consecutive_losses: number;
}

// System Types
export interface SystemStatus {
  status: 'operational' | 'degraded' | 'down';
  components: {
    database: 'healthy' | 'unhealthy';
    bot_api: 'healthy' | 'unhealthy';
    cache: 'healthy' | 'unhealthy';
    indexer: 'healthy' | 'unhealthy';
  };
  metrics: {
    active_bots: number;
    active_backtests: number;
    total_trades_24h: number;
    api_requests_1h: number;
    average_latency_ms: number;
  };
}

// Main API Client Class
export class DydxBotAPIClient {
  private apiClient: AxiosInstance;
  private baseURL: string;
  private token: string | null = null;
  private refreshToken: string | null = null;

  constructor(baseURL: string = 'http://localhost:8888') {
    this.baseURL = baseURL;
    
    this.apiClient = axios.create({
      baseURL: `${baseURL}/api/v1`,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add request interceptor to include auth token
    this.apiClient.interceptors.request.use(
      (config) => {
        if (this.token) {
          config.headers.Authorization = `Bearer ${this.token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Add response interceptor to handle token refresh
    this.apiClient.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config;

        // Handle 401 (Unauthorized) by attempting token refresh
        if (error.response?.status === 401 && !originalRequest?._retry) {
          (originalRequest as any)._retry = true;

          try {
            if (this.refreshToken) {
              await this.refreshAccessToken();
              return this.apiClient(originalRequest!);
            }
          } catch (refreshError) {
            // Refresh failed, logout user
            this.clearAuth();
            window.location.href = '/login';
            return Promise.reject(refreshError);
          }
        }

        return Promise.reject(error);
      }
    );
  }

  // ==================== Authentication ====================

  async register(username: string, password: string, email: string): Promise<User> {
    const response = await this.apiClient.post<ApiResponse<User>>('/auth/register', {
      username,
      password,
      email,
    });
    return response.data.data!;
  }

  async login(username: string, password: string): Promise<AuthResponse> {
    const response = await this.apiClient.post<ApiResponse<AuthResponse>>('/auth/login', {
      username,
      password,
    });

    const authData = response.data.data!;
    this.token = authData.access_token;
    this.refreshToken = authData.refresh_token;
    this.saveAuth();

    return authData;
  }

  async refreshAccessToken(): Promise<void> {
    if (!this.refreshToken) {
      throw new Error('No refresh token available');
    }

    const response = await this.apiClient.post<ApiResponse<AuthResponse>>('/auth/refresh', {
      refresh_token: this.refreshToken,
    });

    const authData = response.data.data!;
    this.token = authData.access_token;
    this.refreshToken = authData.refresh_token;
    this.saveAuth();
  }

  async getCurrentUser(): Promise<User> {
    const response = await this.apiClient.get<ApiResponse<User>>('/users/me');
    return response.data.data!;
  }

  async updateProfile(profile: Partial<User>): Promise<void> {
    await this.apiClient.put('/profile', profile);
  }

  setAuth(token: string, refreshToken: string): void {
    this.token = token;
    this.refreshToken = refreshToken;
    this.saveAuth();
  }

  private saveAuth(): void {
    localStorage.setItem('auth_token', this.token || '');
    localStorage.setItem('refresh_token', this.refreshToken || '');
  }

  private clearAuth(): void {
    this.token = null;
    this.refreshToken = null;
    localStorage.removeItem('auth_token');
    localStorage.removeItem('refresh_token');
  }

  loadAuthFromStorage(): boolean {
    const token = localStorage.getItem('auth_token');
    const refreshToken = localStorage.getItem('refresh_token');

    if (token && refreshToken) {
      this.token = token;
      this.refreshToken = refreshToken;
      return true;
    }
    return false;
  }

  // ==================== Bot Instance Management ====================

  async createBotInstance(config: {
    instance_id: string;
    name: string;
    credentials: { address: string; mnemonic: string };
    trading_params: any;
  }): Promise<BotInstance> {
    const response = await this.apiClient.post<ApiResponse<BotInstance>>('/bots', config);
    return response.data.data!;
  }

  async listBotInstances(
    status?: string,
    limit: number = 50,
    offset: number = 0
  ): Promise<{ count: number; data: BotInstance[] }> {
    const params: any = { limit, offset };
    if (status) params.status = status;

    const response = await this.apiClient.get<ApiResponse<any>>('/bots', { params });
    return response.data.data;
  }

  async getBotInstance(instanceId: string): Promise<BotInstance> {
    const response = await this.apiClient.get<ApiResponse<BotInstance>>(`/bots/${instanceId}`);
    return response.data.data!;
  }

  async startBotInstance(instanceId: string, strategy?: string, pairs?: string[]): Promise<any> {
    const response = await this.apiClient.post(`/bots/${instanceId}/start`, {
      strategy,
      pairs,
    });
    return response.data;
  }

  async stopBotInstance(instanceId: string): Promise<any> {
    const response = await this.apiClient.post(`/bots/${instanceId}/stop`);
    return response.data;
  }

  async restartBotInstance(instanceId: string): Promise<any> {
    const response = await this.apiClient.post(`/bots/${instanceId}/restart`);
    return response.data;
  }

  async deleteBotInstance(instanceId: string): Promise<void> {
    await this.apiClient.delete(`/bots/${instanceId}`);
  }

  async quickDeployBot(config: {
    instance_id: string;
    credentials: { address: string; mnemonic: string };
    pairs: string[];
    trading_params: any;
  }): Promise<BotInstance> {
    const response = await this.apiClient.post<ApiResponse<BotInstance>>('/bots/quick-deploy', config);
    return response.data.data!;
  }

  // ==================== Bot Statistics & History ====================

  async getBotStats(instanceId: string): Promise<BotStats> {
    const response = await this.apiClient.get<ApiResponse<BotStats>>(`/bots/${instanceId}/stats`);
    return response.data.data!;
  }

  async getBotTrades(
    instanceId: string,
    limit: number = 50,
    offset: number = 0,
    status?: string,
    startDate?: string,
    endDate?: string
  ): Promise<{ count: number; data: BotTrade[] }> {
    const params: any = { limit, offset };
    if (status) params.status = status;
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;

    const response = await this.apiClient.get<ApiResponse<any>>(`/bots/${instanceId}/trades`, { params });
    return response.data.data;
  }

  async getBotHistory(instanceId: string, days: number = 7, granularity: string = 'daily'): Promise<any[]> {
    const response = await this.apiClient.get<ApiResponse<any[]>>(`/bots/${instanceId}/history`, {
      params: { days, granularity },
    });
    return response.data.data!;
  }

  async getBotJobs(
    instanceId: string,
    limit: number = 50,
    offset: number = 0,
    type?: string
  ): Promise<{ count: number; data: any[] }> {
    const params: any = { limit, offset };
    if (type) params.type = type;

    const response = await this.apiClient.get<ApiResponse<any>>(`/bots/${instanceId}/jobs`, { params });
    return response.data.data;
  }

  // ==================== Real-Time Bot Data ====================

  async getCurrentPositions(instanceId: string): Promise<BotPosition[]> {
    const response = await this.apiClient.get<ApiResponse<any>>(`/bots/${instanceId}/positions/current`);
    return response.data.data;
  }

  async getPosition(instanceId: string, positionId: string): Promise<BotPosition> {
    const response = await this.apiClient.get<ApiResponse<BotPosition>>(
      `/bots/${instanceId}/positions/${positionId}`
    );
    return response.data.data!;
  }

  async getPositionHistory(instanceId: string, positionId: string, hours: number = 24): Promise<any[]> {
    const response = await this.apiClient.get<ApiResponse<any>>(
      `/bots/${instanceId}/position-history/${positionId}`,
      {
        params: { hours },
      }
    );
    return response.data.data;
  }

  async getMarketData(instanceId: string): Promise<Record<string, any>> {
    const response = await this.apiClient.get<ApiResponse<Record<string, any>>>(
      `/bots/${instanceId}/market-data`
    );
    return response.data.data!;
  }

  async getRealtimeStats(instanceId: string): Promise<BotRealtimeStats> {
    const response = await this.apiClient.get<ApiResponse<BotRealtimeStats>>(
      `/bots/${instanceId}/realtime-stats`
    );
    return response.data.data!;
  }

  async getAlerts(instanceId: string, limit: number = 50, severity?: string): Promise<{ count: number; data: BotAlert[] }> {
    const params: any = { limit };
    if (severity) params.severity = severity;

    const response = await this.apiClient.get<ApiResponse<any>>(`/bots/${instanceId}/alerts`, { params });
    return response.data.data;
  }

  // ==================== Backtest Management ====================

  async createBacktest(config: BacktestConfig): Promise<Backtest> {
    const response = await this.apiClient.post<ApiResponse<Backtest>>('/backtests', config);
    return response.data.data!;
  }

  async listBacktests(
    limit: number = 50,
    offset: number = 0,
    status?: string,
    days?: number
  ): Promise<{ count: number; data: Backtest[] }> {
    const params: any = { limit, offset };
    if (status) params.status = status;
    if (days) params.days = days;

    const response = await this.apiClient.get<ApiResponse<any>>('/backtests', { params });
    return response.data.data;
  }

  async getBacktest(runId: string): Promise<Backtest> {
    const response = await this.apiClient.get<ApiResponse<Backtest>>(`/backtests/${runId}`);
    return response.data.data!;
  }

  async getBacktestStatus(runId: string): Promise<BacktestProgress> {
    const response = await this.apiClient.get<ApiResponse<BacktestProgress>>(`/backtests/${runId}/status`);
    return response.data.data!;
  }

  async getBacktestTrades(runId: string, limit: number = 50, offset: number = 0): Promise<{ count: number; data: any[] }> {
    const response = await this.apiClient.get<ApiResponse<any>>(`/backtests/${runId}/trades`, {
      params: { limit, offset },
    });
    return response.data.data;
  }

  async getBacktestAnalytics(runId: string): Promise<any> {
    const response = await this.apiClient.get<ApiResponse<any>>(`/backtests/${runId}/analytics`);
    return response.data.data!;
  }

  async getBacktestMetrics(runId: string): Promise<BacktestMetrics> {
    const response = await this.apiClient.get<ApiResponse<BacktestMetrics>>(
      `/backtests/${runId}/performance-metrics`
    );
    return response.data.data!;
  }

  async compareBacktests(runIds: string[], metrics: string[]): Promise<any> {
    const response = await this.apiClient.post<ApiResponse<any>>('/backtests/compare', {
      run_ids: runIds,
      metrics,
    });
    return response.data.data!;
  }

  async cancelBacktest(runId: string): Promise<any> {
    const response = await this.apiClient.post(`/backtests/${runId}/cancel`);
    return response.data;
  }

  async getBacktestSummaryStats(days: number = 30): Promise<any> {
    const response = await this.apiClient.get<ApiResponse<any>>('/backtests/stats/summary', {
      params: { days },
    });
    return response.data.data!;
  }

  async getBacktestPositionSnapshots(runId: string): Promise<any[]> {
    const response = await this.apiClient.get<ApiResponse<any>>(`/backtests/${runId}/position-snapshots`);
    return response.data.data;
  }

  async getBacktestDydxValidation(runId: string): Promise<any> {
    const response = await this.apiClient.get<ApiResponse<any>>(`/backtests/${runId}/dydx-validation`);
    return response.data.data!;
  }

  async deleteBacktest(runId: string): Promise<void> {
    await this.apiClient.delete(`/backtests/${runId}`);
  }

  // ==================== WebSocket Connections ====================

  connectBacktestProgress(runId: string, onMessage: (progress: BacktestProgress) => void): WebSocket {
    const wsUrl = `ws://${this.baseURL.replace(/^https?:\/\//, '')}/api/v1/backtests/${runId}/live-progress`;
    const ws = new WebSocket(`${wsUrl}?token=${this.token}`);

    ws.onmessage = (event) => {
      try {
        const progress = JSON.parse(event.data);
        onMessage(progress);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    return ws;
  }

  connectBotUpdates(instanceId: string, onMessage: (update: any) => void): WebSocket {
    const wsUrl = `ws://${this.baseURL.replace(/^https?:\/\//, '')}/api/v1/bots/${instanceId}/updates`;
    const ws = new WebSocket(`${wsUrl}?token=${this.token}`);

    ws.onmessage = (event) => {
      try {
        const update = JSON.parse(event.data);
        onMessage(update);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    return ws;
  }

  // ==================== System Status ====================

  async getSystemStatus(): Promise<SystemStatus> {
    const response = await this.apiClient.get<ApiResponse<SystemStatus>>('/system/status');
    return response.data.data!;
  }

  async getHealth(): Promise<any> {
    // Note: No auth required for health endpoint
    const response = await axios.get(`${this.baseURL}/health`);
    return response.data;
  }
}

// Export singleton instance for use across the app
export const apiClient = new DydxBotAPIClient();
