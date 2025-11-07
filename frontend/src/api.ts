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
  pairs?: string[];
  zscore_threshold?: number;
  max_half_life?: number;
  usd_per_trade?: number;
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
  [key: string]: unknown;
}

class ApiClient {
  private client: AxiosInstance;
  private accessToken: string | null = null;
  private isRefreshing: boolean = false;
  private refreshSubscribers: ((token: string) => void)[] = [];

  constructor() {
    console.log('🔌 api.ts: ApiClient constructor, API_BASE_URL:', API_BASE_URL);
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Load token from localStorage/cookie
    this.loadToken();
    console.log('🔌 api.ts: Token loaded, present:', !!this.accessToken);

    // Request interceptor to add auth token
    this.client.interceptors.request.use((config) => {
      console.log('📤 Request to:', config.url);
      // Prefer in-memory accessToken, but fall back to storage (localStorage or cookie)
      const token = this.accessToken || this.getTokenFromStorage();
      if (token) {
        // Ensure headers object exists
        if (config.headers) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        console.log('✅ Authorization header added for request to:', config.url);
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
        if (status === 401 && url && !url.includes('/auth/login') && !url.includes('/auth/refresh')) {
          console.warn('⏳ 401 Unauthorized detected, attempting silent refresh...');

          // If already refreshing, queue this request to retry after refresh completes
          if (this.isRefreshing) {
            console.log('🔄 api.ts: Refresh already in progress, queuing request retry');
            return new Promise((resolve) => {
              this.refreshSubscribers.push((newToken: string) => {
                // Update auth header with new token
                if (error.config && error.config.headers) {
                  error.config.headers.Authorization = `Bearer ${newToken}`;
                  resolve(this.client(error.config));
                }
              });
            });
          }

          // Mark as refreshing and attempt to get new token
          this.isRefreshing = true;
          try {
            const refreshToken = localStorage.getItem('refresh_token');
            if (!refreshToken) {
              throw new Error('No refresh token available');
            }

            console.log('🔐 api.ts: Calling refresh endpoint...');
            // Attempt refresh using the refresh token (depends on backend implementation)
            // This assumes backend has POST /api/v1/auth/refresh endpoint which returns wrapper
            const refreshResponse = await axios.post<ApiResponse<Token>>(
              `${API_BASE_URL}/api/v1/auth/refresh`,
              { refresh_token: refreshToken }
            );

            const refreshPayload = (refreshResponse.data?.data || refreshResponse.data) as Token;
            const newAccessToken = refreshPayload?.access_token;
            if (!newAccessToken) {
              throw new Error('Refresh endpoint did not return new access_token');
            }

             console.log('✅ api.ts: Token refreshed successfully');
             this.setToken(newAccessToken);

             // Notify all queued requests of the new token
             this.refreshSubscribers.forEach((callback) => callback(newAccessToken));
             this.refreshSubscribers = [];

             // Retry original request with new token
             if (error.config && error.config.headers) {
               error.config.headers.Authorization = `Bearer ${newAccessToken}`;
               console.log('🔄 api.ts: Retrying original request with new token');
               return this.client(error.config);
             }
           } catch (refreshError: unknown) {
            // Refresh failed - session truly invalid
            const errorMsg = refreshError instanceof Error ? refreshError.message : String(refreshError);
            console.error('❌ api.ts: Token refresh failed, logging out', errorMsg);
            this.refreshSubscribers = [];
            this.logout();
            localStorage.setItem('auth_redirect', 'true');
            window.location.href = '/login';
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

  private loadToken(): void {
    const token = localStorage.getItem('access_token');
    if (token) {
      this.accessToken = token;
      console.log('✅ Token loaded from localStorage');
      return;
    }

    // Fallback to cookie (non-HttpOnly); useful for some cross-tab setups
    const cookieToken = this.getTokenFromCookie();
    if (cookieToken) {
      this.accessToken = cookieToken;
      console.log('✅ Token loaded from cookie');
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
      console.log('✅ Token set and saved to localStorage');

      // Also set a non-HttpOnly cookie for cross-tab compatibility (expires in 7 days)
      const maxAge = remember ? 7 * 24 * 60 * 60 : undefined; // seconds
      if (typeof document !== 'undefined') {
        let cookieStr = `access_token=${encodeURIComponent(token)}; path=/`;
        if (maxAge) cookieStr += `; max-age=${maxAge}`;
        // Set SameSite lax for decent CSRF protection; secure only on https
        cookieStr += `; samesite=lax`;
        if (window.location.protocol === 'https:') cookieStr += `; secure`;
        document.cookie = cookieStr;
        console.log('✅ Token saved in cookie for cross-tab usage');
      }
    } catch (e) {
      console.error('❌ api.ts: Failed to persist token:', e);
    }
  }

  // Helper: Check if token is present
  hasToken(): boolean {
    const hasToken = !!(this.accessToken || this.getTokenFromStorage());
    console.log('🔍 Token check:', { hasToken, tokenLength: (this.accessToken || this.getTokenFromStorage())?.length || 0 });
    return hasToken;
  }

  // Helper: Ensure token is loaded from localStorage
  ensureTokenLoaded(): void {
    if (!this.accessToken) {
      console.log('🔄 Token not in memory, reloading from localStorage/cookie');
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
        console.log('✅ access_token cookie removed');
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
    console.log('🔌 api.ts: login() called, making POST to /api/v1/auth/login');
    console.log('🔌 api.ts: baseURL:', API_BASE_URL);
    console.log('🔌 api.ts: request data:', data);
    try {
      // Backend wraps responses in { success, message, data: { ... } }
      const response = await this.client.post<ApiResponse<Token>>('/api/v1/auth/login', data);
      console.log('🔌 api.ts: login response:', response.data);

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
        console.log('🔌 api.ts: token saved to storage');
      } else {
        console.warn('❌ api.ts: login did not return access_token in expected place', payload);
      }

      return payload as Token;
    } catch (error: unknown) {
      const errorMsg = error instanceof AxiosError ? error.response?.data?.message || error.message : String(error);
      console.error('❌ api.ts: login failed:', errorMsg);
      throw error;
    }
  }

  async getCurrentUser(): Promise<ApiResponse<UserProfile>> {
    const response = await this.client.get('/api/v1/users/me');
    return response.data;
  }

  async updateProfile(data: Partial<UserProfile>): Promise<ApiResponse> {
    const response = await this.client.put<ApiResponse>('/api/v1/profile', data);
    return response.data;
  }

  // 2FA (TOTP) endpoints
  async setup2FA(): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    console.log('🔌 api.ts: setup2FA() called');
    try {
      const response = await this.client.post<ApiResponse>('/api/v1/auth/2fa/setup', {});
      console.log('✅ api.ts: setup2FA response:', response.data);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async verify2FA(token: string): Promise<ApiResponse> {
    console.log('🔌 api.ts: verify2FA() called');
    try {
      const response = await this.client.post<ApiResponse>('/api/v1/auth/2fa/verify', { token });
      console.log('✅ api.ts: verify2FA response:', response.data);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  // Backtest endpoints
  async listBacktests(skip: number = 0, limit: number = 50): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse>(
      `/api/v1/backtests?skip=${skip}&limit=${limit}`
    );
    return response.data;
  }

  async getBacktest(runId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse>(`/api/v1/backtests/${runId}`);
    return response.data;
  }

  async runBacktest(data: BacktestRequest): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    console.log('🔌 api.ts: runBacktest() called with:', JSON.stringify(data, null, 2));
    console.log('🔌 api.ts: current token:', this.accessToken ? `${this.accessToken.substring(0, 30)}...` : 'NONE');
    console.log('🔌 api.ts: token from localStorage:', localStorage.getItem('access_token') ? 'YES' : 'NO');
    try {
      const response = await this.client.post('/api/v1/backtests/run', data);
      console.log('✅ api.ts: runBacktest response received:', response.status, response.data);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async getStats(): Promise<ApiResponse> {
    const response = await this.client.get<ApiResponse>('/api/v1/stats');
    return response.data;
  }

  async getBacktestLogs(runId: string): Promise<ApiResponse> {
    // Ensure token is loaded before making the request
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse>(`/api/v1/backtests/${runId}/logs`);
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

  async getBacktestPerformance(runId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse>(
      `/api/v1/backtests/${runId}/performance`
    );
    return response.data;
  }

  async getBacktestTrades(runId: string, limit: number = 100, offset: number = 0): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse>(
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

  async getBacktestSummary(runId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse>(
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
  async createStrategy(data: StrategyRequest): Promise<ApiResponse> {
    console.log('🔌 api.ts: createStrategy() called with:', data);
    try {
      const response = await this.client.post<ApiResponse>('/api/v1/strategies', data);
      console.log('🔌 api.ts: createStrategy response:', response.data);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async listStrategies(skip: number = 0, limit: number = 50): Promise<ApiResponse> {
    const response = await this.client.get<ApiResponse>(
      `/api/v1/strategies?skip=${skip}&limit=${limit}`
    );
    return response.data;
  }

  async getStrategy(strategyId: number): Promise<ApiResponse> {
    const response = await this.client.get<ApiResponse>(`/api/v1/strategies/${strategyId}`);
    return response.data;
  }

  async updateStrategy(strategyId: number, data: StrategyRequest): Promise<ApiResponse> {
    console.log('🔌 api.ts: updateStrategy() called with:', data);
    try {
      const response = await this.client.put<ApiResponse>(`/api/v1/strategies/${strategyId}`, data);
      console.log('🔌 api.ts: updateStrategy response:', response.data);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async deleteStrategy(strategyId: number): Promise<ApiResponse> {
    console.log('🔌 api.ts: deleteStrategy() called for ID:', strategyId);
    try {
      const response = await this.client.delete<ApiResponse>(`/api/v1/strategies/${strategyId}`);
      console.log('🔌 api.ts: deleteStrategy response:', response.data);
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
  async getStrategyVersionHistory(strategyId: number): Promise<ApiResponse> {
    console.log('🔌 api.ts: getStrategyVersionHistory() called for strategy:', strategyId);
    try {
      const response = await this.client.get<ApiResponse>(
        `/api/v1/strategies/${strategyId}/versions`
      );
      console.log('🔌 api.ts: getStrategyVersionHistory response:', response.data);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async revertStrategyToVersion(strategyId: number, versionId: number): Promise<ApiResponse> {
    console.log('🔌 api.ts: revertStrategyToVersion() called for strategy:', strategyId, 'version:', versionId);
    try {
      const response = await this.client.post<ApiResponse>(
        `/api/v1/strategies/${strategyId}/versions/${versionId}/revert`
      );
      console.log('🔌 api.ts: revertStrategyToVersion response:', response.data);
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
    console.log('🔌 api.ts: createStrategyFromBacktest() called with:', data);
    try {
      const response = await this.client.post<ApiResponse>(
        `/api/v1/backtests/${data.backtest_run_id}/create-strategy`,
        {
          name: data.name,
          description: data.description,
          config: data.config,
        }
      );
      console.log('🔌 api.ts: createStrategyFromBacktest response:', response.data);
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
    console.log('🔌 api.ts: createBotInstance() called with:', data.instance_id);
    try {
      const response = await this.client.post<ApiResponse>('/api/v1/bots', data);
      console.log('✅ api.ts: createBotInstance response:', response.data);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async listBotInstances(skip: number = 0, limit: number = 50): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    console.log('🔌 api.ts: listBotInstances() called');
    try {
      const response = await this.client.get<ApiResponse>(`/api/v1/bots?skip=${skip}&limit=${limit}`);
      console.log('✅ api.ts: listBotInstances response:', response.data);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async getBotInstance(instanceId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    console.log('🔌 api.ts: getBotInstance() called for:', instanceId);
    try {
      const response = await this.client.get<ApiResponse>(`/api/v1/bots/${instanceId}`);
      console.log('✅ api.ts: getBotInstance response:', response.data);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async startBotInstance(instanceId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    console.log('🔌 api.ts: startBotInstance() called for:', instanceId);
    try {
      const response = await this.client.post<ApiResponse>(`/api/v1/bots/${instanceId}/start`, {});
      console.log('✅ api.ts: startBotInstance response:', response.data);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async stopBotInstance(instanceId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    console.log('🔌 api.ts: stopBotInstance() called for:', instanceId);
    try {
      const response = await this.client.post<ApiResponse>(`/api/v1/bots/${instanceId}/stop`, {});
      console.log('✅ api.ts: stopBotInstance response:', response.data);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async restartBotInstance(instanceId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    console.log('🔌 api.ts: restartBotInstance() called for:', instanceId);
    try {
      const response = await this.client.post<ApiResponse>(`/api/v1/bots/${instanceId}/restart`, {});
      console.log('✅ api.ts: restartBotInstance response:', response.data);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async deleteBotInstance(instanceId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    console.log('🔌 api.ts: deleteBotInstance() called for:', instanceId);
    try {
      const response = await this.client.delete<ApiResponse>(`/api/v1/bots/${instanceId}`);
      console.log('✅ api.ts: deleteBotInstance response:', response.data);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  // Bot Positions & Trading
  async getBotCurrentPositions(instanceId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    console.log('🔌 api.ts: getBotCurrentPositions() called for:', instanceId);
    try {
      const response = await this.client.get<ApiResponse>(`/api/v1/bots/${instanceId}/positions/current`);
      console.log('✅ api.ts: getBotCurrentPositions response:', response.data);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async getBotPositionDetails(instanceId: string, positionId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    console.log('🔌 api.ts: getBotPositionDetails() called for:', instanceId, 'position:', positionId);
    try {
      const response = await this.client.get<ApiResponse>(
        `/api/v1/bots/${instanceId}/positions/${positionId}`
      );
      console.log('✅ api.ts: getBotPositionDetails response:', response.data);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async getBotPositionHistory(instanceId: string, positionId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    console.log('🔌 api.ts: getBotPositionHistory() called for:', instanceId, 'position:', positionId);
    try {
      const response = await this.client.get<ApiResponse>(
        `/api/v1/bots/${instanceId}/position-history/${positionId}`
      );
      console.log('✅ api.ts: getBotPositionHistory response:', response.data);
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
    console.log('🔌 api.ts: getBotTrades() called for:', instanceId);
    try {
      const response = await this.client.get<ApiResponse>(
        `/api/v1/bots/${instanceId}/trades?skip=${skip}&limit=${limit}`
      );
      console.log('✅ api.ts: getBotTrades response:', response.data);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  // Bot Statistics & Analytics
  async getBotStats(instanceId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    console.log('🔌 api.ts: getBotStats() called for:', instanceId);
    try {
      const response = await this.client.get<ApiResponse>(`/api/v1/bots/${instanceId}/stats`);
      console.log('✅ api.ts: getBotStats response:', response.data);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async getBotRealtimeStats(instanceId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    console.log('🔌 api.ts: getBotRealtimeStats() called for:', instanceId);
    try {
      const response = await this.client.get<ApiResponse>(
        `/api/v1/bots/${instanceId}/realtime-stats`
      );
      console.log('✅ api.ts: getBotRealtimeStats response:', response.data);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async getBotHistory(instanceId: string, skip: number = 0, limit: number = 100): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    console.log('🔌 api.ts: getBotHistory() called for:', instanceId);
    try {
      const response = await this.client.get<ApiResponse>(
        `/api/v1/bots/${instanceId}/history?skip=${skip}&limit=${limit}`
      );
      console.log('✅ api.ts: getBotHistory response:', response.data);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async getBotJobs(instanceId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    console.log('🔌 api.ts: getBotJobs() called for:', instanceId);
    try {
      const response = await this.client.get<ApiResponse>(`/api/v1/bots/${instanceId}/jobs`);
      console.log('✅ api.ts: getBotJobs response:', response.data);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async getBotMarketData(instanceId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    console.log('🔌 api.ts: getBotMarketData() called for:', instanceId);
    try {
      const response = await this.client.get<ApiResponse>(
        `/api/v1/bots/${instanceId}/market-data`
      );
      console.log('✅ api.ts: getBotMarketData response:', response.data);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async getBotAlerts(instanceId: string, skip: number = 0, limit: number = 50): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    console.log('🔌 api.ts: getBotAlerts() called for:', instanceId);
    try {
      const response = await this.client.get<ApiResponse>(
        `/api/v1/bots/${instanceId}/alerts?skip=${skip}&limit=${limit}`
      );
      console.log('✅ api.ts: getBotAlerts response:', response.data);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  // Bot Configuration Updates
  async updateBotConfig(instanceId: string, config: Record<string, unknown>): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    console.log('🔌 api.ts: updateBotConfig() called for:', instanceId);
    try {
      const response = await this.client.put<ApiResponse>(`/api/v1/bots/${instanceId}/config`, config);
      console.log('✅ api.ts: updateBotConfig response:', response.data);
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
      console.log('🔌 api.ts: connectSocket ->', wsUrl);
      return new WebSocket(wsUrl);
    } catch (e) {
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const normalizedPath = path.startsWith('/') ? path : `/${path}`;
      const wsUrl = `${wsProtocol}//${window.location.host}${normalizedPath}${useToken ? `?token=${encodeURIComponent(useToken)}` : ''}`;
      console.warn('⚠️ api.ts: Failed to parse API_BASE_URL, falling back to window.location.host for WS', e);
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
    console.log('🔌 api.ts: getKeys() called');
    const response = await this.client.get('/api/v1/keys/list');
    return response.data;
  }

  async createKey(data: DYDXKey): Promise<ApiResponse<DYDXKey>> {
    this.ensureTokenLoaded();
    console.log('🔌 api.ts: createKey() called with:', data);
    const response = await this.client.post('/api/v1/keys/create', data);
    return response.data;
  }

  async deleteKey(network: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    console.log('🔌 api.ts: deleteKey() called for network:', network);
    const response = await this.client.delete(`/api/v1/keys/${network}`);
    return response.data;
  }

  // Redis Settings (centralized from RedisSettings.tsx)
  async getRedisStatus(): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    console.log('🔌 api.ts: getRedisStatus() called');
    const response = await this.client.get('/api/v1/redis/status');
    return response.data;
  }

  async testRedisConnection(): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    console.log('🔌 api.ts: testRedisConnection() called');
    const response = await this.client.post('/api/v1/redis/test-connection', {});
    return response.data;
  }

  async toggleRedis(enabled: boolean): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    console.log('🔌 api.ts: toggleRedis() called with enabled:', enabled);
    const response = await this.client.post('/api/v1/redis/toggle', { enabled });
    return response.data;
  }

  async flushRedis(): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    console.log('🔌 api.ts: flushRedis() called');
    const response = await this.client.post('/api/v1/redis/flush', {});
    return response.data;
  }

  async getRedisSettings(): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    console.log('🔌 api.ts: getRedisSettings() called');
    const response = await this.client.get('/api/v1/redis/settings');
    return response.data;
  }

}

export default new ApiClient();
