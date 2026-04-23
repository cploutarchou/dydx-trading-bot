/**
 * API client for dYdX Backtest system
 */

import axios, { AxiosError, AxiosInstance, AxiosRequestHeaders } from 'axios';
import {
    guardBacktestStatusContract,
    guardListBacktestsContract,
    guardRunBacktestContract,
    guardSyncHealthContract,
} from './api/contractGuards';
import { getBackendHttpBase, resolveBackendWebSocketUrl } from './api/origin';
import { attachTraceHeader, traceHeaderName } from './api/trace';

const API_BASE_URL = getBackendHttpBase();

const isPublicUnauthenticatedRoute = (url: string): boolean =>
  url.includes('/auth/login') ||
  url.includes('/auth/register') ||
  url.includes('/auth/refresh') ||
  url.includes('/auth/token') ||
  url.includes('/auth/registration-status') ||
  url.includes('/health') ||
  url.includes('/ready');

// Type-safe error message extractor
const getErrorMessage = (error: unknown): string => {
  if (error instanceof AxiosError) {
    const data = error.response?.data as Record<string, unknown> | undefined;
    const upstreamMessage =
      typeof data?.message === 'string'
        ? data.message
        : typeof data?.detail === 'string'
          ? data.detail
          : typeof data?.error === 'string'
            ? data.error
            : null;
    return upstreamMessage || error.message || 'Unknown error';
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
};

const AUTH_COOKIE_NAMES = ['dydx_session', 'access_token', 'refresh_token'] as const;

const getCookieDomainVariants = (hostname: string): Array<string | null> => {
  const variants = new Set<string | null>([null]);
  const normalizedHost = hostname.trim().toLowerCase();

  if (!normalizedHost || normalizedHost === 'localhost' || normalizedHost.includes(':')) {
    return Array.from(variants);
  }

  const hostParts = normalizedHost.split('.').filter(Boolean);
  if (hostParts.length < 2) {
    return Array.from(variants);
  }

  variants.add(normalizedHost);
  variants.add(`.${normalizedHost}`);

  if (hostParts.length > 2) {
    const baseDomain = hostParts.slice(-2).join('.');
    variants.add(baseDomain);
    variants.add(`.${baseDomain}`);
  }

  return Array.from(variants);
};

const expireCookie = (name: string, domain: string | null, secure: boolean): void => {
  const segments = [
    `${name}=`,
    'path=/',
    'expires=Thu, 01 Jan 1970 00:00:00 GMT',
    'max-age=0',
    'samesite=lax',
  ];

  if (domain) {
    segments.push(`domain=${domain}`);
  }

  if (secure) {
    segments.push('secure');
  }

  document.cookie = segments.join('; ');
};

type ApiFailureKind = 'transport' | 'business' | 'unknown';

export interface ApiFailureInfo {
  kind: ApiFailureKind;
  statusCode: number | null;
  message: string;
  traceId?: string | null;
}

export const classifyApiError = (error: unknown): ApiFailureInfo => {
  if (error instanceof AxiosError) {
    const statusCode = error.response?.status ?? null;
    const data = error.response?.data as Record<string, unknown> | undefined;
    const traceId =
      typeof data?.trace_id === 'string'
        ? data.trace_id
        : error.response?.headers?.[traceHeaderName.toLowerCase()] || null;
    const upstreamMessage =
      typeof data?.message === 'string'
        ? data.message
        : typeof data?.detail === 'string'
          ? data.detail
          : typeof data?.error === 'string'
            ? data.error
            : null;

    const message = upstreamMessage || error.message || 'Unknown API error';

    if (statusCode === null || statusCode >= 500 || statusCode === 502 || statusCode === 504) {
      return { kind: 'transport', statusCode, message, traceId };
    }

    if (statusCode >= 400 && statusCode < 500) {
      return { kind: 'business', statusCode, message, traceId };
    }

    return { kind: 'unknown', statusCode, message, traceId };
  }

  if (error instanceof Error) {
    return { kind: 'unknown', statusCode: null, message: error.message };
  }

  return { kind: 'unknown', statusCode: null, message: String(error) };
};

interface ApiResponse<T extends Record<string, unknown> | Token = Record<string, unknown>> {
  success: boolean;
  message: string;
  data?: T;
  timestamp: string;
  trace_id?: string;
}

interface Token extends Record<string, unknown> {
  access_token?: string;
  refresh_token?: string;
  token_type: string;
  expires_in: number;
  session_expires_at?: string;
}

interface LoginRequest {
  username: string;
  password: string;
  cf_turnstile_response?: string;
}

interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  invitation_code?: string;
  cf_turnstile_response?: string;
}

export interface RegistrationStatusResponse extends Record<string, unknown> {
  enabled: boolean;
  reason: string;
  mode: 'open' | 'disabled' | 'invitation_only' | string;
  invitation_required: boolean;
}

interface UserProfile extends Record<string, unknown> {
  id: number;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  is_admin: boolean;
  mfa_enabled?: boolean;
  privileged_mfa_required?: boolean;
  password_change_required: boolean;
  created_at: string;
  avatar?: string;
  full_name?: string;
}

export interface AdminUser extends UserProfile {
  updated_at: string;
}

export interface AdminUserListResponse extends Record<string, unknown> {
  users: AdminUser[];
  roles: string[];
}

export interface CreateAdminUserPayload extends Record<string, unknown> {
  username: string;
  email: string;
  password: string;
  role: string;
  full_name?: string;
  is_active?: boolean;
}

export interface UpdateAdminUserPayload extends Record<string, unknown> {
  email?: string;
  full_name?: string;
  role?: string;
  is_active?: boolean;
}

export interface ChangePasswordPayload extends Record<string, unknown> {
  current_password: string;
  new_password: string;
}

export interface IBInvitationToken extends Record<string, unknown> {
  id: number;
  token_code: string;
  label: string;
  ib_name: string;
  campaign_name: string;
  max_uses: number;
  used_count: number;
  created_by_user_id?: number;
  last_used_by_user_id?: number;
  expires_at?: string;
  last_used_at?: string;
  revoked_at?: string;
  created_at: string;
  updated_at: string;
}

export interface IBInvitationTokenListResponse extends Record<string, unknown> {
  tokens: IBInvitationToken[];
  total: number;
}

export interface CreateIBInvitationTokenPayload extends Record<string, unknown> {
  label?: string;
  ib_name?: string;
  campaign_name?: string;
  max_uses?: number;
  expires_in_hours?: number;
}

export interface SeedDummyClientsResponse extends Record<string, unknown> {
  created_users: AdminUser[];
  existing_usernames: string[];
  seeded_relationships: number;
  seeded_commission_metrics: number;
  seeded_applications: number;
  shared_development_secret: string;
}

export interface ResetAdminUserMFAResponse extends Record<string, unknown> {
  user: AdminUser;
  had_mfa_enabled: boolean;
  credential_removed: boolean;
}

export interface PortalOverviewModule extends Record<string, unknown> {
  key: string;
  title: string;
  description: string;
  routes: string[];
}

