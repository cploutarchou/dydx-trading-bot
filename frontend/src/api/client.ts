// Modern API Client for dYdX Trading Bot Frontend
// Production-ready TypeScript client with comprehensive error handling, caching, and interceptors



import axios, { AxiosError, AxiosInstance, CancelTokenSource } from 'axios';import axios, { AxiosError, AxiosInstance, AxiosRequestConfig, CancelTokenSource } from 'axios';

import type {import {

  ApiResponse,  ApiResponse,

  AuthResponse,  ApiError,

  User,  PaginatedResponse,

  BotInstance,  AuthResponse,

  BotStats,  User,

  BotTrade,  BotInstance,

  BotPosition,  BotStats,

  BotAlert,  BotTrade,

  BotRealtimeStats,  BotPosition,

  Backtest,  BotAlert,

  BacktestConfig,  BotRealtimeStats,

  BacktestProgress,  Backtest,

  BacktestMetrics,  BacktestConfig,

  SystemStatus,  BacktestProgress,

  CreateBotRequest,  BacktestMetrics,

  UpdateBotRequest,  BacktestAnalytics,

  StartBotRequest,  SystemStatus,

  QuickDeployBotRequest,  MarketData,

  ListBotsParams,  Settings,

  ListTradesParams,  LoginRequest,

  ListBacktestsParams,  RegisterRequest,

  ListAlertsParams,  CreateBotRequest,

} from './types';  UpdateBotRequest,

  StartBotRequest,

// Client Configuration  QuickDeployBotRequest,

interface ClientConfig {  ListBotsParams,

  baseURL: string;  ListTradesParams,

  timeout: number;  ListBacktestsParams,

  retryAttempts: number;  ListAlertsParams,

  retryDelay: number;} from './types';

  cacheEnabled: boolean;

  cacheTTL: number;// Client Configuration

}interface ClientConfig {

  baseURL: string;

// Request Cache Entry  timeout: number;

interface CacheEntry<T> {  retryAttempts: number;

  data: T;  retryDelay: number;

  timestamp: number;  cacheEnabled: boolean;

  ttl: number;  cacheTTL: number;

}}



// Request Metadata// Request Cache Entry

interface RequestMetadata {interface CacheEntry<T> {

  cancelToken?: CancelTokenSource;  data: T;

  cache?: boolean;  timestamp: number;

  cacheTTL?: number;  ttl: number;

  retry?: boolean;}

  retryAttempts?: number;

}// Request Metadata

interface RequestMetadata {

/**  cancelToken?: CancelTokenSource;

 * Modern API Client with advanced features:  cache?: boolean;

 * - Automatic token management and refresh  cacheTTL?: number;

 * - Request/response caching with TTL  retry?: boolean;

 * - Request cancellation and retry logic  retryAttempts?: number;

 * - Comprehensive error handling}

 * - TypeScript type safety

 * - WebSocket connection managementexport interface AuthResponse {

 */  access_token: string;

export class DydxAPIClient {  refresh_token: string;

  private client: AxiosInstance;  token_type: 'bearer';

  private config: ClientConfig;  expires_in: number;

  private accessToken: string | null = null;}

  private refreshToken: string | null = null;

  private isRefreshing = false;export interface User {

  private refreshSubscribers: Array<(token: string) => void> = [];  id: string;

  private cache = new Map<string, CacheEntry<any>>();  username: string;

  private activeRequests = new Map<string, CancelTokenSource>();  email: string;

  profile?: {

  constructor(config: Partial<ClientConfig> = {}) {    first_name?: string;

    this.config = {    last_name?: string;

      baseURL: config.baseURL || import.meta.env.VITE_API_URL || 'http://localhost:8888',  };

      timeout: config.timeout || 30000,  created_at: string;

      retryAttempts: config.retryAttempts || 3,}

      retryDelay: config.retryDelay || 1000,

      cacheEnabled: config.cacheEnabled ?? true,// Bot Instance Types

      cacheTTL: config.cacheTTL || 60000, // 1 minute defaultexport interface BotInstance {

    };  instance_id: string;

  name: string;

    this.client = axios.create({  status: 'RUNNING' | 'STOPPED' | 'ERROR' | 'CREATED';

      baseURL: `${this.config.baseURL}/api/v1`,  credentials: {

      timeout: this.config.timeout,    address: string;

      headers: {  };

        'Content-Type': 'application/json',  trading_params: {

      },    is_testnet: boolean;

    });    zscore_threshold: number;

    max_half_life: number;

    this.setupInterceptors();    usd_per_trade: number;

    this.loadAuthFromStorage();  };

  }  stats?: BotStats;

  last_heartbeat?: string;

  // ==================== Setup & Configuration ====================  uptime_seconds?: number;

  total_trades?: number;

