/**
 * API client for dYdX Backtest system
 */

import axios, { AxiosError, AxiosInstance } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8888';

// Type-safe error message extractor
const getErrorMessage = (error: unknown): string => {
  if (error instanceof AxiosError) {
    return error.response?.data?.message || error.message || 'Unknown error';
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
};

interface ApiResponse<T extends Record<string, unknown> | Token = Record<string, unknown>> {
  success: boolean;
  message: string;
  data?: T;
  timestamp: string;
}

interface Token extends Record<string, unknown> {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  expires_in: number;
}

interface LoginRequest {
  username: string;
  password: string;
}

interface RegisterRequest {
  username: string;
  email: string;
  password: string;
}

interface UserProfile extends Record<string, unknown> {
  id: number;
  username: string;
  email: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
  avatar?: string;
  full_name?: string;
}

interface BacktestRequest extends Record<string, unknown> {
  start_date: string;
  end_date: string;
  name?: string;
  description?: string;
  initial_balance?: number;
  max_pairs?: number;
  pairs?: string[];
  strategy_id?: number;
  trading_parameters?: Record<string, unknown>;
}

interface StrategyRequest extends Record<string, unknown> {
  name: string;
  description?: string;
  zscore_threshold?: number;
  max_half_life?: number;
}

interface SettingsUpdate extends Record<string, unknown> {
  // Settings properties
  [key: string]: unknown;
}

interface DYDXKey extends Record<string, unknown> {
  id?: number;
  network: string;
  chain_address: string;
  encrypted_secret?: string;
  is_active?: boolean;
  created_at?: string;
  updated_at?: string;
  [key: string]: unknown;
}

interface CreateKeyRequest extends Record<string, unknown> {
  network: string;
  chain_address: string;
  secret_phrase: string;
}

interface BacktestListItem extends Record<string, unknown> {
  id?: string;
  run_id: string;
  status: string;
  created_at: string;
  start_date?: string;
  end_date?: string;
  total_trades?: number;
  profitable_trades?: number;
  losing_trades?: number;
  total_pnl?: number;
  total_pnl_usd?: number;
  win_rate?: number;
  sharpe_ratio?: number;
  profit_factor?: number;
  max_drawdown?: number;
}

interface BacktestListResponse extends Record<string, unknown> {
  backtests: BacktestListItem[];
  total: number;
}

interface BacktestTradeResponse extends Record<string, unknown> {
  trades: Record<string, unknown>[];
  total: number;
}

interface BacktestSummaryResponse extends Record<string, unknown> {
  run_id: string;
  status: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  total_trades: number;
  earliest_trade_date?: string;
  latest_trade_date?: string;
  configuration: {
    num_pairs: number;
    zscore_threshold: number;
    stats_window: number;
    usd_per_trade: number;
  };
}

interface BacktestPerformanceResponse extends Record<string, unknown> {
  run_id: string;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_pnl: number;
  average_pnl: number;
  max_win: number;
  max_loss: number;
  sharpe_ratio: number;
  max_drawdown: number;
  average_duration: number;
}

interface BacktestDetailsResponse extends Record<string, unknown> {
  run_id: string;
  status: string;
  created_at?: string;
  start_date?: string;
  end_date?: string;
  duration_seconds?: number;
  total_trades?: number;
  profitable_trades?: number;
  total_pnl?: number;
  total_pnl_usd?: number;
  win_rate?: number;
  sharpe_ratio?: number;
  max_drawdown?: number;
  profit_factor?: number;
  starting_balance?: number;
  ending_balance?: number;
  strategy_snapshot?: Record<string, unknown>;
  strategy_id?: number;
  results?: Record<string, unknown>[];
  all_trades?: Record<string, unknown>[];
}

interface StrategyResponse extends Record<string, unknown> {
  id: number;
  name: string;
  category?: string;
  description?: string;
  zscore_threshold?: number;
  stats_window?: number;
  max_half_life?: number;
  usd_per_trade?: number;
  usd_min_collateral?: number;
  close_at_zscore_cross?: boolean;
  find_cointegrated_pairs?: boolean;
  manage_exits?: boolean;
  place_trades?: boolean;
  abort_all_positions?: boolean;
  max_positions?: number;
  max_drawdown_pct?: number;
  stop_loss_pct?: number;
  take_profit_pct?: number;
  trailing_stop_pct?: number;
  rebalance_interval_hours?: number;
  position_timeout_hours?: number;
  is_public?: boolean;
  created_at?: string;
  updated_at?: string;
}

interface StrategyListResponse extends Record<string, unknown> {
  strategies: StrategyResponse[];
  total: number;
}

interface StrategyVersionResponse extends Record<string, unknown> {
  id: number;
  version_number: number;
  name: string;
  description?: string;
  config: Record<string, unknown>;
  changed_fields: string[];
  change_reason?: string;
  created_at: string;
  created_by_user_id?: number;
}

interface StrategyVersionHistoryResponse extends Record<string, unknown> {
  versions: StrategyVersionResponse[];
}

interface RedisStatusResponse extends Record<string, unknown> {
  settings: Record<string, unknown> | null;
  connection: Record<string, unknown> | null;
  cache_stats: Record<string, unknown> | null;
}

interface UpdateProfileResponse extends Record<string, unknown> {
  user: UserProfile;
}

type PendingRequest = {
  resolve: (_token: string) => void;
  reject: (_error: unknown) => void;
};

class ApiClient {
  private client: AxiosInstance;
  private accessToken: string | null = null;
  private isRefreshing: boolean = false;
  private pendingRequests: PendingRequest[] = [];

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      withCredentials: true,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Load token from localStorage/cookie
    this.loadToken();

    // Request interceptor to add an auth token
    this.client.interceptors.request.use((config) => {
      // Prefer in-memory accessToken, but fall back to storage (localStorage or cookie)
      const token = this.accessToken || this.getTokenFromStorage();
      if (token) {
        // Ensure the headers object exists
        if (config.headers) {
          config.headers.Authorization = `Bearer ${token}`;
        }
      } else {
        console.warn('⚠️ NO TOKEN - Request to', config.url, 'will fail if auth is required');
      }
      return config;
    });

    // Response interceptor for error handling with refresh-token support
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        // Log all errors for debugging
        const url = error.config?.url || '';
        const status = error.response?.status;
        console.warn('🚨 API Error:', { url, status, message: error.message });

        // Handle 401 Unauthorized - attempt silent refresh
        if (
          status === 401 &&
          url &&
          !url.includes('/auth/login') &&
          !url.includes('/auth/refresh')
        ) {
          const originalRequest = error.config as
            | (typeof error.config & { _retry?: boolean })
            | undefined;
          if (originalRequest?._retry) {
            return Promise.reject(error);
          }

          console.warn('⏳ 401 Unauthorized detected, attempting silent refresh...');

          // If already refreshing, queue this request to retry after refresh completes
          if (this.isRefreshing) {
            return new Promise((resolve, reject) => {
              this.pendingRequests.push({
                resolve: (newToken: string) => {
                  if (error.config && error.config.headers) {
                    error.config.headers.Authorization = `Bearer ${newToken}`;
                    resolve(this.client(error.config));
                    return;
                  }
                  reject(new Error('Failed to retry request after token refresh'));
                },
                reject,
              });
            });
          }

          // Mark as refreshing and attempt to get new token
          this.isRefreshing = true;
          try {
            if (originalRequest) {
              originalRequest._retry = true;
            }

            const refreshPayload = await this.refreshAccessToken();
            const newAccessToken = refreshPayload.access_token;
            if (!newAccessToken) {
              throw new Error('Refresh endpoint did not return new access_token');
            }

            this.notifyRefreshSuccess(newAccessToken);

            // Retry original request with new token
            if (error.config && error.config.headers) {
              error.config.headers.Authorization = `Bearer ${newAccessToken}`;
              return this.client(error.config);
            }
          } catch (refreshError: unknown) {
            // Refresh failed - session truly invalid
            const errorMsg =
              refreshError instanceof Error ? refreshError.message : String(refreshError);
            console.error('❌ api.ts: Token refresh failed', errorMsg);
            this.notifyRefreshFailure(refreshError);
            this.logout();
            if (typeof window !== 'undefined') {
              window.dispatchEvent(
                new CustomEvent('auth:session-expired', {
                  detail: { reason: errorMsg },
                })
              );
            }
            return Promise.reject(refreshError);
          } finally {
            this.isRefreshing = false;
          }
        }

        // DO NOT auto-logout on OTHER errors here
        // Let components handle their own errors and decide what to do
        // Only logout should happen via explicit user action or auth page

        return Promise.reject(error);
      }
    );
  }

  private notifyRefreshSuccess(token: string): void {
    this.pendingRequests.forEach((request) => request.resolve(token));
    this.pendingRequests = [];
  }

  private notifyRefreshFailure(error: unknown): void {
    this.pendingRequests.forEach((request) => request.reject(error));
    this.pendingRequests = [];
  }

  private loadToken(): void {
    const token = localStorage.getItem('access_token');
    if (token) {
      this.accessToken = token;
      return;
    }

    // Fallback to cookie (non-HttpOnly); useful for some cross-tab setups
    const cookieToken = this.getTokenFromCookie();
    if (cookieToken) {
      this.accessToken = cookieToken;
      return;
    }

    console.warn('⚠️ No token in localStorage or cookie');
  }

  private getTokenFromCookie(): string | null {
    try {
      const match = document.cookie.match(/(^|; )access_token=([^;]+)/);
      return match ? decodeURIComponent(match[2]) : null;
    } catch (e) {
      console.warn('❌ api.ts: error reading cookie for token', e);
      return null;
    }
  }

  private getTokenFromStorage(): string | null {
    const token = localStorage.getItem('access_token');
    if (token) return token;
    return this.getTokenFromCookie();
  }

  // Allow callers to set token; optional remember flag to persist longer (not used right now)
  setToken(token: string, remember: boolean = true): void {
    this.accessToken = token;
    try {
      // Store in localStorage for fast access
      localStorage.setItem('access_token', token);

      // Also set a non-HttpOnly cookie for cross-tab compatibility (expires in 7 days)
      const maxAge = remember ? 7 * 24 * 60 * 60 : undefined; // seconds
      if (typeof document !== 'undefined') {
        let cookieStr = `access_token=${encodeURIComponent(token)}; path=/`;
        if (maxAge) cookieStr += `; max-age=${maxAge}`;
        // Set SameSite lax for decent CSRF protection; secure only on https
        cookieStr += `; samesite=lax`;
        if (window.location.protocol === 'https:') cookieStr += `; secure`;
        document.cookie = cookieStr;
      }
    } catch (e) {
      console.error('❌ api.ts: Failed to persist token:', e);
    }
  }

  async refreshAccessToken(): Promise<Token> {
    const refreshToken = localStorage.getItem('refresh_token');
    const requestBody = refreshToken ? { refresh_token: refreshToken } : {};

    const refreshResponse = await axios.post<ApiResponse<Token> | Token>(
      `${API_BASE_URL}/api/v1/auth/refresh`,
      requestBody,
      {
        withCredentials: true,
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );

    const refreshPayload = (refreshResponse.data as ApiResponse<Token>)?.data
      ? (refreshResponse.data as ApiResponse<Token>).data
      : (refreshResponse.data as Token);

    if (!refreshPayload?.access_token) {
      throw new Error('Refresh endpoint did not return new access token');
    }

    this.setToken(refreshPayload.access_token);
    if (refreshPayload.refresh_token) {
      localStorage.setItem('refresh_token', refreshPayload.refresh_token);
    }

    return refreshPayload;
  }

  hasRefreshToken(): boolean {
    return !!localStorage.getItem('refresh_token');
  }

  async restoreSession(): Promise<boolean> {
    this.ensureTokenLoaded();

    const hasAccessToken = this.hasToken();
    const hasRefreshToken = this.hasRefreshToken();

    if (!hasAccessToken && !hasRefreshToken) {
      return false;
    }

    if (!hasAccessToken && hasRefreshToken) {
      await this.refreshAccessToken();
    }

    return this.hasToken();
  }

  // Helper: Check if token is present
  hasToken(): boolean {
    const hasToken = !!(this.accessToken || this.getTokenFromStorage());
    return hasToken;
  }

  // Helper: Ensure token is loaded from localStorage
  ensureTokenLoaded(): void {
    if (!this.accessToken) {
      this.loadToken();
    }
  }

  logout(): void {
    this.accessToken = null;
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    // Remove cookie
    try {
      if (typeof document !== 'undefined') {
        document.cookie = 'access_token=; path=/; max-age=0';
        document.cookie = 'refresh_token=; path=/; max-age=0';
      }
    } catch (e) {
      console.warn('❌ api.ts: failed to remove cookie', e);
    }
  }

  // Auth endpoints
  async register(data: RegisterRequest): Promise<ApiResponse> {
    const response = await this.client.post<ApiResponse>('/api/v1/auth/register', data);
    return response.data;
  }

  async login(data: LoginRequest): Promise<Token> {
    try {
      // Backend wraps responses in { success, message, data: { ... } }
      const response = await this.client.post<ApiResponse<Token>>('/api/v1/auth/login', data);

      // Extract token payload from nested data when present
      const payload = (response.data?.data || response.data) as Token;

      if (payload && payload.access_token) {
        // Use setToken so we persist in both localStorage and cookie
        this.setToken(payload.access_token);
        if (payload.refresh_token) {
          try {
            localStorage.setItem('refresh_token', payload.refresh_token);
          } catch (e) {
            console.warn('❌ api.ts: Could not save refresh_token to localStorage', e);
          }
        }
      } else {
        console.warn('❌ api.ts: login did not return access_token in expected place', payload);
      }

      return payload as Token;
    } catch (error: unknown) {
      const errorMsg =
        error instanceof AxiosError
          ? error.response?.data?.message || error.message
          : String(error);
      console.error('❌ api.ts: login failed:', errorMsg);
      throw error;
    }
  }

  async getCurrentUser(): Promise<ApiResponse<UserProfile>> {
    const response = await this.client.get<ApiResponse<UserProfile>>('/api/v1/users/me');
    return response.data;
  }

  async updateProfile(data: Partial<UserProfile>): Promise<ApiResponse<UpdateProfileResponse>> {
    const response = await this.client.put<ApiResponse<UpdateProfileResponse>>(
      '/api/v1/profile',
      data
    );
    return response.data;
  }

  // 2FA (TOTP) endpoints
  async setup2FA(): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.post<ApiResponse>('/api/v1/auth/2fa/setup', {});
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async verify2FA(token: string): Promise<ApiResponse> {
    try {
      const response = await this.client.post<ApiResponse>('/api/v1/auth/2fa/verify', { token });
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  // Backtest endpoints
  async listBacktests(
    skip: number = 0,
    limit: number = 50
  ): Promise<ApiResponse<BacktestListResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse<BacktestListResponse>>(
      `/api/v1/backtests?skip=${skip}&limit=${limit}`
    );
    return response.data;
  }

  async getBacktest(runId: string): Promise<ApiResponse<BacktestDetailsResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse<BacktestDetailsResponse>>(
      `/api/v1/backtests/${runId}`
    );
    return response.data;
  }

  async runBacktest(data: BacktestRequest): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.post('/api/v1/backtests/run', data);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async getStats(): Promise<ApiResponse> {
    const response = await this.client.get<ApiResponse>('/api/v1/stats');
    return response.data;
  }

  async getBacktestLogs(
    runId: string
  ): Promise<
    ApiResponse<{ logs: Array<{ id: number; message: string; level: string; created_at: string }> }>
  > {
    // Ensure token is loaded before making the request
    this.ensureTokenLoaded();
    const response = await this.client.get<
      ApiResponse<{
        logs: Array<{ id: number; message: string; level: string; created_at: string }>;
      }>
    >(`/api/v1/backtests/${runId}/logs`);
    return response.data;
  }

  // Settings endpoints
  async getSettingsSchema(): Promise<ApiResponse> {
    const response = await this.client.get<ApiResponse>('/api/v1/settings/schema');
    return response.data;
  }

  async getSettings(section?: string): Promise<ApiResponse> {
    const url = section ? `/api/v1/settings?section=${section}` : '/api/v1/settings';
    const response = await this.client.get<ApiResponse>(url);
    return response.data;
  }

  async updateSettings(updates: SettingsUpdate): Promise<ApiResponse> {
    const response = await this.client.post<ApiResponse>('/api/v1/settings', updates);
    return response.data;
  }

  async initializeSettings(): Promise<ApiResponse> {
    const response = await this.client.post<ApiResponse>('/api/v1/settings/initialize', {});
    return response.data;
  }

  async getBacktestPerformance(runId: string): Promise<ApiResponse<BacktestPerformanceResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse<BacktestPerformanceResponse>>(
      `/api/v1/backtests/${runId}/performance`
    );
    return response.data;
  }

  async getBacktestTrades(
    runId: string,
    limit: number = 100,
    offset: number = 0
  ): Promise<ApiResponse<BacktestTradeResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse<BacktestTradeResponse>>(
      `/api/v1/backtests/${runId}/trades?limit=${limit}&offset=${offset}`
    );
    return response.data;
  }

  async getBacktestTrade(runId: string, tradeId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse>(
      `/api/v1/backtests/${runId}/trades/${tradeId}`
    );
    return response.data;
  }

  async getBacktestSummary(runId: string): Promise<ApiResponse<BacktestSummaryResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse<BacktestSummaryResponse>>(
      `/api/v1/backtests/${runId}/summary`
    );
    return response.data;
  }

  async getBacktestResults(
    runId: string,
    limit: number = 20,
    offset: number = 0,
    sortBy: string = 'pnl',
    sortOrder: string = 'desc',
    minWinRate?: number,
    minTrades?: number
  ): Promise<ApiResponse> {
    this.ensureTokenLoaded();

    let url = `/api/v1/backtests/${runId}/results?`;
    url += `limit=${limit}&offset=${offset}`;
    url += `&sort_by=${sortBy}&sort_order=${sortOrder}`;

    if (minWinRate !== undefined) {
      url += `&min_win_rate=${minWinRate}`;
    }
    if (minTrades !== undefined) {
      url += `&min_trades=${minTrades}`;
    }

    const response = await this.client.get<ApiResponse>(url);
    return response.data;
  }

  // Strategy endpoints
  async createStrategy(data: StrategyRequest): Promise<ApiResponse<StrategyResponse>> {
    try {
      const response = await this.client.post<ApiResponse<StrategyResponse>>(
        '/api/v1/strategies',
        data
      );
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async listStrategies(
    skip: number = 0,
    limit: number = 50
  ): Promise<ApiResponse<StrategyListResponse>> {
    const response = await this.client.get<ApiResponse<StrategyListResponse>>(
      `/api/v1/strategies?skip=${skip}&limit=${limit}`
    );
    return response.data;
  }

  async getStrategy(strategyId: number): Promise<ApiResponse<StrategyResponse>> {
    const response = await this.client.get<ApiResponse<StrategyResponse>>(
      `/api/v1/strategies/${strategyId}`
    );
    return response.data;
  }

  async updateStrategy(
    strategyId: number,
    data: StrategyRequest
  ): Promise<ApiResponse<StrategyResponse>> {
    try {
      const response = await this.client.put<ApiResponse<StrategyResponse>>(
        `/api/v1/strategies/${strategyId}`,
        data
      );
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async deleteStrategy(strategyId: number): Promise<ApiResponse> {
    try {
      const response = await this.client.delete<ApiResponse>(`/api/v1/strategies/${strategyId}`);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async getPublicStrategies(): Promise<ApiResponse> {
    const response = await this.client.get<ApiResponse>('/api/v1/strategies/public');
    return response.data;
  }

  // Strategy version control
  async getStrategyVersionHistory(
    strategyId: number
  ): Promise<ApiResponse<StrategyVersionHistoryResponse>> {
    try {
      const response = await this.client.get<ApiResponse<StrategyVersionHistoryResponse>>(
        `/api/v1/strategies/${strategyId}/versions`
      );
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async revertStrategyToVersion(strategyId: number, versionId: number): Promise<ApiResponse> {
    try {
      const response = await this.client.post<ApiResponse>(
        `/api/v1/strategies/${strategyId}/versions/${versionId}/revert`
      );
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async createStrategyFromBacktest(data: {
    name: string;
    description: string;
    config: Record<string, unknown>;
    backtest_run_id: string;
  }): Promise<ApiResponse> {
    try {
      const response = await this.client.post<ApiResponse>(
        `/api/v1/backtests/${data.backtest_run_id}/create-strategy`,
        {
          name: data.name,
          description: data.description,
          config: data.config,
        }
      );
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  // Backtest detailed data (candles, positions, trades)
  async getBacktestCandles(
    runId: string,
    market?: string,
    startDate?: string,
    endDate?: string
  ): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    const params = new URLSearchParams();
    if (market) params.append('market', market);
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);

    const url = `/api/v1/backtests/${runId}/candles${params.toString() ? `?${params}` : ''}`;
    const response = await this.client.get<ApiResponse>(url);
    return response.data;
  }

  async getBacktestPositions(
    runId: string,
    status?: string,
    market1?: string,
    market2?: string
  ): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (market1) params.append('market_1', market1);
    if (market2) params.append('market_2', market2);

    const url = `/api/v1/backtests/${runId}/positions${params.toString() ? `?${params}` : ''}`;
    const response = await this.client.get<ApiResponse>(url);
    return response.data;
  }

  async getBacktestTradesDetailed(
    runId: string,
    market1?: string,
    market2?: string,
    skip: number = 0,
    limit: number = 50
  ): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    const params = new URLSearchParams();
    if (market1) params.append('market_1', market1);
    if (market2) params.append('market_2', market2);
    params.append('skip', skip.toString());
    params.append('limit', limit.toString());

    const url = `/api/v1/backtests/${runId}/trades?${params}`;
    const response = await this.client.get<ApiResponse>(url);
    return response.data;
  }

  async getBacktestAnalytics(runId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse>(`/api/v1/backtests/${runId}/analytics`);
    return response.data;
  }

  async getBacktestPositionSnapshots(
    runId: string,
    limit: number = 100,
    offset: number = 0,
    marketPair?: string
  ): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    const params = new URLSearchParams();
    params.append('limit', limit.toString());
    params.append('offset', offset.toString());
    if (marketPair) params.append('market_pair', marketPair);

    const response = await this.client.get<ApiResponse>(
      `/api/v1/backtests/${runId}/position-snapshots?${params}`
    );
    return response.data;
  }

  // Bot Instance Management (delegated from Python bot API to backend)
  async createBotInstance(data: {
    instance_id: string;
    credentials: {
      chain_id: string;
      address: string;
      mnemonic: string;
    };
    trading_params: {
      is_testnet: boolean;
      zscore_threshold?: number;
      max_half_life?: number;
      usd_per_trade?: number;
    };
  }): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.post<ApiResponse>('/api/v1/bots', data);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async listBotInstances(skip: number = 0, limit: number = 50): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.get<ApiResponse>(
        `/api/v1/bots?skip=${skip}&limit=${limit}`
      );
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async getBotInstance(instanceId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.get<ApiResponse>(`/api/v1/bots/${instanceId}`);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async startBotInstance(instanceId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.post<ApiResponse>(`/api/v1/bots/${instanceId}/start`, {});
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async stopBotInstance(instanceId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.post<ApiResponse>(`/api/v1/bots/${instanceId}/stop`, {});
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async restartBotInstance(instanceId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.post<ApiResponse>(
        `/api/v1/bots/${instanceId}/restart`,
        {}
      );
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async deleteBotInstance(instanceId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.delete<ApiResponse>(`/api/v1/bots/${instanceId}`);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  // Bot Positions & Trading
  async getBotCurrentPositions(instanceId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.get<ApiResponse>(
        `/api/v1/bots/${instanceId}/positions/current`
      );
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async getBotPositionDetails(instanceId: string, positionId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.get<ApiResponse>(
        `/api/v1/bots/${instanceId}/positions/${positionId}`
      );
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async getBotPositionHistory(instanceId: string, positionId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.get<ApiResponse>(
        `/api/v1/bots/${instanceId}/position-history/${positionId}`
      );
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async getBotTrades(
    instanceId: string,
    skip: number = 0,
    limit: number = 50
  ): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.get<ApiResponse>(
        `/api/v1/bots/${instanceId}/trades?skip=${skip}&limit=${limit}`
      );
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  // Bot Statistics & Analytics
  async getBotStats(instanceId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.get<ApiResponse>(`/api/v1/bots/${instanceId}/stats`);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async getBotRealtimeStats(instanceId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.get<ApiResponse>(
        `/api/v1/bots/${instanceId}/realtime-stats`
      );
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async getBotHistory(
    instanceId: string,
    skip: number = 0,
    limit: number = 100
  ): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.get<ApiResponse>(
        `/api/v1/bots/${instanceId}/history?skip=${skip}&limit=${limit}`
      );
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async getBotJobs(instanceId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.get<ApiResponse>(`/api/v1/bots/${instanceId}/jobs`);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async getBotMarketData(instanceId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.get<ApiResponse>(`/api/v1/bots/${instanceId}/market-data`);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async getBotAlerts(
    instanceId: string,
    skip: number = 0,
    limit: number = 50
  ): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.get<ApiResponse>(
        `/api/v1/bots/${instanceId}/alerts?skip=${skip}&limit=${limit}`
      );
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  // Bot Configuration Updates
  async updateBotConfig(instanceId: string, config: Record<string, unknown>): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.put<ApiResponse>(
        `/api/v1/bots/${instanceId}/config`,
        config
      );
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  // WebSocket connection for real-time updates
  connectSocket(path: string, token?: string): WebSocket {
    // If token not supplied, try stored token
    const useToken = token || this.getTokenFromStorage() || '';

    // Build WebSocket URL from API_BASE_URL so it points to the backend configured in env
    try {
      const apiUrl = new URL(API_BASE_URL);
      const wsProtocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:';
      const backendHost = apiUrl.host; // e.g. localhost:8888
      // Ensure path starts with '/'
      const normalizedPath = path.startsWith('/') ? path : `/${path}`;
      const wsUrl = `${wsProtocol}//${backendHost}${normalizedPath}${useToken ? `?token=${encodeURIComponent(useToken)}` : ''}`;
      return new WebSocket(wsUrl);
    } catch (e) {
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const normalizedPath = path.startsWith('/') ? path : `/${path}`;
      const wsUrl = `${wsProtocol}//${window.location.host}${normalizedPath}${useToken ? `?token=${encodeURIComponent(useToken)}` : ''}`;
      console.warn(
        '⚠️ api.ts: Failed to parse API_BASE_URL, falling back to window.location.host for WS',
        e
      );
      return new WebSocket(wsUrl);
    }
  }

  // Backwards-compatible helper specifically for backtest progress
  connectBacktestSocket(runId: string, token?: string): WebSocket {
    return this.connectSocket(`/ws/backtest/${runId}`, token);
  }

  // Keys Management (centralized from DYDXKeyManager.tsx)
  async getKeys(): Promise<ApiResponse<{ keys: DYDXKey[]; total: number }>> {
    this.ensureTokenLoaded();
    const response =
      await this.client.get<ApiResponse<{ keys: DYDXKey[]; total: number }>>('/api/v1/keys/list');
    return response.data;
  }

  async createKey(data: CreateKeyRequest): Promise<ApiResponse<DYDXKey>> {
    this.ensureTokenLoaded();
    const response = await this.client.post<ApiResponse<DYDXKey>>('/api/v1/keys/create', data);
    return response.data;
  }

  async deleteKey(network: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    const response = await this.client.delete(`/api/v1/keys/${network}`);
    return response.data;
  }

  // Redis Settings (centralized from RedisSettings.tsx)
  async getRedisStatus(): Promise<ApiResponse<RedisStatusResponse>> {
    this.ensureTokenLoaded();
    const response =
      await this.client.get<ApiResponse<RedisStatusResponse>>('/api/v1/redis/status');
    return response.data;
  }

  async testRedisConnection(): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response = await this.client.post<ApiResponse<Record<string, unknown>>>(
      '/api/v1/redis/test-connection',
      {}
    );
    return response.data;
  }

  async toggleRedis(enabled: boolean): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response = await this.client.post<ApiResponse<Record<string, unknown>>>(
      '/api/v1/redis/toggle',
      { enabled }
    );
    return response.data;
  }

  async flushRedis(): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    const response = await this.client.post<ApiResponse>('/api/v1/redis/flush', {});
    return response.data;
  }

  async getRedisSettings(): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response =
      await this.client.get<ApiResponse<Record<string, unknown>>>('/api/v1/redis/settings');
    return response.data;
  }
}

export default new ApiClient();