export interface PortalOverviewCounts extends Record<string, unknown> {
  clients: number;
  ibs: number;
  sub_ibs: number;
  backoffice: number;
  admins: number;
  pending_partner_applications: number;
}

export interface PortalOverviewResponse extends Record<string, unknown> {
  role: string;
  modules: PortalOverviewModule[];
  counts: PortalOverviewCounts;
}

export interface PartnerApplication extends Record<string, unknown> {
  id: number;
  applicant_user_id: number;
  sponsor_user_id?: number;
  requested_role: 'ib' | 'sub_ib' | string;
  status: 'pending' | 'reviewing' | 'approved' | 'rejected' | string;
  business_name: string;
  notes: string;
  review_notes: string;
  reviewed_by_user_id?: number;
  reviewed_at?: string;
  created_at: string;
  updated_at: string;
}

export interface PartnerApplicationListResponse extends Record<string, unknown> {
  applications: PartnerApplication[];
}

export interface CreatePartnerApplicationPayload extends Record<string, unknown> {
  requested_role: 'ib' | 'sub_ib';
  sponsor_user_id?: number;
  business_name?: string;
  notes?: string;
}

export interface ReviewPartnerApplicationPayload extends Record<string, unknown> {
  status: 'approved' | 'rejected' | 'reviewing';
  review_notes?: string;
}

export interface CRMSummaryResponse extends Record<string, unknown> {
  active_users: number;
  clients: number;
  ibs: number;
  sub_ibs: number;
  backoffice: number;
  hierarchy_edges?: number;
  sponsored_partners?: number;
  net_commission_usd?: number;
  pending_partner_applications: number;
}

export interface CRMUserRow extends Record<string, unknown> {
  id: number;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  sponsor_user_id: number;
  relationship_type: string;
  direct_partner_count: number;
  created_at: string;
  updated_at: string;
}

export interface CRMUsersTableResponse extends Record<string, unknown> {
  users: CRMUserRow[];
}