  private setupInterceptors(): void {  win_rate?: number;

    // Request interceptor  pnl?: number;

    this.client.interceptors.request.use(  created_at: string;

      (config) => {}

        // Add auth token

        if (this.accessToken) {export interface BotStats {

          config.headers = config.headers || {};  total_trades: number;

          config.headers.Authorization = `Bearer ${this.accessToken}`;  win_rate: number;

        }  total_pnl: number;

  daily_pnl: number;

        // Add request timestamp for debugging  open_positions: number;

        config.metadata = { ...config.metadata, requestTime: Date.now() };  daily_volume: number;

  uptime_seconds: number;

        return config;  average_trade_duration_minutes: number;

      },  sharpe_ratio: number;

      (error) => Promise.reject(error)  sortino_ratio: number;

    );}



    // Response interceptorexport interface BotTrade {

    this.client.interceptors.response.use(  trade_id: string;

      (response) => {  market_1: string;

        // Calculate request duration  market_2: string;

        const requestTime = response.config.metadata?.requestTime;  side_1: 'BUY' | 'SELL';

        if (requestTime) {  side_2: 'BUY' | 'SELL';

          const duration = Date.now() - requestTime;  size_1: number;

          console.debug(`API Request: ${response.config.method?.toUpperCase()} ${response.config.url} - ${duration}ms`);  size_2: number;

        }  status: 'FILLED' | 'PENDING' | 'CANCELLED';

  entry_z_score: number;

        return response;  exit_z_score?: number;

      },  pnl?: number;

      async (error: AxiosError) => {  pnl_percent?: number;

        const originalRequest = error.config as any;  entry_time: string;

  exit_time?: string;

        // Handle 401 Unauthorized with token refresh  duration_minutes?: number;

        if (error.response?.status === 401 && !originalRequest._retry) {}

          originalRequest._retry = true;

export interface BotPosition {

          if (this.isRefreshing) {  position_id: string;

            // Queue request to retry after refresh  market_1: string;

            return new Promise((resolve) => {  market_2: string;

              this.refreshSubscribers.push((token: string) => {  side_1: 'BUY' | 'SELL';

                originalRequest.headers.Authorization = `Bearer ${token}`;  side_2: 'BUY' | 'SELL';

                resolve(this.client(originalRequest));  size_1: number;

              });  size_2: number;

            });  entry_price_1: number;

          }  entry_price_2: number;

  current_price_1: number;

          this.isRefreshing = true;  current_price_2: number;

  unrealized_pnl: number;

          try {  unrealized_pnl_percent: number;

            if (this.refreshToken) {  entry_time: string;

              await this.refreshAccessToken();  current_z_score: number;

              originalRequest.headers.Authorization = `Bearer ${this.accessToken}`;  mark_price_1: number;

  mark_price_2: number;

              // Notify queued requests  status: 'LIVE' | 'CLOSED' | 'ERROR';

              this.refreshSubscribers.forEach((callback) => callback(this.accessToken!));}

              this.refreshSubscribers = [];

export interface BotAlert {

              return this.client(originalRequest);  alert_id: string;

            }  severity: 'ERROR' | 'WARNING' | 'INFO';

          } catch (refreshError) {  message: string;

            this.clearAuth();  timestamp: string;

            window.location.href = '/login';  acknowledged: boolean;

            return Promise.reject(refreshError);}

          } finally {

            this.isRefreshing = false;export interface BotRealtimeStats {

          }  uptime_seconds: number;

        }  total_trades: number;

  trades_today: number;

        // Handle rate limiting (429)  open_positions: number;

        if (error.response?.status === 429) {  total_pnl: number;

          const retryAfter = parseInt(error.response.headers['retry-after'] || '60', 10);  daily_pnl: number;

          console.warn(`Rate limited. Retrying after ${retryAfter} seconds`);  pnl_percent: number;

            win_rate: number;

          await this.delay(retryAfter * 1000);  average_trade_duration_minutes: number;

          return this.client(originalRequest);  last_trade_time?: string;

        }  last_error?: string;

  last_error_time?: string;

        // Enhanced error logging  api_latency_ms: number;

        console.error('API Error:', {  db_latency_ms: number;

          url: error.config?.url,}

          method: error.config?.method,

          status: error.response?.status,// Backtest Types

          statusText: error.response?.statusText,export interface BacktestConfig {

          data: error.response?.data,  name: string;

        });  start_date: string;

  end_date: string;

        return Promise.reject(this.normalizeError(error));  initial_capital: number;

      }  strategy: string;

    );  pairs: Array<{

  }    base_market: string;

    quote_market: string;

  private normalizeError(error: AxiosError): Error {    hedge_ratio: number;

    const apiError = error.response?.data as any;    half_life: number;

      }>;

