/**
 * API client for dYdX Backtest system
 */

import axios, { AxiosError, AxiosInstance } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8888';

interface ApiResponse<T = any> {
  success: boolean;
  message: string;
  data?: T;
  timestamp: string;
}

interface Token {
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

class ApiClient {
  private client: AxiosInstance;
  private accessToken: string | null = null;

  constructor() {
    console.log('🔌 api.ts: ApiClient constructor, API_BASE_URL:', API_BASE_URL);
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Load token from localStorage
    this.loadToken();
    console.log('🔌 api.ts: Token loaded, present:', !!this.accessToken);

    // Request interceptor to add auth token
    this.client.interceptors.request.use((config) => {
      console.log('📤 Request to:', config.url);
      if (this.accessToken) {
        config.headers.Authorization = `Bearer ${this.accessToken}`;
        console.log('✅ Authorization header added for request to:', config.url);
      } else {
        console.warn('⚠️ NO TOKEN - Request to', config.url, 'will fail if auth is required');
      }
      return config;
    });

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        // Log all errors for debugging
        const url = error.config?.url || '';
        const status = error.response?.status;
        console.warn('🚨 API Error:', { url, status, message: error.message });
        
        // Handle 401 Unauthorized - token likely expired
        if (status === 401 && url && !url.includes('/auth/login')) {
          console.warn('⚠️ Token expired or invalid, attempting refresh...');
          
          // Try to get current user to refresh session
          try {
            await this.client.get('/api/v1/users/me');
            // If we got here, session is still valid, retry original request
            if (error.config) {
              console.log('✅ Session refreshed, retrying original request:', url);
              return this.client(error.config);
            }
          } catch (refreshError: any) {
            // Session truly invalid, logout and redirect to login
            console.error('❌ Session invalid, logging out');
            this.logout();
            // Trigger login redirect via localStorage event
            localStorage.setItem('auth_redirect', 'true');
            window.location.href = '/login';
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
    } else {
      console.warn('⚠️ No token in localStorage');
    }
  }

  setToken(token: string): void {
    this.accessToken = token;
    localStorage.setItem('access_token', token);
    console.log('✅ Token set and saved to localStorage');
  }

  // Helper: Check if token is present
  hasToken(): boolean {
    const hasToken = !!this.accessToken;
    console.log('🔍 Token check:', { hasToken, tokenLength: this.accessToken?.length || 0 });
    return hasToken;
  }

  // Helper: Ensure token is loaded from localStorage
  ensureTokenLoaded(): void {
    if (!this.accessToken) {
      console.log('🔄 Token not in memory, reloading from localStorage');
      this.loadToken();
    }
  }

  logout(): void {
    this.accessToken = null;
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
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
      const response = await this.client.post<Token>('/api/v1/auth/login', data);
      console.log('🔌 api.ts: login response:', response.data);
      if (response.data.access_token) {
        this.setToken(response.data.access_token);
        console.log('🔌 api.ts: token saved to localStorage');
      }
      return response.data;
    } catch (error: any) {
      console.error('❌ api.ts: login failed');
      console.error('❌ api.ts: error status:', error.response?.status);
      console.error('❌ api.ts: error data:', error.response?.data);
      console.error('❌ api.ts: error message:', error.message);
      throw error;
    }
  }

  async getCurrentUser(): Promise<any> {
    const response = await this.client.get('/api/v1/users/me');
    return response.data;
  }

  async updateProfile(data: any): Promise<ApiResponse> {
    const response = await this.client.put<ApiResponse>('/api/v1/profile', data);
    return response.data;
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

  async runBacktest(data: any): Promise<any> {
    this.ensureTokenLoaded();
    console.log('🔌 api.ts: runBacktest() called with:', JSON.stringify(data, null, 2));
    console.log('🔌 api.ts: current token:', this.accessToken ? `${this.accessToken.substring(0, 30)}...` : 'NONE');
    console.log('🔌 api.ts: token from localStorage:', localStorage.getItem('access_token') ? 'YES' : 'NO');
    try {
      const response = await this.client.post('/api/v1/backtests/run', data);
      console.log('✅ api.ts: runBacktest response received:', response.status, response.data);
      return response.data;
    } catch (error: any) {
      console.error('❌ api.ts: runBacktest FAILED:', {
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data,
        headers: error.response?.headers,
        message: error.message
      });
      throw error;
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

  async updateSettings(updates: Record<string, any>): Promise<ApiResponse> {
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

  // Strategy endpoints
  async createStrategy(data: any): Promise<ApiResponse> {
    console.log('🔌 api.ts: createStrategy() called with:', data);
    try {
      const response = await this.client.post<ApiResponse>('/api/v1/strategies', data);
      console.log('🔌 api.ts: createStrategy response:', response.data);
      return response.data;
    } catch (error: any) {
      console.error('❌ api.ts: createStrategy failed:', error);
      throw error;
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

  async updateStrategy(strategyId: number, data: any): Promise<ApiResponse> {
    console.log('🔌 api.ts: updateStrategy() called with:', data);
    try {
      const response = await this.client.put<ApiResponse>(`/api/v1/strategies/${strategyId}`, data);
      console.log('🔌 api.ts: updateStrategy response:', response.data);
      return response.data;
    } catch (error: any) {
      console.error('❌ api.ts: updateStrategy failed:', error);
      throw error;
    }
  }

  async deleteStrategy(strategyId: number): Promise<ApiResponse> {
    console.log('🔌 api.ts: deleteStrategy() called for ID:', strategyId);
    try {
      const response = await this.client.delete<ApiResponse>(`/api/v1/strategies/${strategyId}`);
      console.log('🔌 api.ts: deleteStrategy response:', response.data);
      return response.data;
    } catch (error: any) {
      console.error('❌ api.ts: deleteStrategy failed:', error);
      throw error;
    }
  }

  async getPublicStrategies(): Promise<ApiResponse> {
    const response = await this.client.get<ApiResponse>('/api/v1/strategies/public');
    return response.data;
  }

  // WebSocket connection for real-time updates
  connectBacktestSocket(runId: string, token: string): WebSocket {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/backtest/${runId}?token=${token}`;
    return new WebSocket(wsUrl);
  }
}

export default new ApiClient();
