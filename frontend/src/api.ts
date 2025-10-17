/**
 * API client for dYdX Backtest system
 */

import axios, { AxiosInstance, AxiosError } from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';

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
    const response = await this.client.post<ApiResponse>(
      '/auth/register',
      data
    );
    return response.data;
  }

  async login(data: LoginRequest): Promise<Token> {
    const response = await this.client.post<Token>('/auth/login', data);
    if (response.data.access_token) {
      this.setToken(response.data.access_token);
    }
    return response.data;
  }

  async getCurrentUser(): Promise<any> {
    const response = await this.client.get('/users/me');
    return response.data;
  }

  // Backtest endpoints
  async listBacktests(skip: number = 0, limit: number = 50): Promise<ApiResponse> {
    const response = await this.client.get<ApiResponse>(
      `/backtests?skip=${skip}&limit=${limit}`
    );
    return response.data;
  }

  async getBacktest(runId: string): Promise<ApiResponse> {
    const response = await this.client.get<ApiResponse>(`/backtests/${runId}`);
    return response.data;
  }

  async getStats(): Promise<ApiResponse> {
    const response = await this.client.get<ApiResponse>('/stats');
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