    if (apiError?.error) {  trading_params: {

      return new Error(apiError.error);    zscore_threshold: number;

    }    usd_per_trade: number;

        max_half_life: number;

    if (apiError?.message) {    slippage_percent: number;

      return new Error(apiError.message);  };

    }}



    return new Error(error.message || 'An unexpected error occurred');export interface Backtest {

  }  run_id: string;

  name: string;

  // ==================== Authentication Management ====================  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';

  start_date: string;

  private loadAuthFromStorage(): void {  end_date: string;

    this.accessToken = localStorage.getItem('access_token');  total_pnl: number;

    this.refreshToken = localStorage.getItem('refresh_token');  total_pnl_percent: number;

  }  total_trades: number;

  win_rate: number;

  private saveAuthToStorage(): void {  sharpe_ratio: number;

    if (this.accessToken) {  sortino_ratio: number;

      localStorage.setItem('access_token', this.accessToken);  max_drawdown_percent: number;

    }  calmar_ratio: number;

    if (this.refreshToken) {  created_at: string;

      localStorage.setItem('refresh_token', this.refreshToken);  completed_at?: string;

    }}

  }

export interface BacktestProgress {

  private clearAuth(): void {  run_id: string;

    this.accessToken = null;  status: string;

    this.refreshToken = null;  progress_percent: number;

    localStorage.removeItem('access_token');  trades_completed: number;

    localStorage.removeItem('refresh_token');  trades_total: number;

  }  current_date: string;

  estimated_completion_seconds: number;

  public setAuth(accessToken: string, refreshToken: string): void {}

    this.accessToken = accessToken;

    this.refreshToken = refreshToken;export interface BacktestMetrics {

    this.saveAuthToStorage();  total_return: number;

  }  annualized_return: number;

  sharpe_ratio: number;

  public isAuthenticated(): boolean {  sortino_ratio: number;

    return !!this.accessToken;  calmar_ratio: number;

  }  max_drawdown: number;

  max_drawdown_percent: number;

  // ==================== Caching System ====================  win_rate: number;

  profit_factor: number;

  private getCacheKey(method: string, url: string, params?: any): string {  recovery_factor: number;

    return `${method}:${url}:${JSON.stringify(params || {})}`;  trade_count: number;

  }  average_trade_pnl: number;

  average_winning_trade: number;

  private getFromCache<T>(key: string): T | null {  average_losing_trade: number;

    if (!this.config.cacheEnabled) return null;  consecutive_wins: number;

  consecutive_losses: number;

    const entry = this.cache.get(key);}

    if (!entry) return null;

// System Types

    if (Date.now() > entry.timestamp + entry.ttl) {export interface SystemStatus {

      this.cache.delete(key);  status: 'operational' | 'degraded' | 'down';

      return null;  components: {

    }    database: 'healthy' | 'unhealthy';

    bot_api: 'healthy' | 'unhealthy';

    return entry.data;    cache: 'healthy' | 'unhealthy';

  }    indexer: 'healthy' | 'unhealthy';

  };

  private setCache<T>(key: string, data: T, ttl: number = this.config.cacheTTL): void {  metrics: {

    if (!this.config.cacheEnabled) return;    active_bots: number;

    active_backtests: number;

    this.cache.set(key, {    total_trades_24h: number;

      data,    api_requests_1h: number;

      timestamp: Date.now(),    average_latency_ms: number;

      ttl,  };

    });}

  }

