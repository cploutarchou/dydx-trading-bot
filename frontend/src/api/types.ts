// API Types for dYdX Trading Bot Frontend
// Complete TypeScript definitions for all API responses

// ==================== Core API Response Types ====================

export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
  timestamp?: string;
}

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  timestamp: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  has_next: boolean;
  has_prev: boolean;
}

// ==================== Authentication Types ====================

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: 'Bearer';
  expires_in: number;
}

export interface User {
  id: number;
  username: string;
  email: string;
  full_name?: string;
  avatar?: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
  updated_at?: string;
  profile?: UserProfile;
}

export interface UserProfile {
  first_name?: string;
  last_name?: string;
  timezone?: string;
  preferred_currency?: string;
  notification_settings?: NotificationSettings;
}

export interface NotificationSettings {
  email_alerts: boolean;
  trade_notifications: boolean;
  error_notifications: boolean;
  performance_reports: boolean;
}

// ==================== Bot Instance Types ====================

export interface BotInstance {
  instance_id: string;
  name: string;
  description?: string;
  status: BotStatus;
  credentials: BotCredentials;
  trading_params: TradingParams;
  stats?: BotStats;
  last_heartbeat?: string;
  uptime_seconds: number;
  total_trades: number;
  win_rate: number;
  pnl: number;
  created_at: string;
  updated_at: string;
}

export type BotStatus = 'RUNNING' | 'STOPPED' | 'ERROR' | 'CREATED' | 'STARTING' | 'STOPPING';

export interface BotCredentials {
  address: string;
  network: 'mainnet' | 'testnet';
  // Note: mnemonic is never returned in responses for security
}

export interface TradingParams {
  is_testnet: boolean;
  zscore_threshold: number;
  max_half_life: number;
  usd_per_trade: number;
  max_positions: number;
  slippage_tolerance: number;
  risk_multiplier: number;
  pair_selection_mode?: 'liquidity' | 'volatility' | 'cointegration' | 'input';
}

export interface BotStats {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_pnl: number;
  daily_pnl: number;
  weekly_pnl: number;
  monthly_pnl: number;
  open_positions: number;
  daily_volume: number;
  weekly_volume: number;
  uptime_seconds: number;
  average_trade_duration_minutes: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown: number;
  max_drawdown_percent: number;
  recovery_factor: number;
  profit_factor: number;
}

export interface BotTrade {
  trade_id: string;
  bot_instance_id: string;
  market_1: string;
  market_2: string;
  side_1: 'BUY' | 'SELL';
  side_2: 'BUY' | 'SELL';
  size_1: number;
  size_2: number;
  price_1: number;
  price_2: number;
  status: TradeStatus;
  entry_z_score: number;
  exit_z_score?: number;
  pnl: number;
  pnl_percent: number;
  fees: number;
  slippage: number;
  entry_time: string;
  exit_time?: string;
  duration_minutes?: number;
  order_id_1?: string;
  order_id_2?: string;
}

export type TradeStatus = 'FILLED' | 'PENDING' | 'CANCELLED' | 'FAILED' | 'PARTIAL';

export interface BotPosition {
  position_id: string;
  bot_instance_id: string;
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
  mark_price_1: number;
  mark_price_2: number;
  unrealized_pnl: number;
  unrealized_pnl_percent: number;
  realized_pnl: number;
  entry_time: string;
  current_z_score: number;
  hedge_ratio: number;
  status: PositionStatus;
  risk_score: number;
}

export type PositionStatus = 'LIVE' | 'CLOSED' | 'ERROR' | 'CLOSING';

export interface BotAlert {
  alert_id: string;
  bot_instance_id: string;
  severity: AlertSeverity;
  type: AlertType;
  message: string;
  details?: Record<string, unknown>;
  timestamp: string;
  acknowledged: boolean;
  acknowledged_by?: string;
  acknowledged_at?: string;
}

export type AlertSeverity = 'CRITICAL' | 'ERROR' | 'WARNING' | 'INFO';
export type AlertType =
  | 'TRADE_ERROR'
  | 'CONNECTION_ERROR'
  | 'RISK_ALERT'
  | 'PERFORMANCE_ALERT'
  | 'SYSTEM_ERROR';

