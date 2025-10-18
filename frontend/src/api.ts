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

    // Request interceptor to add auth token
    this.client.interceptors.request.use((config) => {
      if (this.accessToken) {
        config.headers.Authorization = `Bearer ${this.accessToken}`;
      }
      return config;
    });

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        if (error.response?.status === 401) {
          // Token expired or invalid
          this.logout();
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }

  private loadToken(): void {
    const token = localStorage.getItem('access_token');
    if (token) {
      this.accessToken = token;
    }
  }

  setToken(token: string): void {
    this.accessToken = token;
    localStorage.setItem('access_token', token);
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

  // Backtest endpoints
  async listBacktests(skip: number = 0, limit: number = 50): Promise<ApiResponse> {
    const response = await this.client.get<ApiResponse>(
      `/api/v1/backtests?skip=${skip}&limit=${limit}`
    );
    return response.data;
  }

  async getBacktest(runId: string): Promise<ApiResponse> {
    const response = await this.client.get<ApiResponse>(`/api/v1/backtests/${runId}`);
    return response.data;
  }

  async runBacktest(data: any): Promise<any> {
    console.log('🔌 api.ts: runBacktest() called with:', data);
    try {
      const response = await this.client.post('/api/v1/backtests/run', data);
      console.log('🔌 api.ts: runBacktest response:', response.data);
      return response.data;
    } catch (error: any) {
      console.error('❌ api.ts: runBacktest failed:', error);
      throw error;
    }
  }

  async getStats(): Promise<ApiResponse> {
    const response = await this.client.get<ApiResponse>('/api/v1/stats');
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