// Main API Client Class

  public clearCache(): void {export class DydxBotAPIClient {

    this.cache.clear();  private apiClient: AxiosInstance;

  }  private baseURL: string;

  private token: string | null = null;

  // ==================== Request Utilities ====================  private refreshToken: string | null = null;



  private delay(ms: number): Promise<void> {  constructor(baseURL: string = 'http://localhost:8888') {

    return new Promise(resolve => setTimeout(resolve, ms));    this.baseURL = baseURL;

  }    

    this.apiClient = axios.create({

  private async makeRequest<T>(      baseURL: `${baseURL}/api/v1`,

    method: 'get' | 'post' | 'put' | 'delete',      timeout: 30000,

    url: string,      headers: {

    data?: any,        'Content-Type': 'application/json',

    options: RequestMetadata = {}      },

  ): Promise<T> {    });

    const cacheKey = options.cache !== false ? this.getCacheKey(method, url, data) : null;

        // Add request interceptor to include auth token

    // Check cache for GET requests    this.apiClient.interceptors.request.use(

    if (method === 'get' && cacheKey) {      (config) => {

      const cached = this.getFromCache<T>(cacheKey);        if (this.token) {

      if (cached) {          config.headers.Authorization = `Bearer ${this.token}`;

        console.debug(`Cache hit: ${cacheKey}`);        }

        return cached;        return config;

      }      },

    }      (error) => Promise.reject(error)

    );

    // Cancel any existing request with same key

    if (cacheKey && this.activeRequests.has(cacheKey)) {    // Add response interceptor to handle token refresh

      this.activeRequests.get(cacheKey)?.cancel('Request superseded');    this.apiClient.interceptors.response.use(

    }      (response) => response,

      async (error: AxiosError) => {

    // Create cancel token        const originalRequest = error.config;

    const cancelToken = axios.CancelToken.source();

    if (cacheKey) {        // Handle 401 (Unauthorized) by attempting token refresh

      this.activeRequests.set(cacheKey, cancelToken);        if (error.response?.status === 401 && !originalRequest?._retry) {

    }          (originalRequest as any)._retry = true;



    try {          try {

      let response;            if (this.refreshToken) {

      const config = { cancelToken: cancelToken.token };              await this.refreshAccessToken();

              return this.apiClient(originalRequest!);

      switch (method) {            }

        case 'get':          } catch (refreshError) {

          response = await this.client.get<ApiResponse<T>>(url, config);            // Refresh failed, logout user

          break;            this.clearAuth();

        case 'post':            window.location.href = '/login';

          response = await this.client.post<ApiResponse<T>>(url, data, config);            return Promise.reject(refreshError);

          break;          }

        case 'put':        }

          response = await this.client.put<ApiResponse<T>>(url, data, config);

          break;        return Promise.reject(error);

        case 'delete':      }

          response = await this.client.delete<ApiResponse<T>>(url, config);    );

          break;  }

      }

  // ==================== Authentication ====================

      const result = response.data.data || response.data;

  async register(username: string, password: string, email: string): Promise<User> {

      // Cache successful GET responses    const response = await this.apiClient.post<ApiResponse<User>>('/auth/register', {

      if (method === 'get' && cacheKey && result) {      username,

        this.setCache(cacheKey, result, options.cacheTTL);      password,

      }      email,

    });

      return result as T;    return response.data.data!;

    } finally {  }

      if (cacheKey) {

        this.activeRequests.delete(cacheKey);  async login(username: string, password: string): Promise<AuthResponse> {

      }    const response = await this.apiClient.post<ApiResponse<AuthResponse>>('/auth/login', {

    }      username,

  }      password,

    });

  // ==================== Authentication Endpoints ====================

    const authData = response.data.data!;

  async login(username: string, password: string): Promise<AuthResponse> {    this.token = authData.access_token;

    const response = await this.client.post<ApiResponse<AuthResponse>>('/auth/login', {    this.refreshToken = authData.refresh_token;

      username,    this.saveAuth();

      password,

    });    return authData;

  }

    const authData = response.data.data!;

    this.setAuth(authData.access_token, authData.refresh_token);  async refreshAccessToken(): Promise<void> {

    if (!this.refreshToken) {

    return authData;      throw new Error('No refresh token available');

  }    }



  async register(username: string, email: string, password: string): Promise<User> {    const response = await this.apiClient.post<ApiResponse<AuthResponse>>('/auth/refresh', {

    return this.makeRequest<User>('post', '/auth/register', {      refresh_token: this.refreshToken,

      username,    });

      email,

      password,    const authData = response.data.data!;

    });    this.token = authData.access_token;

  }    this.refreshToken = authData.refresh_token;

    this.saveAuth();

  async refreshAccessToken(): Promise<void> {  }

    if (!this.refreshToken) {

      throw new Error('No refresh token available');  async getCurrentUser(): Promise<User> {

    }    const response = await this.apiClient.get<ApiResponse<User>>('/users/me');

    return response.data.data!;

    const response = await this.client.post<ApiResponse<AuthResponse>>('/auth/refresh', {  }

      refresh_token: this.refreshToken,

    });  async updateProfile(profile: Partial<User>): Promise<void> {

    await this.apiClient.put('/profile', profile);

    const authData = response.data.data!;  }

    this.setAuth(authData.access_token, authData.refresh_token);

  }  setAuth(token: string, refreshToken: string): void {

    this.token = token;

  async getCurrentUser(): Promise<User> {    this.refreshToken = refreshToken;

    return this.makeRequest<User>('get', '/users/me', undefined, { cache: true, cacheTTL: 300000 }); // 5 minutes    this.saveAuth();

  }  }



  async updateProfile(profile: Partial<User>): Promise<void> {  private saveAuth(): void {

    await this.makeRequest<void>('put', '/users/me', profile);    localStorage.setItem('auth_token', this.token || '');

    this.clearCache(); // Clear user cache after update    localStorage.setItem('refresh_token', this.refreshToken || '');

  }  }



  logout(): void {  private clearAuth(): void {

    this.clearAuth();    this.token = null;

    this.clearCache();    this.refreshToken = null;

  }    localStorage.removeItem('auth_token');

    localStorage.removeItem('refresh_token');

  // ==================== Bot Instance Management ====================  }



  async createBotInstance(config: CreateBotRequest): Promise<BotInstance> {  loadAuthFromStorage(): boolean {

    return this.makeRequest<BotInstance>('post', '/bots', config);    const token = localStorage.getItem('auth_token');

  }    const refreshToken = localStorage.getItem('refresh_token');



  async listBotInstances(params: ListBotsParams = {}): Promise<{ count: number; data: BotInstance[] }> {    if (token && refreshToken) {

    const queryParams = new URLSearchParams();      this.token = token;

    Object.entries(params).forEach(([key, value]) => {      this.refreshToken = refreshToken;

      if (value !== undefined) {      return true;

        queryParams.append(key, value.toString());    }

      }    return false;

    });  }



    const url = `/bots${queryParams.toString() ? `?${queryParams}` : ''}`;  // ==================== Bot Instance Management ====================

    return this.makeRequest<{ count: number; data: BotInstance[] }>('get', url, undefined, { 

      cache: true,   async createBotInstance(config: {

      cacheTTL: 30000 // 30 seconds    instance_id: string;

    });    name: string;

  }    credentials: { address: string; mnemonic: string };

    trading_params: any;

  async getBotInstance(instanceId: string): Promise<BotInstance> {  }): Promise<BotInstance> {

    return this.makeRequest<BotInstance>('get', `/bots/${instanceId}`, undefined, {    const response = await this.apiClient.post<ApiResponse<BotInstance>>('/bots', config);

      cache: true,    return response.data.data!;

      cacheTTL: 10000 // 10 seconds  }

    });

  }  async listBotInstances(

    status?: string,

  async updateBotInstance(instanceId: string, updates: UpdateBotRequest): Promise<BotInstance> {    limit: number = 50,

    const result = await this.makeRequest<BotInstance>('put', `/bots/${instanceId}`, updates);    offset: number = 0

    // Clear related cache entries  ): Promise<{ count: number; data: BotInstance[] }> {

    this.cache.delete(`get:/bots/${instanceId}:undefined`);    const params: any = { limit, offset };

    return result;    if (status) params.status = status;

  }

    const response = await this.apiClient.get<ApiResponse<any>>('/bots', { params });

  async startBotInstance(instanceId: string, config?: StartBotRequest): Promise<{ message: string }> {    return response.data.data;

    return this.makeRequest<{ message: string }>('post', `/bots/${instanceId}/start`, config);  }

  }

  async getBotInstance(instanceId: string): Promise<BotInstance> {

  async stopBotInstance(instanceId: string): Promise<{ message: string }> {    const response = await this.apiClient.get<ApiResponse<BotInstance>>(`/bots/${instanceId}`);

    return this.makeRequest<{ message: string }>('post', `/bots/${instanceId}/stop`);    return response.data.data!;

  }  }



  async restartBotInstance(instanceId: string): Promise<{ message: string }> {  async startBotInstance(instanceId: string, strategy?: string, pairs?: string[]): Promise<any> {

    return this.makeRequest<{ message: string }>('post', `/bots/${instanceId}/restart`);    const response = await this.apiClient.post(`/bots/${instanceId}/start`, {

  }      strategy,

      pairs,

  async deleteBotInstance(instanceId: string): Promise<void> {    });

    await this.makeRequest<void>('delete', `/bots/${instanceId}`);    return response.data;

    this.clearCache(); // Clear all bot-related cache  }

  }

  async stopBotInstance(instanceId: string): Promise<any> {

  async quickDeployBot(config: QuickDeployBotRequest): Promise<BotInstance> {    const response = await this.apiClient.post(`/bots/${instanceId}/stop`);

    return this.makeRequest<BotInstance>('post', '/bots/quick-deploy', config);    return response.data;

  }  }



  // ==================== Bot Statistics & Data ====================  async restartBotInstance(instanceId: string): Promise<any> {

    const response = await this.apiClient.post(`/bots/${instanceId}/restart`);

  async getBotStats(instanceId: string): Promise<BotStats> {    return response.data;

    return this.makeRequest<BotStats>('get', `/bots/${instanceId}/stats`, undefined, {  }

      cache: true,

      cacheTTL: 30000 // 30 seconds  async deleteBotInstance(instanceId: string): Promise<void> {

    });    await this.apiClient.delete(`/bots/${instanceId}`);

  }  }



  async getBotTrades(instanceId: string, params: ListTradesParams = {}): Promise<{ count: number; data: BotTrade[] }> {  async quickDeployBot(config: {

    const queryParams = new URLSearchParams();    instance_id: string;

    Object.entries(params).forEach(([key, value]) => {    credentials: { address: string; mnemonic: string };

      if (value !== undefined) {    pairs: string[];

        queryParams.append(key, value.toString());    trading_params: any;

      }  }): Promise<BotInstance> {

    });    const response = await this.apiClient.post<ApiResponse<BotInstance>>('/bots/quick-deploy', config);

    return response.data.data!;

    const url = `/bots/${instanceId}/trades${queryParams.toString() ? `?${queryParams}` : ''}`;  }

    return this.makeRequest<{ count: number; data: BotTrade[] }>('get', url, undefined, {

      cache: true,  // ==================== Bot Statistics & History ====================

      cacheTTL: 60000 // 1 minute

    });  async getBotStats(instanceId: string): Promise<BotStats> {

  }    const response = await this.apiClient.get<ApiResponse<BotStats>>(`/bots/${instanceId}/stats`);

    return response.data.data!;

  // ==================== Real-Time Bot Data ====================  }



  async getCurrentPositions(instanceId: string): Promise<BotPosition[]> {  async getBotTrades(

    return this.makeRequest<BotPosition[]>('get', `/bots/${instanceId}/positions/current`, undefined, {    instanceId: string,

      cache: true,    limit: number = 50,

      cacheTTL: 5000 // 5 seconds    offset: number = 0,

    });    status?: string,

  }    startDate?: string,

    endDate?: string

  async getPosition(instanceId: string, positionId: string): Promise<BotPosition> {  ): Promise<{ count: number; data: BotTrade[] }> {

    return this.makeRequest<BotPosition>('get', `/bots/${instanceId}/positions/${positionId}`, undefined, {    const params: any = { limit, offset };

      cache: true,    if (status) params.status = status;

      cacheTTL: 5000    if (startDate) params.start_date = startDate;

    });    if (endDate) params.end_date = endDate;

  }

    const response = await this.apiClient.get<ApiResponse<any>>(`/bots/${instanceId}/trades`, { params });

  async getPositionHistory(instanceId: string, positionId: string, hours: number = 24): Promise<any[]> {    return response.data.data;

    return this.makeRequest<any[]>('get', `/bots/${instanceId}/position-history/${positionId}?hours=${hours}`, undefined, {  }

      cache: true,

      cacheTTL: 300000 // 5 minutes  async getBotHistory(instanceId: string, days: number = 7, granularity: string = 'daily'): Promise<any[]> {

    });    const response = await this.apiClient.get<ApiResponse<any[]>>(`/bots/${instanceId}/history`, {

  }      params: { days, granularity },

    });

  async getMarketData(instanceId: string): Promise<Record<string, any>> {    return response.data.data!;

    return this.makeRequest<Record<string, any>>('get', `/bots/${instanceId}/market-data`, undefined, {  }

      cache: true,

      cacheTTL: 30000  async getBotJobs(

    });    instanceId: string,

  }    limit: number = 50,

    offset: number = 0,

  async getRealtimeStats(instanceId: string): Promise<BotRealtimeStats> {    type?: string

    return this.makeRequest<BotRealtimeStats>('get', `/bots/${instanceId}/realtime-stats`, undefined, {  ): Promise<{ count: number; data: any[] }> {

      cache: true,    const params: any = { limit, offset };

      cacheTTL: 5000    if (type) params.type = type;

    });

  }    const response = await this.apiClient.get<ApiResponse<any>>(`/bots/${instanceId}/jobs`, { params });

    return response.data.data;

  async getAlerts(instanceId: string, params: ListAlertsParams = {}): Promise<{ count: number; data: BotAlert[] }> {  }

    const queryParams = new URLSearchParams();

    Object.entries(params).forEach(([key, value]) => {  // ==================== Real-Time Bot Data ====================

      if (value !== undefined) {

        queryParams.append(key, value.toString());  async getCurrentPositions(instanceId: string): Promise<BotPosition[]> {

      }    const response = await this.apiClient.get<ApiResponse<any>>(`/bots/${instanceId}/positions/current`);

    });    return response.data.data;

  }

    const url = `/bots/${instanceId}/alerts${queryParams.toString() ? `?${queryParams}` : ''}`;

    return this.makeRequest<{ count: number; data: BotAlert[] }>('get', url);  async getPosition(instanceId: string, positionId: string): Promise<BotPosition> {

  }    const response = await this.apiClient.get<ApiResponse<BotPosition>>(

      `/bots/${instanceId}/positions/${positionId}`

  // ==================== Backtest Management ====================    );

    return response.data.data!;

  async createBacktest(config: BacktestConfig): Promise<Backtest> {  }

    return this.makeRequest<Backtest>('post', '/backtests', config);

  }  async getPositionHistory(instanceId: string, positionId: string, hours: number = 24): Promise<any[]> {

    const response = await this.apiClient.get<ApiResponse<any>>(

  async listBacktests(params: ListBacktestsParams = {}): Promise<{ count: number; data: Backtest[] }> {      `/bots/${instanceId}/position-history/${positionId}`,

    const queryParams = new URLSearchParams();      {

    Object.entries(params).forEach(([key, value]) => {        params: { hours },

      if (value !== undefined) {      }

        queryParams.append(key, value.toString());    );

      }    return response.data.data;

    });  }



    const url = `/backtests${queryParams.toString() ? `?${queryParams}` : ''}`;  async getMarketData(instanceId: string): Promise<Record<string, any>> {

    return this.makeRequest<{ count: number; data: Backtest[] }>('get', url, undefined, {    const response = await this.apiClient.get<ApiResponse<Record<string, any>>>(

      cache: true,      `/bots/${instanceId}/market-data`

      cacheTTL: 60000    );

    });    return response.data.data!;

  }  }



  async getBacktest(runId: string): Promise<Backtest> {  async getRealtimeStats(instanceId: string): Promise<BotRealtimeStats> {

    return this.makeRequest<Backtest>('get', `/backtests/${runId}`, undefined, {    const response = await this.apiClient.get<ApiResponse<BotRealtimeStats>>(

      cache: true,      `/bots/${instanceId}/realtime-stats`

      cacheTTL: 300000    );

    });    return response.data.data!;

  }  }



  async getBacktestStatus(runId: string): Promise<BacktestProgress> {  async getAlerts(instanceId: string, limit: number = 50, severity?: string): Promise<{ count: number; data: BotAlert[] }> {

    return this.makeRequest<BacktestProgress>('get', `/backtests/${runId}/status`, undefined, {    const params: any = { limit };

      cache: false // Always fresh for progress    if (severity) params.severity = severity;

    });

  }    const response = await this.apiClient.get<ApiResponse<any>>(`/bots/${instanceId}/alerts`, { params });

    return response.data.data;

  async getBacktestTrades(runId: string, limit: number = 50, offset: number = 0): Promise<{ count: number; data: any[] }> {  }

    return this.makeRequest<{ count: number; data: any[] }>('get', `/backtests/${runId}/trades?limit=${limit}&offset=${offset}`, undefined, {

      cache: true,  // ==================== Backtest Management ====================

      cacheTTL: 300000

    });  async createBacktest(config: BacktestConfig): Promise<Backtest> {

  }    const response = await this.apiClient.post<ApiResponse<Backtest>>('/backtests', config);

    return response.data.data!;

  async getBacktestMetrics(runId: string): Promise<BacktestMetrics> {  }

    return this.makeRequest<BacktestMetrics>('get', `/backtests/${runId}/performance-metrics`, undefined, {

      cache: true,  async listBacktests(

      cacheTTL: 300000    limit: number = 50,

    });    offset: number = 0,

  }    status?: string,

    days?: number

  async compareBacktests(runIds: string[], metrics: string[]): Promise<any> {  ): Promise<{ count: number; data: Backtest[] }> {

    return this.makeRequest<any>('post', '/backtests/compare', {    const params: any = { limit, offset };

      run_ids: runIds,    if (status) params.status = status;

      metrics,    if (days) params.days = days;

    });

  }    const response = await this.apiClient.get<ApiResponse<any>>('/backtests', { params });

    return response.data.data;

  async cancelBacktest(runId: string): Promise<{ message: string }> {  }

    return this.makeRequest<{ message: string }>('post', `/backtests/${runId}/cancel`);

  }  async getBacktest(runId: string): Promise<Backtest> {

    const response = await this.apiClient.get<ApiResponse<Backtest>>(`/backtests/${runId}`);

  async deleteBacktest(runId: string): Promise<void> {    return response.data.data!;

    await this.makeRequest<void>('delete', `/backtests/${runId}`);  }

    this.clearCache(); // Clear backtest cache

  }  async getBacktestStatus(runId: string): Promise<BacktestProgress> {

    const response = await this.apiClient.get<ApiResponse<BacktestProgress>>(`/backtests/${runId}/status`);

  // ==================== System Status ====================    return response.data.data!;

  }

  async getSystemStatus(): Promise<SystemStatus> {

    return this.makeRequest<SystemStatus>('get', '/system/status', undefined, {  async getBacktestTrades(runId: string, limit: number = 50, offset: number = 0): Promise<{ count: number; data: any[] }> {

      cache: true,    const response = await this.apiClient.get<ApiResponse<any>>(`/backtests/${runId}/trades`, {

      cacheTTL: 10000      params: { limit, offset },

    });    });

  }    return response.data.data;

  }

  async getHealth(): Promise<any> {

    // Health endpoint doesn't require auth  async getBacktestAnalytics(runId: string): Promise<any> {

    const response = await axios.get(`${this.config.baseURL}/health`);    const response = await this.apiClient.get<ApiResponse<any>>(`/backtests/${runId}/analytics`);

    return response.data;    return response.data.data!;

  }  }



  // ==================== WebSocket Management ====================  async getBacktestMetrics(runId: string): Promise<BacktestMetrics> {

    const response = await this.apiClient.get<ApiResponse<BacktestMetrics>>(

  connectWebSocket(path: string, onMessage?: (data: any) => void, onError?: (error: Event) => void): WebSocket {      `/backtests/${runId}/performance-metrics`

    const wsProtocol = this.config.baseURL.startsWith('https') ? 'wss:' : 'ws:';    );

    const baseUrl = this.config.baseURL.replace(/^https?:\/\//, '');    return response.data.data!;

    const wsUrl = `${wsProtocol}//${baseUrl}${path}${this.accessToken ? `?token=${this.accessToken}` : ''}`;  }



    const ws = new WebSocket(wsUrl);  async compareBacktests(runIds: string[], metrics: string[]): Promise<any> {

    const response = await this.apiClient.post<ApiResponse<any>>('/backtests/compare', {

    ws.onopen = () => {      run_ids: runIds,

      console.debug(`WebSocket connected: ${path}`);      metrics,

    };    });

    return response.data.data!;

    ws.onmessage = (event) => {  }

      if (onMessage) {

        try {  async cancelBacktest(runId: string): Promise<any> {

          const data = JSON.parse(event.data);    const response = await this.apiClient.post(`/backtests/${runId}/cancel`);

          onMessage(data);    return response.data;

        } catch (error) {  }

          console.error('Failed to parse WebSocket message:', error);

        }  async getBacktestSummaryStats(days: number = 30): Promise<any> {

      }    const response = await this.apiClient.get<ApiResponse<any>>('/backtests/stats/summary', {

    };      params: { days },

    });

    ws.onerror = (error) => {    return response.data.data!;

      console.error(`WebSocket error on ${path}:`, error);  }

      if (onError) {

        onError(error);  async getBacktestPositionSnapshots(runId: string): Promise<any[]> {

      }    const response = await this.apiClient.get<ApiResponse<any>>(`/backtests/${runId}/position-snapshots`);

    };    return response.data.data;

  }

    ws.onclose = (event) => {

      console.debug(`WebSocket closed: ${path}`, event.code, event.reason);  async getBacktestDydxValidation(runId: string): Promise<any> {

    };    const response = await this.apiClient.get<ApiResponse<any>>(`/backtests/${runId}/dydx-validation`);

    return response.data.data!;

    return ws;  }

  }

  async deleteBacktest(runId: string): Promise<void> {

  connectBotUpdates(instanceId: string, onMessage: (update: any) => void): WebSocket {    await this.apiClient.delete(`/backtests/${runId}`);

    return this.connectWebSocket(`/api/v1/bots/${instanceId}/updates`, onMessage);  }

  }

  // ==================== WebSocket Connections ====================

  connectBacktestProgress(runId: string, onMessage: (progress: BacktestProgress) => void): WebSocket {

    return this.connectWebSocket(`/api/v1/backtests/${runId}/live-progress`, onMessage);  connectBacktestProgress(runId: string, onMessage: (progress: BacktestProgress) => void): WebSocket {

  }    const wsUrl = `ws://${this.baseURL.replace(/^https?:\/\//, '')}/api/v1/backtests/${runId}/live-progress`;

    const ws = new WebSocket(`${wsUrl}?token=${this.token}`);

  // ==================== Advanced Features ====================

    ws.onmessage = (event) => {

  public getRequestStats(): { cacheHits: number; cacheMisses: number; activeRequests: number } {      try {

    return {        const progress = JSON.parse(event.data);

      cacheHits: 0, // TODO: Implement cache hit tracking        onMessage(progress);

      cacheMisses: 0, // TODO: Implement cache miss tracking      } catch (error) {

      activeRequests: this.activeRequests.size,        console.error('Failed to parse WebSocket message:', error);

    };      }

  }    };



  public cancelAllRequests(): void {    return ws;

    this.activeRequests.forEach((source) => {  }

      source.cancel('All requests cancelled');

    });  connectBotUpdates(instanceId: string, onMessage: (update: any) => void): WebSocket {

    this.activeRequests.clear();    const wsUrl = `ws://${this.baseURL.replace(/^https?:\/\//, '')}/api/v1/bots/${instanceId}/updates`;

  }    const ws = new WebSocket(`${wsUrl}?token=${this.token}`);



  public updateConfig(newConfig: Partial<ClientConfig>): void {    ws.onmessage = (event) => {

    this.config = { ...this.config, ...newConfig };      try {

            const update = JSON.parse(event.data);

    if (newConfig.baseURL) {        onMessage(update);

      this.client.defaults.baseURL = `${newConfig.baseURL}/api/v1`;      } catch (error) {

    }        console.error('Failed to parse WebSocket message:', error);

          }

    if (newConfig.timeout) {    };

      this.client.defaults.timeout = newConfig.timeout;

    }    return ws;

  }  }

}

  // ==================== System Status ====================

// Export singleton instance

export const apiClient = new DydxAPIClient();  async getSystemStatus(): Promise<SystemStatus> {

export default apiClient;    const response = await this.apiClient.get<ApiResponse<SystemStatus>>('/system/status');
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