export interface BotRealtimeStats {
  bot_instance_id: string;
  timestamp: string;
  uptime_seconds: number;
  total_trades: number;
  trades_today: number;
  trades_this_hour: number;
  open_positions: number;
  total_pnl: number;
  daily_pnl: number;
  hourly_pnl: number;
  pnl_percent: number;
  win_rate: number;
  win_rate_today: number;
  average_trade_duration_minutes: number;
  last_trade_time?: string;
  last_error?: string;
  last_error_time?: string;
  api_latency_ms: number;
  db_latency_ms: number;
  memory_usage_mb: number;
  cpu_usage_percent: number;
}

// ==================== Market Data Types ====================

export interface MarketData {
  market: string;
  price: number;
  volume_24h: number;
  price_change_24h: number;
  price_change_percent_24h: number;
  high_24h: number;
  low_24h: number;
  timestamp: string;
}

export interface CandleData {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  market: string;
}

// ==================== Backtest Types ====================

export interface BacktestConfig {
  name: string;
  description?: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  strategy: string;
  pairs: BacktestPair[];
  trading_params: TradingParams;
  risk_params?: RiskParams;
}

export interface BacktestPair {
  base_market: string;
  quote_market: string;
  hedge_ratio: number;
  half_life: number;
  weight?: number;
}

export interface RiskParams {
  max_drawdown_percent: number;
  max_positions: number;
  position_size_percent: number;
  stop_loss_percent?: number;
  take_profit_percent?: number;
}

export interface Backtest {
  run_id: string;
  name: string;
  description?: string;
  status: BacktestStatus;
  start_date: string;
  end_date: string;
  initial_capital: number;
  final_capital: number;
  total_pnl: number;
  total_pnl_percent: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  profit_factor: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  max_drawdown: number;
  max_drawdown_percent: number;
  recovery_factor: number;
  average_trade_pnl: number;
  average_winning_trade: number;
  average_losing_trade: number;
  largest_winning_trade: number;
  largest_losing_trade: number;
  consecutive_wins: number;
  consecutive_losses: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;
}

export type BacktestStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';

export interface BacktestProgress {
  run_id: string;
  status: BacktestStatus;
  progress_percent: number;
  current_date: string;
  trades_completed: number;
  trades_total: number;
  estimated_completion_seconds: number;
  elapsed_seconds: number;
  current_pnl: number;
  current_pnl_percent: number;
  current_drawdown_percent: number;
}

export interface BacktestMetrics {
  run_id: string;
  timestamp: string;
  total_return: number;
  annualized_return: number;
  volatility: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  max_drawdown: number;
  max_drawdown_percent: number;
  recovery_factor: number;
  win_rate: number;
  profit_factor: number;
  trade_count: number;
  average_trade_pnl: number;
  average_winning_trade: number;
  average_losing_trade: number;
  largest_winning_trade: number;
  largest_losing_trade: number;
  consecutive_wins: number;
  consecutive_losses: number;
  average_trade_duration: number;
  trading_frequency: number;
  turnover_rate: number;
}

export interface BacktestAnalytics {
  run_id: string;
  equity_curve: EquityPoint[];
  drawdown_curve: DrawdownPoint[];
  trade_distribution: TradeDistribution;
  monthly_returns: MonthlyReturn[];
  rolling_metrics: RollingMetrics[];
  correlation_matrix: Record<string, Record<string, number>>;
}

export interface BacktestSyncHealthRun {
  run_id: string;
  status?: string;
  trades: number;
  positions: number;
  candles: number;
  run_age_seconds?: number;
  sync_lag_seconds?: number;
}

export interface BacktestSyncHealth {
  runs: BacktestSyncHealthRun[];
}

export interface EquityPoint {
  timestamp: string;
  equity: number;
  pnl: number;
  cumulative_pnl: number;
  drawdown: number;
  drawdown_percent: number;
}

export interface DrawdownPoint {
  timestamp: string;
  drawdown: number;
  drawdown_percent: number;
  recovery_time_days?: number;
}

export interface TradeDistribution {
  profit_bins: Array<{ range: string; count: number; percentage: number }>;
  duration_bins: Array<{ range: string; count: number; percentage: number }>;
  by_day_of_week: Array<{ day: string; count: number; avg_pnl: number }>;
  by_hour: Array<{ hour: number; count: number; avg_pnl: number }>;
}

export interface MonthlyReturn {
  year: number;
  month: number;
  return_percent: number;
  trades: number;
  win_rate: number;
}

export interface RollingMetrics {
  timestamp: string;
  window_days: number;
  return_percent: number;
  volatility: number;
  sharpe_ratio: number;
  max_drawdown_percent: number;
}

// ==================== System Types ====================