export interface PartnerRelationship extends Record<string, unknown> {
  id: number;
  sponsor_user_id: number;
  partner_user_id: number;
  relationship_type: string;
  source_application_id?: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PartnerHierarchyResponse extends Record<string, unknown> {
  relationships: PartnerRelationship[];
}

export interface CRMSecurityEvent extends Record<string, unknown> {
  id: number;
  user_id?: number;
  username: string;
  event_type: string;
  outcome: string;
  reason: string;
  ip_address?: string;
  user_agent?: string;
  created_at: string;
}

export interface CRMSecurityEventsResponse extends Record<string, unknown> {
  events: CRMSecurityEvent[];
}

export interface PartnerCommissionMetric extends Record<string, unknown> {
  id?: number;
  user_id: number;
  period_start: string;
  period_end: string;
  direct_clients: number;
  sub_ib_count: number;
  notional_volume_usd: number;
  gross_commission_usd: number;
  rebate_usd: number;
  net_commission_usd: number;
  created_at?: string;
  updated_at?: string;
}

export interface PartnerCommissionMetricEnvelope extends Record<string, unknown> {
  owner: PartnerCommissionMetric;
  downline: PartnerCommissionMetric;
  direct_partner_ids: number[];
}

export interface UpsertPartnerCommissionMetricPayload extends Record<string, unknown> {
  period_start?: string;
  period_end?: string;
  direct_clients: number;
  sub_ib_count: number;
  notional_volume_usd: number;
  gross_commission_usd: number;
  rebate_usd: number;
  net_commission_usd: number;
}

// ==================== IB TIER COMMISSION RATE TYPES ====================

export interface IBTierCommissionRate extends Record<string, unknown> {
  id: number;
  tier_level: number;
  commission_rate_pct: number;
  rebate_rate_pct: number;
  description: string;
  is_active: boolean;
  created_by_user_id?: number;
  created_at: string;
  updated_at: string;
}

export interface IBTierCommissionRateListResponse extends Record<string, unknown> {
  rates: IBTierCommissionRate[];
  total: number;
}

export interface UpsertIBTierCommissionRatePayload extends Record<string, unknown> {
  commission_rate_pct: number;
  rebate_rate_pct: number;
  description?: string;
  is_active?: boolean;
}

// Pyramid tree — unlimited depth hierarchy
export interface IBPyramidNode extends Record<string, unknown> {
  user_id: number;
  sponsor_user_id?: number;
  relationship_type: string;
  tier_level: number;
  is_active: boolean;
  children: IBPyramidNode[];
}

export interface IBHierarchyTreeResponse extends Record<string, unknown> {
  roots: IBPyramidNode[];
  total_nodes: number;
  max_depth: number;
}

export interface MailgunStatusResponse extends Record<string, unknown> {
  provider: string;
  configured: boolean;
  shared_key_present: boolean;
  shared_key_masked?: string;
  shared_key_label?: string;
  domain?: string;
  from_email?: string;
  from_name?: string;
  region?: 'us' | 'eu' | string;
  base_url?: string;
  pending_password_change_count: number;
}

export interface MailgunConfigPayload extends Record<string, unknown> {
  api_key: string;
  label?: string;
  domain: string;
  from_email: string;
  from_name?: string;
  region?: 'us' | 'eu' | string;
}

export interface TelegramStatusResponse extends Record<string, unknown> {
  provider: string;
  configured: boolean;
  shared_token_present: boolean;
  shared_token_masked?: string;
  shared_token_label?: string;
  chat_id?: string;
  chat_id_masked?: string;
  delivery_mode?: string;
  message?: string;
}

export interface TelegramConfigPayload extends Record<string, unknown> {
  bot_token?: string;
  chat_id: string;
  label?: string;
}

export interface BotServiceCapabilitiesResponse extends Record<string, unknown> {
  service: string;
  http_endpoints: string[];
  websocket_channels: string[];
  http_count: number;
  websocket_count: number;
  count: number;
  command_endpoints?: string[];
  query_endpoints?: string[];
  event_channels?: string[];
}

export interface BotRuntimeDBConfigResponse extends Record<string, unknown> {
  db_type: string;
  cutover_mode: string;
  connection_source: string;
  field_source?: string;
  database_url_configured?: boolean;
  host?: string;
  port?: number | string;
  name?: string;
  user?: string;
  password_configured?: boolean;
  timeout_seconds?: number;
  pool_size?: number;
  max_overflow?: number;
  max_connections?: number;
  ssl_enabled?: boolean;
  echo_sql?: boolean;
  count?: number;
}

export interface InterruptedBacktestsResponse extends Record<string, unknown> {
  interruption_error: string;
  orphaned_in_progress: Array<Record<string, unknown>>;
  interrupted_runs: Array<Record<string, unknown>>;
  orphaned_count: number;
  interrupted_count: number;
  count: number;
  dry_run?: boolean;
  candidates?: Array<Record<string, unknown>>;
  reconciled?: Array<Record<string, unknown>>;
  candidate_count?: number;
  reconciled_count?: number;
}

interface BacktestRequest extends Record<string, unknown> {
  start_date: string;
  end_date: string;
  name?: string;
  description?: string;
  initial_balance?: number;
  timeout_seconds?: number;
  max_pairs?: number;
  pair_selection_mode?: 'liquidity' | 'volatility' | 'cointegration' | 'input';
  pairs?: string[];
  strategy_id?: number;
  trading_parameters?: Record<string, unknown> & {
    pair_selection_mode?: 'liquidity' | 'volatility' | 'cointegration' | 'input';
  };
}

interface StrategyRequest extends Record<string, unknown> {
  name: string;
  category?: string;
  description?: string;
  is_public?: boolean;
  user_id?: number;
  runtime_strategy?: string;
  runtime_network?: 'testnet' | 'mainnet';
  runtime_subaccount?: number;
  resolution?: string;
  candle_resolution?: string;
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
  transaction_fee?: number;
  slippage?: number;
  starting_balance?: number;
  max_history_days?: number;
  benchmark_symbol?: string;
  risk_free_rate?: number;
  initial_amount?: number;
  pair_selection_mode?: 'liquidity' | 'volatility' | 'cointegration' | 'input';
}

interface SettingsUpdate extends Record<string, unknown> {
  // Settings properties
  [key: string]: unknown;
}

export interface CodexCapabilities extends Record<string, unknown> {
  query_only: boolean;
  supports_websockets: boolean;
  supports_webhooks: boolean;
  supports_wallet_pnl: boolean;
  supports_wallet_balances: boolean;
  requests_per_second: number;
  monthly_requests: number;
}

export interface CodexStatusResponse extends Record<string, unknown> {
  configured: boolean;
  provider: string;
  base_url: string;
  shared_key_available: boolean;
  user_key_available: boolean;
  shared_key_masked?: string;
  user_key_masked?: string;
  active_key_source: 'user' | 'shared' | 'none';
  capabilities: CodexCapabilities;
  message: string;
}

export interface CodexTokenSummary extends Record<string, unknown> {
  id: string;
  address: string;
  network_id: number;
  name: string;
  symbol: string;
  price_usd: number;
  price_change_pct_1h: number;
  price_change_pct_4h: number;
  price_change_pct_24h: number;
  liquidity_usd: number;
  volume_usd_24h: number;
  market_cap_usd: number;
  transactions_24h: number;
  is_scam: boolean;
  exchanges: string[];
  confidence_hint: 'high' | 'medium' | 'low' | 'flagged';
  resolution_confidence?: 'high' | 'medium';
}

export interface CodexMarketOverviewResponse extends Record<string, unknown> {
  network_id: number;
  movers: CodexTokenSummary[];
  safe_movers: CodexTokenSummary[];
  generated_at: string;
}

export interface CodexTokenSearchResponse extends Record<string, unknown> {
  results: CodexTokenSummary[];
  count: number;
  query: string;
}

export interface CodexPairSummary extends Record<string, unknown> {
  pair_id: string;
  pair_address: string;
  exchange_name: string;
  exchange_id: string;
  protocol: string;
  liquidity_usd: number;
  volume_usd_24h: number;
  price_usd: number;
  price_change_pct_24h: number;
  backing_token: string;
}

export interface CodexTokenDetailResponse extends Record<string, unknown> {
  token: CodexTokenSummary;
  description: string;
  image_small_url: string;
  image_large_url: string;
  image_banner_url: string;
  circulating_supply: number;
  total_supply: number;
  top_pairs: CodexPairSummary[];
}

export interface CodexChartPoint extends Record<string, unknown> {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume_usd: number;
  liquidity_usd: number;
  transactions: number;
}

export interface CodexTokenChartResponse extends Record<string, unknown> {
  token_id: string;
  interval: string;
  points: CodexChartPoint[];
  generated_at: string;
}

export interface CodexAssetContextRequest extends Record<string, unknown> {
  network_id?: number;
  assets: Array<{
    label?: string;
    symbol?: string;
    address?: string;
    network_id?: number;
  }>;
}

export interface CodexAssetIntel extends Record<string, unknown> {
  label: string;
  resolved: boolean;
  resolution_reason?: string;
  token?: CodexTokenSummary;
}

export interface CodexAssetContextResponse extends Record<string, unknown> {
  items: CodexAssetIntel[];
}

export interface CodexKeyPayload extends Record<string, unknown> {
  api_key: string;
  label?: string;
}

export interface CoinDeskArticle extends Record<string, unknown> {
  id: string;
  title: string;
  url: string;
  summary: string;
  author: string;
  category: string;
  published_at: string;
  image_url: string;
  tags: string[];
}

export interface CoinDeskNewsResponse extends Record<string, unknown> {
  provider: string;
  source: string;
  feed_url: string;
  last_build_at: string;
  generated_at: string;
  articles: CoinDeskArticle[];
}

export interface CoinDeskNewsConfigStatus extends Record<string, unknown> {
  provider: string;
  shared_key_present: boolean;
  shared_key_masked?: string;
  shared_key_label?: string;
  feed_url: string;
  source: string;
  configured_by_admin: boolean;
}

export interface CoinDeskNewsConfigPayload extends Record<string, unknown> {
  api_key: string;
  label?: string;
}

interface DYDXKey extends Record<string, unknown> {
  id?: number;
  network: string;
  chain_address: string;
  secret_masked?: string;
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
  runtime_strategy?: string;
  runtime_network?: 'testnet' | 'mainnet';
  runtime_subaccount?: number;
  resolution?: string;
  candle_resolution?: string;
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
  transaction_fee?: number;
  slippage?: number;
  starting_balance?: number;
  max_history_days?: number;
  benchmark_symbol?: string;
  risk_free_rate?: number;
  initial_amount?: number;
  pair_selection_mode?: 'liquidity' | 'volatility' | 'cointegration' | 'input';
  is_public?: boolean;
  created_at?: string;
  updated_at?: string;
}

interface StrategyListResponse extends Record<string, unknown> {
  strategies: StrategyResponse[];
  total: number;
}

interface StrategyRuntimeResponse extends Record<string, unknown> {
  strategy_id: number;
  strategy_name?: string;
  instance_id?: string;
  network?: string;
  runtime_network?: string;
  runtime_subaccount?: number;
  capital_allocation_usd?: number;
  status: string;
  bot_status?: string;
  is_running: boolean;
  process_id?: number | null;
  last_error?: string;
  started_at?: string;
  stopped_at?: string;
  last_run_at?: string;
  next_run_at?: string;
  updated_at?: string;
  last_synced_at?: string;
}

interface StrategyStartReadinessResponse extends Record<string, unknown> {
  strategy_id: number;
  strategy_name?: string;
  selected_runtime_network: 'testnet' | 'mainnet';
  selected_subaccount: number;
  key_exists: boolean;
  key_chain_address?: string;
  available_collateral: number;
  equity: number;
  open_positions: number;
  usd_per_trade: number;
  usd_min_collateral: number;
  capital_allocation_usd: number;
  trade_size_to_collateral_ratio?: number | null;
  sufficient_for_trade_size: boolean;
  sufficient_for_min_collateral: boolean;
  wallet_ready: boolean;
  account_exists: boolean;
  ready: boolean;
  blockers: string[];
  warnings: string[];
}

const normalizeStrategyPayload = (data: StrategyRequest): StrategyRequest => {
  const normalized: StrategyRequest = { ...data };

  const resolvedResolution =
    typeof normalized.resolution === 'string' && normalized.resolution.length > 0
      ? normalized.resolution
      : typeof normalized.candle_resolution === 'string' && normalized.candle_resolution.length > 0
        ? normalized.candle_resolution
        : undefined;

  if (resolvedResolution) {
    normalized.resolution = resolvedResolution;
    normalized.candle_resolution = resolvedResolution;
  }

  return normalized;
};

const normalizeStrategyResponse = <T extends StrategyResponse | undefined>(strategy: T): T => {
  if (!strategy) {
    return strategy;
  }

  const resolution =
    typeof strategy.resolution === 'string' && strategy.resolution.length > 0
      ? strategy.resolution
      : typeof strategy.candle_resolution === 'string'
        ? strategy.candle_resolution
        : undefined;

  return {
    ...strategy,
    ...(resolution ? { resolution, candle_resolution: resolution } : {}),
  } as T;
};

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
  private sessionEstablished: boolean = false;
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

    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    }

    // Request interceptor: browser auth is carried by the HttpOnly session cookie.
    this.client.interceptors.request.use((config) => {
      config.headers ??= {} as AxiosRequestHeaders;
      const headers = config.headers as AxiosRequestHeaders;
      attachTraceHeader(headers as Record<string, string>);

      if (this.accessToken) {
        headers.Authorization = `Bearer ${this.accessToken}`;
      } else {
        const url = config.url || '';
        if (!isPublicUnauthenticatedRoute(url)) {
          console.debug('Cookie session request:', config.url);
        }
      }
      return config;
    });

    // Response interceptor for error handling with refresh-token support
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const isCanceledRequest =
          axios.isCancel(error) ||
          error.code === 'ERR_CANCELED' ||
          error.message === 'Request aborted';

        if (isCanceledRequest) {
          return Promise.reject(error);
        }

        // Log all errors for debugging
        const url = error.config?.url || '';
        const status = error.response?.status;
        const traceId =
          error.response?.headers?.[traceHeaderName.toLowerCase()] ||
          (error.response?.data as { trace_id?: string } | undefined)?.trace_id ||
          null;
        console.warn('🚨 API Error:', { url, status, message: error.message, traceId });

        // Handle 401 Unauthorized - attempt silent refresh
        if (
          status === 401 &&
          url &&
          !url.includes('/auth/login') &&
          !url.includes('/auth/refresh') &&
          !url.includes('/auth/registration-status')
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
                  if (error.config) {
                    if (newToken && error.config.headers) {
                      error.config.headers.Authorization = `Bearer ${newToken}`;
                    }
                    resolve(this.client(error.config));
                    return;
                  }
                  reject(new Error('Failed to retry request after session refresh'));
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

            this.notifyRefreshSuccess(newAccessToken || '');

            // Retry original request with new token
            if (error.config) {
              if (newAccessToken && error.config.headers) {
                error.config.headers.Authorization = `Bearer ${newAccessToken}`;
              }
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

  setToken(token: string, _remember: boolean = true): void {
    this.accessToken = token;
    this.sessionEstablished = true;
  }

  getAccessToken(): string | null {
    return this.accessToken;
  }

  async refreshAccessToken(): Promise<Token> {
    const refreshResponse = await axios.post<ApiResponse<Token> | Token>(
      `${API_BASE_URL}/api/v1/auth/refresh`,
      {},
      {
        withCredentials: true,
        headers: {
          'Content-Type': 'application/json',
          [traceHeaderName]: attachTraceHeader({}),
        },
      }
    );

    const refreshPayload = (refreshResponse.data as ApiResponse<Token>)?.data
      ? (refreshResponse.data as ApiResponse<Token>).data
      : (refreshResponse.data as Token);

    if (!refreshPayload) {
      throw new Error('Refresh endpoint did not return a session payload');
    }

    this.sessionEstablished = true;
    if (refreshPayload.access_token) {
      this.setToken(refreshPayload.access_token);
    }

    return refreshPayload;
  }

  hasRefreshToken(): boolean {
    return this.sessionEstablished;
  }

  async restoreSession(): Promise<boolean> {
    try {
      // If we already have a valid in-memory access token, skip the refresh round-trip.
      if (this.accessToken && this.sessionEstablished) {
        return true;
      }
      await this.refreshAccessToken();
      return true;
    } catch {
      return false;
    }
  }

  // Helper: Check if token is present
  hasToken(): boolean {
    return this.sessionEstablished || !!this.accessToken;
  }

  ensureTokenLoaded(): void {
    return;
  }

  logout(): void {
    this.accessToken = null;
    this.sessionEstablished = false;

    void axios.post(`${API_BASE_URL}/api/v1/auth/logout`, {}, { withCredentials: true });

    // Best-effort cleanup for auth cookies across common domain/secure variants.
    try {
      if (typeof document !== 'undefined') {
        const domains = getCookieDomainVariants(window.location.hostname);
        const useSecure = window.location.protocol === 'https:';

        AUTH_COOKIE_NAMES.forEach((cookieName) => {
          domains.forEach((domain) => {
            expireCookie(cookieName, domain, false);
            if (useSecure) {
              expireCookie(cookieName, domain, true);
            }
          });
        });
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

  async getRegistrationStatus(): Promise<ApiResponse<RegistrationStatusResponse>> {
    const response = await this.client.get<ApiResponse<RegistrationStatusResponse>>(
      '/api/v1/auth/registration-status'
    );
    return response.data;
  }

  async login(data: LoginRequest): Promise<Token> {
    try {
      // Backend wraps responses in { success, message, data: { ... } }
      const response = await this.client.post<ApiResponse<Token>>('/api/v1/auth/login', data);

      // Extract token payload from nested data when present
      const payload = (response.data?.data || response.data) as Token;

      if (payload) {
        this.sessionEstablished = true;
      }
      if (payload && payload.access_token) {
        this.setToken(payload.access_token);
      } else {
        console.debug('Login established an HttpOnly cookie session');
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
    const response = await this.client.get<ApiResponse<UserProfile> | UserProfile>(
      '/api/v1/users/me'
    );
    const payload = response.data as ApiResponse<UserProfile> | UserProfile;

    if (payload && typeof payload === 'object' && 'success' in payload && 'message' in payload) {
      return payload as ApiResponse<UserProfile>;
    }

    return {
      success: true,
      message: 'Current user fetched successfully',
      data: payload as UserProfile,
      timestamp: new Date().toISOString(),
    };
  }

  async updateProfile(data: Partial<UserProfile>): Promise<ApiResponse<UpdateProfileResponse>> {
    const response = await this.client.put<ApiResponse<UpdateProfileResponse>>(
      '/api/v1/profile',
      data
    );
    return response.data;
  }

  async changePassword(data: ChangePasswordPayload): Promise<ApiResponse<{ user: UserProfile }>> {
    const response = await this.client.put<ApiResponse<{ user: UserProfile }>>(
      '/api/v1/auth/change-password',
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

    const maxPageSize = 25;
    const minPageSize = 10;
    const safeSkip = Number.isFinite(skip) && skip >= 0 ? Math.floor(skip) : 0;
    const safeLimit = Number.isFinite(limit) && limit > 0 ? Math.floor(limit) : 25;

    const isRetryableBacktestListError = (error: unknown): boolean => {
      if (!(error instanceof AxiosError)) {
        return false;
      }

      const status = error.response?.status;
      if (status === 502 || status === 504 || status === 408) {
        return true;
      }

      if (status === undefined) {
        return true;
      }

      const message = (error.message || '').toLowerCase();
      if (
        message.includes('aborted') ||
        message.includes('timeout') ||
        message.includes('network') ||
        message.includes('canceled')
      ) {
        return true;
      }

      return error.code === 'ECONNABORTED' || error.code === 'ERR_NETWORK';
    };

    const fetchBacktestsPage = async (
      pageSkip: number,
      pageLimit: number
    ): Promise<ApiResponse<BacktestListResponse>> => {
      try {
        const response = await this.client.get<ApiResponse<BacktestListResponse>>(
          `/api/v1/backtests?skip=${pageSkip}&limit=${pageLimit}`
        );
        guardListBacktestsContract(response.data);
        return response.data;
      } catch (error) {
        if (!isRetryableBacktestListError(error) || pageLimit <= minPageSize) {
          throw error;
        }

        const fallbackLimit = Math.max(minPageSize, Math.floor(pageLimit / 2));
        const fallbackResponse = await this.client.get<ApiResponse<BacktestListResponse>>(
          `/api/v1/backtests?skip=${pageSkip}&limit=${fallbackLimit}`
        );
        guardListBacktestsContract(fallbackResponse.data);
        return fallbackResponse.data;
      }
    };

    if (safeLimit <= maxPageSize) {
      return fetchBacktestsPage(safeSkip, safeLimit);
    }

    const aggregatedBacktests: BacktestListItem[] = [];
    let remaining = safeLimit;
    let nextSkip = safeSkip;
    let totalFromApi: number | null = null;
    let traceId: string | undefined;
    let message = 'Backtests fetched successfully';

    while (remaining > 0) {
      const pageLimit = Math.min(maxPageSize, remaining);
      const pageResponse = await fetchBacktestsPage(nextSkip, pageLimit);
      const pageData = pageResponse.data;
      const pageBacktests = Array.isArray(pageData?.backtests) ? pageData.backtests : [];

      if (totalFromApi === null && typeof pageData?.total === 'number') {
        totalFromApi = pageData.total;
      }
      if (typeof pageResponse.trace_id === 'string' && pageResponse.trace_id.length > 0) {
        traceId = pageResponse.trace_id;
      }
      if (typeof pageResponse.message === 'string' && pageResponse.message.length > 0) {
        message = pageResponse.message;
      }

      aggregatedBacktests.push(...pageBacktests);

      if (pageBacktests.length === 0) {
        break;
      }

      nextSkip += pageBacktests.length;
      remaining -= pageBacktests.length;

      if (pageBacktests.length < pageLimit) {
        break;
      }
    }

    return {
      success: true,
      message,
      data: {
        backtests: aggregatedBacktests,
        total: typeof totalFromApi === 'number' ? totalFromApi : aggregatedBacktests.length,
      },
      timestamp: new Date().toISOString(),
      ...(traceId ? { trace_id: traceId } : {}),
    };
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
      guardRunBacktestContract(response.data);
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async getStats(): Promise<ApiResponse> {
    const response = await this.client.get<ApiResponse>('/api/v1/stats');
    return response.data;
  }

  async getBotServiceCapabilities(): Promise<ApiResponse<BotServiceCapabilitiesResponse>> {
    this.ensureTokenLoaded();
    const response =
      await this.client.get<ApiResponse<BotServiceCapabilitiesResponse>>('/api/v1/capabilities');
    return response.data;
  }

  async getBotRuntimeDBConfig(): Promise<ApiResponse<BotRuntimeDBConfigResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse<BotRuntimeDBConfigResponse>>(
      '/api/v1/runtime/db-config'
    );
    return response.data;
  }

  async getInterruptedBacktests(
    limit: number = 50,
    admin: boolean = false
  ): Promise<ApiResponse<InterruptedBacktestsResponse>> {
    this.ensureTokenLoaded();
    const prefix = admin ? '/api/v1/admin/backtests' : '/api/v1/backtests';
    const response = await this.client.get<ApiResponse<InterruptedBacktestsResponse>>(
      `${prefix}/interrupted?limit=${limit}`
    );
    return response.data;
  }

  async reconcileInterruptedBacktests(
    dryRun: boolean = true,
    admin: boolean = false
  ): Promise<ApiResponse<InterruptedBacktestsResponse>> {
    this.ensureTokenLoaded();
    const prefix = admin ? '/api/v1/admin/backtests' : '/api/v1/backtests';
    const response = await this.client.post<ApiResponse<InterruptedBacktestsResponse>>(
      `${prefix}/interrupted/reconcile?dry_run=${dryRun}`,
      {}
    );
    return response.data;
  }

  async getBacktestLogs(
    runId: string
  ): Promise<
    ApiResponse<{ logs: Array<{ id: number; message: string; level: string; created_at: string }> }>
  > {
    // Ensure token is loaded before making the request
    this.ensureTokenLoaded();
    try {
      const response = await this.client.get<
        ApiResponse<{
          logs: Array<{ id: number; message: string; level: string; created_at: string }>;
        }>
      >(`/api/v1/backtests/${runId}/logs`);

      // Contract normalize: treat missing logs payload as empty list for resilient polling.
      if (!response.data.data) {
        response.data.data = { logs: [] };
      } else if (!Array.isArray(response.data.data.logs)) {
        response.data.data.logs = [];
      }

      return response.data;
    } catch (error: unknown) {
      if (error instanceof AxiosError && error.response?.status === 404) {
        return {
          success: true,
          message: 'Backtest logs endpoint unavailable',
          data: { logs: [] },
          timestamp: new Date().toISOString(),
        };
      }
      throw new Error(getErrorMessage(error));
    }
  }

  async getBacktestStatus(runId: string): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse<Record<string, unknown>>>(
      `/api/v1/backtests/${runId}/status`
    );
    guardBacktestStatusContract(response.data);
    return response.data;
  }

  async getBacktestSyncHealth(runId?: string): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const query = runId ? `?run_id=${encodeURIComponent(runId)}` : '';
    const response = await this.client.get<ApiResponse<Record<string, unknown>>>(
      `/api/v1/backtests/sync-health${query}`
    );
    guardSyncHealthContract(response.data);
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
    this.ensureTokenLoaded();

    try {
      const response = await this.client.put<ApiResponse>('/api/v1/settings', updates || {});
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async listAdminUsers(): Promise<ApiResponse<AdminUserListResponse>> {
    const response =
      await this.client.get<ApiResponse<AdminUserListResponse>>('/api/v1/admin/users');
    return response.data;
  }

  async getAdminUser(userId: number): Promise<ApiResponse<{ user: AdminUser }>> {
    const response = await this.client.get<ApiResponse<{ user: AdminUser }>>(
      `/api/v1/admin/users/${userId}`
    );
    return response.data;
  }

  async createAdminUser(
    data: CreateAdminUserPayload
  ): Promise<ApiResponse<{ user: AdminUser; roles: string[]; onboarding_notice?: string }>> {
    const response = await this.client.post<
      ApiResponse<{ user: AdminUser; roles: string[]; onboarding_notice?: string }>
    >('/api/v1/admin/users', data);
    return response.data;
  }

  async updateAdminUser(
    userId: number,
    data: UpdateAdminUserPayload
  ): Promise<ApiResponse<{ user: AdminUser; roles: string[] }>> {
    const response = await this.client.put<ApiResponse<{ user: AdminUser; roles: string[] }>>(
      `/api/v1/admin/users/${userId}`,
      data
    );
    return response.data;
  }

  async seedDummyClients(): Promise<ApiResponse<SeedDummyClientsResponse>> {
    const response = await this.client.post<ApiResponse<SeedDummyClientsResponse>>(
      '/api/v1/admin/users/seed-dummy-clients',
      {}
    );
    return response.data;
  }

  async resetAdminUserMFA(userId: number): Promise<ApiResponse<ResetAdminUserMFAResponse>> {
    const response = await this.client.post<ApiResponse<ResetAdminUserMFAResponse>>(
      `/api/v1/admin/users/${userId}/reset-mfa`,
      {}
    );
    return response.data;
  }

  async initializeSettings(): Promise<ApiResponse> {
    const response = await this.client.post<ApiResponse>('/api/v1/settings/initialize', {});
    return response.data;
  }

  async listIBInvitationTokens(
    limit: number = 100,
    offset: number = 0
  ): Promise<ApiResponse<IBInvitationTokenListResponse>> {
    const response = await this.client.get<ApiResponse<IBInvitationTokenListResponse>>(
      `/api/v1/admin/ib/invitations?limit=${limit}&offset=${offset}`
    );
    return response.data;
  }

  async createIBInvitationToken(
    payload: CreateIBInvitationTokenPayload
  ): Promise<ApiResponse<{ token: IBInvitationToken }>> {
    const response = await this.client.post<ApiResponse<{ token: IBInvitationToken }>>(
      '/api/v1/admin/ib/invitations',
      payload
    );
    return response.data;
  }

  async revokeIBInvitationToken(tokenCode: string): Promise<ApiResponse<Record<string, unknown>>> {
    const response = await this.client.post<ApiResponse<Record<string, unknown>>>(
      `/api/v1/admin/ib/invitations/${encodeURIComponent(tokenCode)}/revoke`,
      {}
    );
    return response.data;
  }

  async getPortalOverview(): Promise<ApiResponse<PortalOverviewResponse>> {
    const response =
      await this.client.get<ApiResponse<PortalOverviewResponse>>('/api/v1/portal/overview');
    return response.data;
  }

  async listPartnerApplications(
    limit: number = 100,
    offset: number = 0
  ): Promise<ApiResponse<PartnerApplicationListResponse>> {
    const response = await this.client.get<ApiResponse<PartnerApplicationListResponse>>(
      `/api/v1/portal/applications?limit=${limit}&offset=${offset}`
    );
    return response.data;
  }

  async createPartnerApplication(
    payload: CreatePartnerApplicationPayload
  ): Promise<ApiResponse<{ application: PartnerApplication }>> {
    const response = await this.client.post<ApiResponse<{ application: PartnerApplication }>>(
      '/api/v1/portal/applications',
      payload
    );
    return response.data;
  }

  async getCRMSummary(): Promise<ApiResponse<CRMSummaryResponse>> {
    const response = await this.client.get<ApiResponse<CRMSummaryResponse>>(
      '/api/v1/admin/crm/summary'
    );
    return response.data;
  }

  async getCRMUsersTable(): Promise<ApiResponse<CRMUsersTableResponse>> {
    const response =
      await this.client.get<ApiResponse<CRMUsersTableResponse>>('/api/v1/admin/crm/users');
    return response.data;
  }

  async getCRMHierarchyTable(): Promise<ApiResponse<PartnerHierarchyResponse>> {
    const response = await this.client.get<ApiResponse<PartnerHierarchyResponse>>(
      '/api/v1/admin/crm/hierarchy'
    );
    return response.data;
  }

  async getCRMSecurityEvents(
    limit: number = 50,
    offset: number = 0
  ): Promise<ApiResponse<CRMSecurityEventsResponse>> {
    const response = await this.client.get<ApiResponse<CRMSecurityEventsResponse>>(
      `/api/v1/admin/crm/security-events?limit=${limit}&offset=${offset}`
    );
    return response.data;
  }

  async reviewPartnerApplication(
    applicationId: number,
    payload: ReviewPartnerApplicationPayload
  ): Promise<ApiResponse<{ application: PartnerApplication }>> {
    const response = await this.client.post<ApiResponse<{ application: PartnerApplication }>>(
      `/api/v1/admin/crm/applications/${applicationId}/review`,
      payload
    );
    return response.data;
  }

  async getPartnerHierarchy(): Promise<ApiResponse<PartnerHierarchyResponse>> {
    const response = await this.client.get<ApiResponse<PartnerHierarchyResponse>>(
      '/api/v1/portal/hierarchy'
    );
    return response.data;
  }

  async getPartnerCommissionMetrics(
    userId?: number
  ): Promise<ApiResponse<PartnerCommissionMetricEnvelope>> {
    const query =
      typeof userId === 'number' ? `?user_id=${encodeURIComponent(String(userId))}` : '';
    const response = await this.client.get<ApiResponse<PartnerCommissionMetricEnvelope>>(
      `/api/v1/portal/commission-metrics${query}`
    );
    return response.data;
  }

  async upsertPartnerCommissionMetric(
    userId: number,
    payload: UpsertPartnerCommissionMetricPayload
  ): Promise<ApiResponse<{ metric: PartnerCommissionMetric }>> {
    const response = await this.client.put<ApiResponse<{ metric: PartnerCommissionMetric }>>(
      `/api/v1/admin/crm/commission-metrics/${userId}`,
      payload
    );
    return response.data;
  }

  // ==================== IB TIER COMMISSION RATE METHODS ====================

  async listIBTierRates(): Promise<ApiResponse<IBTierCommissionRateListResponse>> {
    const response = await this.client.get<ApiResponse<IBTierCommissionRateListResponse>>(
      '/api/v1/admin/ib/tier-rates'
    );
    return response.data;
  }

  async upsertIBTierRate(
    tier: number,
    payload: UpsertIBTierCommissionRatePayload
  ): Promise<ApiResponse<{ rate: IBTierCommissionRate }>> {
    const response = await this.client.put<ApiResponse<{ rate: IBTierCommissionRate }>>(
      `/api/v1/admin/ib/tier-rates/${tier}`,
      payload
    );
    return response.data;
  }

  async deleteIBTierRate(tier: number): Promise<ApiResponse<Record<string, unknown>>> {
    const response = await this.client.delete<ApiResponse<Record<string, unknown>>>(
      `/api/v1/admin/ib/tier-rates/${tier}`
    );
    return response.data;
  }

  async getPortalHierarchyTree(): Promise<ApiResponse<IBHierarchyTreeResponse>> {
    const response = await this.client.get<ApiResponse<IBHierarchyTreeResponse>>(
      '/api/v1/portal/hierarchy/tree'
    );
    return response.data;
  }

  async getBacktestPerformance(runId: string): Promise<ApiResponse<BacktestPerformanceResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse<BacktestPerformanceResponse>>(
      `/api/v1/backtests/${runId}/performance`
    );
    return response.data;
  }

  async cancelBacktest(runId: string): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response = await this.client.post<ApiResponse<Record<string, unknown>>>(
      `/api/v1/backtests/${runId}/cancel`,
      {}
    );
    return response.data;
  }

  async pauseBacktest(runId: string): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response = await this.client.post<ApiResponse<Record<string, unknown>>>(
      `/api/v1/backtests/${runId}/pause`,
      {}
    );
    return response.data;
  }

  async resumeBacktest(runId: string): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response = await this.client.post<ApiResponse<Record<string, unknown>>>(
      `/api/v1/backtests/${runId}/resume`,
      {}
    );
    return response.data;
  }

  async restartBacktest(runId: string): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response = await this.client.post<ApiResponse<Record<string, unknown>>>(
      `/api/v1/backtests/${runId}/restart`,
      {}
    );
    return response.data;
  }

  async retryBacktest(runId: string): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response = await this.client.post<ApiResponse<Record<string, unknown>>>(
      `/api/v1/backtests/${runId}/retry`,
      {}
    );
    return response.data;
  }

  async deleteBacktest(runId: string): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response = await this.client.delete<ApiResponse<Record<string, unknown>>>(
      `/api/v1/backtests/${runId}`
    );
    return response.data;
  }

  async compareBacktests(
    runIds: string[],
    metrics: string[]
  ): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response = await this.client.post<ApiResponse<Record<string, unknown>>>(
      '/api/v1/backtests/compare',
      {
        run_ids: runIds,
        metrics,
      }
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
        normalizeStrategyPayload(data)
      );
      return {
        ...response.data,
        data: normalizeStrategyResponse(response.data.data),
      };
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
    return {
      ...response.data,
      data: response.data.data
        ? {
            ...response.data.data,
            strategies: Array.isArray(response.data.data.strategies)
              ? response.data.data.strategies.map((strategy) =>
                  normalizeStrategyResponse(strategy as StrategyResponse)
                )
              : [],
          }
        : response.data.data,
    };
  }

  async getStrategy(strategyId: number): Promise<ApiResponse<StrategyResponse>> {
    const response = await this.client.get<ApiResponse<StrategyResponse>>(
      `/api/v1/strategies/${strategyId}`
    );
    return {
      ...response.data,
      data: normalizeStrategyResponse(response.data.data),
    };
  }

  async updateStrategy(
    strategyId: number,
    data: StrategyRequest
  ): Promise<ApiResponse<StrategyResponse>> {
    try {
      const response = await this.client.put<ApiResponse<StrategyResponse>>(
        `/api/v1/strategies/${strategyId}`,
        normalizeStrategyPayload(data)
      );
      return {
        ...response.data,
        data: normalizeStrategyResponse(response.data.data),
      };
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
    const strategyData = response.data.data as StrategyListResponse | undefined;
    if (!strategyData) {
      return response.data;
    }

    return {
      ...response.data,
      data: {
        ...strategyData,
        strategies: Array.isArray(strategyData.strategies)
          ? strategyData.strategies.map((strategy) =>
              normalizeStrategyResponse(strategy as StrategyResponse)
            )
          : [],
      },
    };
  }

  async getStrategyRuntime(strategyId: number): Promise<ApiResponse<StrategyRuntimeResponse>> {
    try {
      const response = await this.client.get<ApiResponse<StrategyRuntimeResponse>>(
        `/api/v1/strategies/${strategyId}/runtime`
      );
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async getStrategyStartReadiness(
    strategyId: number,
    network?: 'testnet' | 'mainnet'
  ): Promise<ApiResponse<StrategyStartReadinessResponse>> {
    try {
      const params = new URLSearchParams();
      if (network) {
        params.set('network', network);
      }
      const query = params.toString() ? `?${params.toString()}` : '';
      const response = await this.client.get<ApiResponse<StrategyStartReadinessResponse>>(
        `/api/v1/strategies/${strategyId}/start-readiness${query}`
      );
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async startStrategyRuntime(
    strategyId: number,
    network: 'testnet' | 'mainnet',
    forceRecreate: boolean = false
  ): Promise<ApiResponse<StrategyRuntimeResponse>> {
    try {
      const params = new URLSearchParams();
      params.set('network', network);
      if (forceRecreate) {
        params.set('force_recreate', 'true');
      }
      const query = `?${params.toString()}`;
      const response = await this.client.post<ApiResponse<StrategyRuntimeResponse>>(
        `/api/v1/strategies/${strategyId}/start${query}`
      );
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async stopStrategyRuntime(
    strategyId: number,
    force: boolean = false
  ): Promise<ApiResponse<StrategyRuntimeResponse>> {
    try {
      const query = force ? '?force=true' : '';
      const response = await this.client.post<ApiResponse<StrategyRuntimeResponse>>(
        `/api/v1/strategies/${strategyId}/stop${query}`
      );
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
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
    instance_name?: string;
    network?: 'testnet' | 'mainnet';
    strategy?: string;
    credentials: {
      chain_id: string;
      address: string;
      secret_phrase: string;
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

  async getBotPositionHistory(
    instanceId: string,
    positionId: string,
    hours: number = 24
  ): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.get<ApiResponse>(
        `/api/v1/bots/${instanceId}/position-history/${positionId}?hours=${hours}`
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

  async getBotHistory(instanceId: string, days: number = 7): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.get<ApiResponse>(
        `/api/v1/bots/${instanceId}/history?days=${days}`
      );
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async getBotJobs(instanceId: string, days: number = 7): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.get<ApiResponse>(
        `/api/v1/bots/${instanceId}/jobs?days=${days}`
      );
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
    _skip: number = 0,
    limit: number = 50
  ): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.get<ApiResponse>(
        `/api/v1/bots/${instanceId}/alerts?limit=${limit}`
      );
      return response.data;
    } catch (error: unknown) {
      throw new Error(getErrorMessage(error));
    }
  }

  async quickDeployBot(
    instanceName: string,
    autoStart: boolean,
    config: Record<string, unknown>
  ): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response = await this.client.post<ApiResponse<Record<string, unknown>>>(
      `/api/v1/bots/quick-deploy?instance_name=${encodeURIComponent(instanceName)}&auto_start=${autoStart}`,
      config
    );
    return response.data;
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
    const useToken = token || this.accessToken || '';
    return new WebSocket(resolveBackendWebSocketUrl(path, useToken, API_BASE_URL));
  }

  // Backwards-compatible helper specifically for backtest progress
  connectBacktestSocket(runId: string, token?: string): WebSocket {
    return this.connectSocket(`/api/v1/backtests/${encodeURIComponent(runId)}/live`, token);
  }

  connectBacktestAliasSocket(runId: string, token?: string): WebSocket {
    return this.connectSocket(`/ws/backtests/${encodeURIComponent(runId)}`, token);
  }

  connectBotRuntimeSocket(instanceId: string, token?: string): WebSocket {
    return this.connectSocket(`/ws/bots/${encodeURIComponent(instanceId)}`, token);
  }

  connectStrategyRuntimeSocket(token?: string): WebSocket {
    return this.connectSocket('/ws/strategies', token);
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
    try {
      const response = await this.client.post<ApiResponse<RedisStatusResponse>>(
        '/api/v1/settings/test-connection',
        {}
      );
      return response.data;
    } catch (error: unknown) {
      if (error instanceof AxiosError && error.response?.status === 404) {
        const fallback =
          await this.client.get<ApiResponse<RedisStatusResponse>>('/api/v1/redis/status');
        return fallback.data;
      }
      throw new Error(getErrorMessage(error));
    }
  }

  async testRedisConnection(): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response = await this.client.post<ApiResponse<Record<string, unknown>>>(
      '/api/v1/settings/test-connection',
      {}
    );
    return response.data;
  }

  async toggleRedis(enabled: boolean): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.put<ApiResponse<Record<string, unknown>>>(
        '/api/v1/settings',
        {
          'redis.enabled': enabled,
        }
      );
      return response.data;
    } catch (error: unknown) {
      if (error instanceof AxiosError && error.response?.status === 404) {
        const legacyResponse = await this.client.post<ApiResponse<Record<string, unknown>>>(
          '/api/v1/redis/toggle',
          { enabled }
        );
        return legacyResponse.data;
      }
      throw new Error(getErrorMessage(error));
    }
  }

  async flushRedis(): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.post<ApiResponse>('/api/v1/settings/redis/flush', {});
      return response.data;
    } catch (error: unknown) {
      if (error instanceof AxiosError && error.response?.status === 404) {
        const legacyResponse = await this.client.post<ApiResponse>('/api/v1/redis/flush', {});
        return legacyResponse.data;
      }
      throw new Error(getErrorMessage(error));
    }
  }

  async getRedisSettings(): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response =
      await this.client.get<ApiResponse<Record<string, unknown>>>('/api/v1/settings/redis');
    return response.data;
  }

  async getCodexStatus(): Promise<ApiResponse<CodexStatusResponse>> {
    this.ensureTokenLoaded();
    const response =
      await this.client.get<ApiResponse<CodexStatusResponse>>('/api/v1/codex/status');
    return response.data;
  }

  async saveCodexKey(data: CodexKeyPayload): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response = await this.client.put<ApiResponse<Record<string, unknown>>>(
      '/api/v1/codex/key',
      data
    );
    return response.data;
  }

  async deleteCodexKey(): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response =
      await this.client.delete<ApiResponse<Record<string, unknown>>>('/api/v1/codex/key');
    return response.data;
  }

  async getCodexMarketOverview(
    network = 1,
    limit = 6
  ): Promise<ApiResponse<CodexMarketOverviewResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse<CodexMarketOverviewResponse>>(
      '/api/v1/codex/market/overview',
      {
        params: { network, limit },
      }
    );
    return response.data;
  }

  async searchCodexTokens(
    query: string,
    network?: number,
    limit = 8
  ): Promise<ApiResponse<CodexTokenSearchResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse<CodexTokenSearchResponse>>(
      '/api/v1/codex/tokens/search',
      {
        params: { q: query, network, limit },
      }
    );
    return response.data;
  }

  async getCodexTokenDetail(
    network: number,
    address: string
  ): Promise<ApiResponse<CodexTokenDetailResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse<CodexTokenDetailResponse>>(
      `/api/v1/codex/tokens/${network}/${address}`
    );
    return response.data;
  }

  async getCodexTokenChart(
    network: number,
    address: string,
    interval: '1h' | '4h' | '1d' = '1d',
    points = 60
  ): Promise<ApiResponse<CodexTokenChartResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse<CodexTokenChartResponse>>(
      `/api/v1/codex/tokens/${network}/${address}/chart`,
      {
        params: { interval, points },
      }
    );
    return response.data;
  }

  async resolveCodexAssetContext(
    data: CodexAssetContextRequest
  ): Promise<ApiResponse<CodexAssetContextResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.post<ApiResponse<CodexAssetContextResponse>>(
      '/api/v1/codex/assets/context',
      data
    );
    return response.data;
  }

  async getCoinDeskNews(limit = 8): Promise<ApiResponse<CoinDeskNewsResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse<CoinDeskNewsResponse>>(
      '/api/v1/news/coindesk',
      {
        params: { limit },
      }
    );
    return response.data;
  }

  async getCoinDeskNewsConfig(): Promise<ApiResponse<CoinDeskNewsConfigStatus>> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse<CoinDeskNewsConfigStatus>>(
      '/api/v1/news/coindesk/config'
    );
    return response.data;
  }

  async saveCoinDeskNewsConfig(
    data: CoinDeskNewsConfigPayload
  ): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response = await this.client.put<ApiResponse<Record<string, unknown>>>(
      '/api/v1/news/coindesk/config',
      data
    );
    return response.data;
  }

  async deleteCoinDeskNewsConfig(): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response = await this.client.delete<ApiResponse<Record<string, unknown>>>(
      '/api/v1/news/coindesk/config'
    );
    return response.data;
  }

  async getMailgunStatus(): Promise<ApiResponse<MailgunStatusResponse>> {
    this.ensureTokenLoaded();
    const response =
      await this.client.get<ApiResponse<MailgunStatusResponse>>('/api/v1/mailgun/status');
    return response.data;
  }

  async getTelegramStatus(): Promise<ApiResponse<TelegramStatusResponse>> {
    this.ensureTokenLoaded();
    const response =
      await this.client.get<ApiResponse<TelegramStatusResponse>>('/api/v1/telegram/status');
    return response.data;
  }

  async saveTelegramConfig(
    data: TelegramConfigPayload
  ): Promise<ApiResponse<TelegramStatusResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.put<ApiResponse<TelegramStatusResponse>>(
      '/api/v1/telegram/config',
      data
    );
    return response.data;
  }

  async deleteTelegramConfig(): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response =
      await this.client.delete<ApiResponse<Record<string, unknown>>>('/api/v1/telegram/config');
    return response.data;
  }

  async saveMailgunConfig(data: MailgunConfigPayload): Promise<ApiResponse<MailgunStatusResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.put<ApiResponse<MailgunStatusResponse>>(
      '/api/v1/mailgun/config',
      data
    );
    return response.data;
  }

  async deleteMailgunConfig(): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response =
      await this.client.delete<ApiResponse<Record<string, unknown>>>('/api/v1/mailgun/config');
    return response.data;
  }
}

export default new ApiClient();