export interface SystemStatus {
  status: 'operational' | 'degraded' | 'down';
  version: string;
  uptime_seconds: number;
  components: SystemComponents;
  metrics: SystemMetrics;
  last_check: string;
}

export interface SystemComponents {
  database: ComponentStatus;
  bot_api: ComponentStatus;
  cache: ComponentStatus;
  indexer: ComponentStatus;
  websocket: ComponentStatus;
}

export interface ComponentStatus {
  status: 'healthy' | 'unhealthy' | 'degraded';
  latency_ms?: number;
  last_check: string;
  error_message?: string;
}

export interface SystemMetrics {
  active_bots: number;
  active_backtests: number;
  total_trades_24h: number;
  total_volume_24h: number;
  api_requests_1h: number;
  websocket_connections: number;
  average_latency_ms: number;
  error_rate_percent: number;
  memory_usage_mb: number;
  cpu_usage_percent: number;
  disk_usage_percent: number;
}

// ==================== Settings Types ====================

export interface Settings {
  trading: TradingSettings;
  risk: RiskSettings;
  notifications: NotificationSettings;
  api: ApiSettings;
}

export interface TradingSettings {
  default_zscore_threshold: number;
  default_usd_per_trade: number;
  default_max_positions: number;
  default_slippage_tolerance: number;
  auto_start_bots: boolean;
  auto_restart_on_error: boolean;
}

export interface RiskSettings {
  max_drawdown_percent: number;
  max_daily_loss: number;
  max_position_size_percent: number;
  emergency_stop_enabled: boolean;
  risk_alerts_enabled: boolean;
}

export interface ApiSettings {
  rate_limit_requests_per_minute: number;
  timeout_seconds: number;
  retry_attempts: number;
  cache_ttl_seconds: number;
}

// ==================== WebSocket Message Types ====================

export interface WebSocketMessage {
  type: string;
  payload: unknown;
  timestamp: string;
}

export interface BotUpdateMessage extends WebSocketMessage {
  type: 'BOT_UPDATE';
  payload: {
    bot_instance_id: string;
    status: BotStatus;
    stats: BotRealtimeStats;
  };
}

export interface TradeUpdateMessage extends WebSocketMessage {
  type: 'TRADE_UPDATE';
  payload: {
    bot_instance_id: string;
    trade: BotTrade;
  };
}

export interface PositionUpdateMessage extends WebSocketMessage {
  type: 'POSITION_UPDATE';
  payload: {
    bot_instance_id: string;
    position: BotPosition;
  };
}

export interface AlertMessage extends WebSocketMessage {
  type: 'ALERT';
  payload: BotAlert;
}

export interface BacktestProgressMessage extends WebSocketMessage {
  type: 'BACKTEST_PROGRESS';
  payload: BacktestProgress;
}

// ==================== Request Types ====================

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  full_name?: string;
}

export interface CreateBotRequest {
  instance_id: string;
  name: string;
  description?: string;
  credentials: {
    address: string;
    mnemonic: string;
    network: 'mainnet' | 'testnet';
  };
  trading_params: TradingParams;
}

export interface UpdateBotRequest {
  name?: string;
  description?: string;
  trading_params?: Partial<TradingParams>;
}

export interface StartBotRequest {
  strategy?: string;
  pairs?: string[];
  override_params?: Partial<TradingParams>;
}

export interface QuickDeployBotRequest {
  instance_id: string;
  name: string;
  credentials: {
    address: string;
    mnemonic: string;
    network: 'mainnet' | 'testnet';
  };
  pairs: string[];
  trading_params: TradingParams;
}

// ==================== Query Parameters ====================

export interface ListBotsParams {
  status?: BotStatus;
  limit?: number;
  offset?: number;
  sort_by?: 'created_at' | 'name' | 'status' | 'pnl';
  sort_order?: 'asc' | 'desc';
}

export interface ListTradesParams {
  bot_instance_id?: string;
  status?: TradeStatus;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
  sort_by?: 'entry_time' | 'pnl' | 'duration_minutes';
  sort_order?: 'asc' | 'desc';
}

export interface ListBacktestsParams {
  status?: BacktestStatus;
  days?: number;
  limit?: number;
  offset?: number;
  sort_by?: 'created_at' | 'name' | 'total_pnl' | 'sharpe_ratio';
  sort_order?: 'asc' | 'desc';
}

export interface ListAlertsParams {
  bot_instance_id?: string;
  severity?: AlertSeverity;
  type?: AlertType;
  acknowledged?: boolean;
  limit?: number;
  offset?: number;
}
