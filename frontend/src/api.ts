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
import {
    getBackendHttpBase,
    resolveBackendWebSocketUrl,
    shouldAttemptCookieSessionBootstrap,
} from './api/origin';
import { attachTraceHeader, traceHeaderName } from './api/trace';
import { getCurrentPortalType } from './app/portal';

const API_BASE_URL = getBackendHttpBase();

export const DYDX_CANDLE_RESOLUTION_OPTIONS = [
  { value: '1MIN', label: '1 Minute' },
  { value: '5MINS', label: '5 Minutes' },
  { value: '15MINS', label: '15 Minutes' },
  { value: '30MINS', label: '30 Minutes' },
  { value: '1HOUR', label: '1 Hour' },
  { value: '4HOURS', label: '4 Hours' },
  { value: '1DAY', label: '1 Day' },
] as const;

export type DydxCandleResolution = (typeof DYDX_CANDLE_RESOLUTION_OPTIONS)[number]['value'];

export const normalizeDydxCandleResolution = (value?: string | null): DydxCandleResolution => {
  const normalized = String(value || '')
    .trim()
    .toUpperCase();
  switch (normalized) {
    case 'M1':
    case '1M':
    case '1MIN':
    case '1MINUTE':
    case '1MINUTES':
      return '1MIN';
    case 'M5':
    case '5M':
    case '5MIN':
    case '5MINS':
    case '5MINUTE':
    case '5MINUTES':
      return '5MINS';
    case 'M15':
    case '15M':
    case '15MIN':
    case '15MINS':
    case '15MINUTE':
    case '15MINUTES':
      return '15MINS';
    case 'M30':
    case '30M':
    case '30MIN':
    case '30MINS':
    case '30MINUTE':
    case '30MINUTES':
      return '30MINS';
    case 'H1':
    case '1H':
    case '1HR':
    case '1HOUR':
    case '1HOURS':
      return '1HOUR';
    case 'H4':
    case '4H':
    case '4HR':
    case '4HOUR':
    case '4HOURS':
      return '4HOURS';
    case 'D1':
    case '1D':
    case '1DAY':
    case '1DAYS':
      return '1DAY';
    default:
      return '1HOUR';
  }
};

const isPublicUnauthenticatedRoute = (url: string): boolean =>
  url.includes('/auth/login') ||
  url.includes('/auth/register') ||
  url.includes('/auth/refresh') ||
  url.includes('/auth/token') ||
  url.includes('/auth/registration-status') ||
  url.includes('/public/app-config') ||
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
const SESSION_HINT_KEY = '_dydx_session_established';

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

export interface PublicAppConfigResponse extends Record<string, unknown> {
  app_name: string;
  brand_name: string;
  coming_soon_enabled: boolean;
  public_launch_message?: string;
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
  max_active_backtests?: number;
  max_strategies?: number;
  max_bot_instances?: number;
}

export interface AdminUserListResponse extends Record<string, unknown> {
  users: AdminUser[];
  roles: string[];
}

export interface AccessControlRole extends Record<string, unknown> {
  role: string;
  display_name: string;
  description: string;
  is_system: boolean;
}

export interface AccessControlPermission extends Record<string, unknown> {
  permission_key: string;
  description: string;
  is_sensitive: boolean;
}

export interface AccessControlRolePermission extends Record<string, unknown> {
  role: string;
  permission_key: string;
}

export interface AccessControlResponse extends Record<string, unknown> {
  roles: string[];
  role_catalog?: AccessControlRole[];
  permissions: AccessControlPermission[];
  role_permissions: AccessControlRolePermission[];
}

export interface CreateCustomRolePayload extends Record<string, unknown> {
  role: string;
  display_name?: string;
  description?: string;
}

export interface CreateAdminUserPayload extends Record<string, unknown> {
  username: string;
  email: string;
  password: string;
  role: string;
  full_name?: string;
  is_active?: boolean;
  max_active_backtests?: number;
  max_strategies?: number;
  max_bot_instances?: number;
}

export interface UpdateAdminUserPayload extends Record<string, unknown> {
  email?: string;
  full_name?: string;
  role?: string;
  is_active?: boolean;
  max_active_backtests?: number;
  max_strategies?: number;
  max_bot_instances?: number;
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

export interface BotAPIStatsResponse extends Record<string, unknown> {
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  transport_failures: number;
  timeouts: number;
  upstream_4xx: number;
  upstream_5xx: number;
  total_latency_ms: number;
  average_latency_ms: number;
  max_latency_ms: number;
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

export type TelegramSettingsScope = 'user' | 'global';

export interface TelegramConfigPayload extends Record<string, unknown> {
  bot_token?: string;
  chat_id: string;
  label?: string;
}

export interface TelegramPreflightResponse extends Record<string, unknown> {
  valid: boolean;
  chat_name?: string;
  chat_id?: string;
  error?: string;
  validation_reason?: string;
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

export interface ArbitrageMetricCounters extends Record<string, number> {
  arbitrage_scan_cycles_total: number;
  exchange_api_calls_total: number;
  exchange_api_calls_saved_total: number;
  duplicate_api_calls_avoided_total: number;
  pair_candidates_total: number;
  pair_candidates_skipped_total: number;
  opportunities_detected_total: number;
  opportunities_rejected_total: number;
  opportunities_executed_total: number;
  stale_data_detected_total: number;
  provider_errors_total: number;
  cache_hits_total: number;
  cache_misses_total: number;
  websocket_reconnects_total: number;
}

export interface ArbitrageImprovementMetricsResponse extends Record<string, unknown> {
  started_at: string;
  updated_at: string;
  counters: Partial<ArbitrageMetricCounters>;
  rejection_reasons?: Record<string, number>;
  feature_flags?: Record<string, boolean>;
  runtime_settings?: Record<string, boolean | number>;
}

export interface ArbitrageRuntimeSettings extends Record<string, boolean | number> {
  arbitrage_improvements_enabled: boolean;
  pair_priority_engine_enabled: boolean;
  polymarket_signals_enabled: boolean;
  defillama_signals_enabled: boolean;
  news_signals_enabled: boolean;
  auto_execution_changes_enabled: boolean;
  pair_priority_max_pairs: number;
  pair_priority_stale_seconds: number;
}

export interface ArbitrageRuntimeSettingsResponse extends Record<string, unknown> {
  data: ArbitrageRuntimeSettings;
  bot_runtime?: Record<string, unknown>;
  bot_sync_status?: string;
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

export interface CeleryTask extends Record<string, unknown> {
  task_id: string;
  task_name?: string | null;
  queue?: string | null;
  status: string;
  created_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  runtime_seconds?: number | null;
  progress_percent?: number | null;
  current_step?: string | null;
  current_pair?: string | null;
  strategy_id?: number | string | null;
  backtest_run_id?: string | null;
  bot_id?: string | null;
  environment?: string | null;
  selected_pairs?: string[];
  error_code?: string | null;
  error_message?: string | null;
  traceback?: string | null;
  worker_hostname?: string | null;
  retry_count?: number | null;
  metadata?: Record<string, unknown>;
}

export interface CeleryTasksResponse extends Record<string, unknown> {
  tasks: CeleryTask[];
  total: number;
}

export interface CeleryWorkersResponse extends Record<string, unknown> {
  workers: Array<Record<string, unknown>>;
  total: number;
}

export interface CeleryQueuesResponse extends Record<string, unknown> {
  queues: Array<{ name: string; length?: number | null }>;
  total: number;
}

export interface CeleryHealthResponse extends Record<string, unknown> {
  status: string;
  broker?: Record<string, unknown>;
  result_backend?: Record<string, unknown>;
  workers?: Record<string, unknown>;
  checked_at?: string;
  errors?: string[];
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
  selected_pairs?: string[];
  strategy_id?: number;
  strategy_payload_snapshot?: Record<string, unknown>;
  bot_id?: string;
  source?: string;
  requested_by_user_id?: number;
  source_strategy_version?: number | string;
  environment?: string;
  trading_parameters?: Record<string, unknown> & {
    pair_selection_mode?: 'liquidity' | 'volatility' | 'cointegration' | 'input';
  };
}

const normalizeStringList = (value: unknown): string[] | undefined => {
  if (!Array.isArray(value)) {
    return undefined;
  }

  const cleaned = value
    .map((item) => String(item).trim())
    .filter((item): item is string => item.length > 0);

  if (cleaned.length === 0) {
    return undefined;
  }

  return Array.from(new Set(cleaned));
};

const buildSelectedPairLabels = (markets: string[]): string[] => {
  const labels: string[] = [];
  for (let i = 0; i < markets.length - 1; i += 1) {
    for (let j = i + 1; j < markets.length; j += 1) {
      labels.push(`${markets[i]}/${markets[j]}`);
    }
  }
  return labels;
};

const deriveMarketsFromPairLabels = (pairLabels: string[]): string[] => {
  const derived: string[] = [];
  const seen = new Set<string>();

  pairLabels.forEach((label) => {
    label
      .split('/')
      .map((item) => item.trim())
      .filter((item) => item.length > 0)
      .forEach((market) => {
        if (seen.has(market)) {
          return;
        }
        seen.add(market);
        derived.push(market);
      });
  });

  return derived;
};

export const normalizeBacktestPayload = (data: BacktestRequest): BacktestRequest => {
  const startDate = String(data.start_date || '').trim();
  const endDate = String(data.end_date || '').trim();

  if (!startDate || !endDate) {
    throw new Error('Backtest payload requires both start_date and end_date');
  }

  if (startDate > endDate) {
    throw new Error('Backtest payload has invalid date range: start_date is after end_date');
  }

  let dedupedPairs = normalizeStringList(data.pairs);
  let selectedPairLabels = normalizeStringList(data.selected_pairs);

  if ((!dedupedPairs || dedupedPairs.length === 0) && selectedPairLabels?.length) {
    dedupedPairs = deriveMarketsFromPairLabels(selectedPairLabels);
  }

  if ((!selectedPairLabels || selectedPairLabels.length === 0) && dedupedPairs?.length) {
    selectedPairLabels = buildSelectedPairLabels(dedupedPairs);
  }

  if (!dedupedPairs || dedupedPairs.length < 2) {
    throw new Error('Backtest payload requires at least two selected markets');
  }

  if (!selectedPairLabels || selectedPairLabels.length === 0) {
    throw new Error('Backtest payload requires selected_pairs');
  }

  const topLevelMode = data.pair_selection_mode;
  const incomingTradingParams =
    data.trading_parameters && typeof data.trading_parameters === 'object'
      ? { ...data.trading_parameters }
      : {};

  const normalizedPairSelectionMode = incomingTradingParams.pair_selection_mode || topLevelMode;

  const existingBenchmark =
    typeof incomingTradingParams.benchmark_symbol === 'string'
      ? incomingTradingParams.benchmark_symbol.trim()
      : typeof data.benchmark_symbol === 'string'
        ? data.benchmark_symbol.trim()
        : '';
  // benchmark_symbol is a performance-comparison reference (e.g. 'BTC-USD'), not a
  // trading market. It must never be derived from the selected pairs list.
  const normalizedBenchmarkSymbol = existingBenchmark || 'BTC-USD';

  const existingResolution =
    typeof incomingTradingParams.resolution === 'string' &&
    incomingTradingParams.resolution.length > 0
      ? incomingTradingParams.resolution
      : typeof incomingTradingParams.candle_resolution === 'string' &&
          incomingTradingParams.candle_resolution.length > 0
        ? incomingTradingParams.candle_resolution
        : undefined;
  const normalizedResolution = existingResolution
    ? normalizeDydxCandleResolution(existingResolution)
    : undefined;

  const normalizedTradingParameters: Record<string, unknown> = {
    ...incomingTradingParams,
    benchmark_symbol: normalizedBenchmarkSymbol,
    ...(normalizedResolution
      ? {
          resolution: normalizedResolution,
          candle_resolution: normalizedResolution,
        }
      : {}),
  };
  if (normalizedPairSelectionMode) {
    normalizedTradingParameters.pair_selection_mode = normalizedPairSelectionMode;
  }

  const normalizedPayload: BacktestRequest = {
    ...data,
    start_date: startDate,
    end_date: endDate,
    source: typeof data.source === 'string' && data.source.trim().length > 0 ? data.source : 'ui',
    trading_parameters: normalizedTradingParameters,
  };
  if (normalizedPairSelectionMode) {
    normalizedPayload.pair_selection_mode = normalizedPairSelectionMode;
  }

  if (dedupedPairs.length > 0) {
    normalizedPayload.pairs = dedupedPairs;
    const explicitMaxPairs = Number(data.max_pairs);
    if (Number.isFinite(explicitMaxPairs) && explicitMaxPairs > 0) {
      normalizedPayload.max_pairs = explicitMaxPairs;
    } else {
      normalizedPayload.max_pairs = dedupedPairs.length;
    }
  }

  normalizedPayload.selected_pairs = selectedPairLabels;

  return normalizedPayload;
};

export interface PerpetualMarketsResponse extends Record<string, unknown> {
  markets: string[];
  count: number;
  source: string;
  cache_stale?: boolean;
  static_fallback?: boolean;
  cache_hit?: boolean;
}

export interface ArbitragePairPriorityItem extends Record<string, unknown> {
  pair: string;
  base_market: string;
  quote_market: string;
  score: number;
  components: Record<string, number>;
  explanation: string[];
  enabled: boolean;
}

export interface ArbitragePairPriorityResponse extends Record<string, unknown> {
  pairs: ArbitragePairPriorityItem[];
  count: number;
  enabled: boolean;
}

export interface ArbitrageOpportunityExplainResponse extends Record<string, unknown> {
  opportunity_id: string;
  matched_rejection_reason?: { reason: string; count: number } | null;
  top_rejection_reasons?: Array<{ reason: string; count: number }>;
  counters?: Partial<ArbitrageMetricCounters>;
  feature_flags?: Record<string, boolean>;
  runtime_settings?: Record<string, boolean | number>;
  explainability_scope?: string;
  note?: string;
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
  selected_markets?: string[];
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

export type AIMarketProvider = 'openai' | 'deepseek' | 'claude';

export interface AIProviderStatus extends Record<string, unknown> {
  provider: AIMarketProvider;
  label?: string;
  enabled: boolean;
  available: boolean;
  availability_status: 'available' | 'disabled' | 'not_configured';
  unavailable_reason?: string;
  shared_key_available: boolean;
  user_key_available: boolean;
  user_key_masked?: string;
  active_key_source: 'user' | 'shared' | 'none';
  model: string;
}

export interface AIMarketStatusResponse extends Record<string, unknown> {
  providers: AIProviderStatus[];
}

export interface AIKeyPayload extends Record<string, unknown> {
  provider: AIMarketProvider;
  api_key: string;
  label?: string;
}

export interface AIMarketSelectionRequest extends Record<string, unknown> {
  provider: AIMarketProvider;
  mode: 'ai_recommended' | 'most_popular' | 'most_profitable' | 'top_20';
  markets?: string[];
  limit?: number;
  strategy?: string;
  criteria?: {
    objective?: string;
    volume_weight?: number;
    liquidity_weight?: number;
    tradeability_weight?: number;
    momentum_weight?: number;
    volatility_weight?: number;
    cointegration_weight?: number;
    risk_weight?: number;
    future_gainers?: boolean;
    notes?: string;
  };
}

export interface AIMarketSelectionResponse extends Record<string, unknown> {
  provider: AIMarketProvider;
  mode: string;
  source: string;
  selected_markets: string[];
  rationale: string;
  confidence: number;
  used_ai: boolean;
  fallback_reason?: string;
}

// ---- AI text-generation types ----

export interface AITextResponse extends Record<string, unknown> {
  provider: AIMarketProvider;
  content: string;
  used_ai: boolean;
}

export interface AIBacktestExplainRequest extends Record<string, unknown> {
  provider: AIMarketProvider;
  win_rate: number;
  total_pnl_usd: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  total_trades: number;
  profit_factor: number;
  markets: string[];
  start_date: string;
  end_date: string;
}

export interface AIBacktestSummary extends Record<string, unknown> {
  win_rate: number;
  total_pnl_usd: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  total_trades: number;
}

const toFiniteNumber = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return null;
};

export const toAIBacktestSummary = (value: Record<string, unknown>): AIBacktestSummary | null => {
  const winRate = toFiniteNumber(value.win_rate);
  const totalPnlUsd =
    toFiniteNumber(value.total_pnl_usd) ??
    toFiniteNumber(value.total_pnl) ??
    toFiniteNumber(value.pnl_usd);
  const sharpeRatio = toFiniteNumber(value.sharpe_ratio);
  const maxDrawdownPct =
    toFiniteNumber(value.max_drawdown_pct) ?? toFiniteNumber(value.max_drawdown);
  const totalTrades = toFiniteNumber(value.total_trades) ?? toFiniteNumber(value.trades_count);

  if (
    winRate === null &&
    totalPnlUsd === null &&
    sharpeRatio === null &&
    maxDrawdownPct === null &&
    totalTrades === null
  ) {
    return null;
  }

  return {
    win_rate: winRate ?? 0,
    total_pnl_usd: totalPnlUsd ?? 0,
    sharpe_ratio: sharpeRatio ?? 0,
    max_drawdown_pct: maxDrawdownPct ?? 0,
    total_trades: totalTrades ?? 0,
  };
};

export interface AISuggestParamsRequest extends Record<string, unknown> {
  provider: AIMarketProvider;
  strategy_name: string;
  current_params: Record<string, unknown>;
  last_error: string;
  recent_backtests: AIBacktestSummary[];
  max_suggestions?: number;
}

export interface AIRuntimeDigestRequest extends Record<string, unknown> {
  provider: AIMarketProvider;
  running_bots: number;
  total_bots: number;
  open_positions: number;
  total_pnl_usd: number;
  active_pairs: number;
  error_count: number;
  network: string;
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

export interface BacktestExperimentRunSummary extends Record<string, unknown> {
  run_id: string;
  status: string;
  created_at: string;
  completed_at?: string;
  total_trades: number;
  total_pnl_usd: number;
  win_rate?: number;
  variant?: string;
  compare_winner?: boolean;
}

export interface BacktestExperimentVariantSummary extends Record<string, unknown> {
  variant: string;
  run_count: number;
}

export interface BacktestExperimentGroup extends Record<string, unknown> {
  experiment_id: string;
  run_count: number;
  variant_count: number;
  created_at: string;
  latest_created_at: string;
  latest_status: string;
  variants: BacktestExperimentVariantSummary[];
  runs: BacktestExperimentRunSummary[];
}

export interface BacktestExperimentsResponse extends Record<string, unknown> {
  experiments: BacktestExperimentGroup[];
  count: number;
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
  trades_executed?: number;
  pnl?: number;
  win_rate?: number;
  open_positions?: number;
  uptime_seconds?: number;
  last_error?: string;
  started_at?: string;
  stopped_at?: string;
  runtime_updated_at?: string;
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
    const canonicalResolution = normalizeDydxCandleResolution(resolvedResolution);
    normalized.resolution = canonicalResolution;
    normalized.candle_resolution = canonicalResolution;
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
  const canonicalResolution = resolution ? normalizeDydxCandleResolution(resolution) : undefined;

  return {
    ...strategy,
    ...(canonicalResolution
      ? { resolution: canonicalResolution, candle_resolution: canonicalResolution }
      : {}),
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

type RequestConfigWithAuthControl = {
  _skipAuthHeader?: boolean;
  _allowAccessTokenFallback?: boolean;
  headers?: AxiosRequestHeaders | Record<string, string>;
  url?: string;
};

class ApiClient {
  private client: AxiosInstance;
  private accessToken: string | null = null;
  private sessionEstablished: boolean = false;
  private isRefreshing: boolean = false;
  private activeRefreshPromise: Promise<Token> | null = null;
  private pendingRequests: PendingRequest[] = [];
  private refreshBlockedUntil: number = 0;
  private readonly refreshFailureCooldownMs: number = 10000;

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
      // Load persisted token for session recovery after page refresh
      this.loadTokenFromStorage();
    }

    // Request interceptor: browser auth is carried by the HttpOnly session cookie.
    this.client.interceptors.request.use((config) => {
      config.headers ??= {} as AxiosRequestHeaders;
      const headers = config.headers as AxiosRequestHeaders;
      attachTraceHeader(headers as Record<string, string>);

      const authControlledConfig = config as typeof config & RequestConfigWithAuthControl;
      const skipAuthHeader = authControlledConfig._skipAuthHeader === true;
      const allowAccessTokenFallback = authControlledConfig._allowAccessTokenFallback === true;

      if (skipAuthHeader && !(allowAccessTokenFallback && this.accessToken)) {
        delete (headers as Record<string, string>).Authorization;
        return config;
      }

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
          !url.includes('/auth/logout') &&
          !url.includes('/auth/refresh') &&
          !url.includes('/auth/registration-status') &&
          !url.includes('/public/app-config')
        ) {
          if (!this.shouldAttemptCookieRefresh()) {
            return Promise.reject(error);
          }

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
              } else if (!newAccessToken && error.config.headers) {
                // Session-only refresh (no new JWT) — clear stale Bearer token so
                // the retry relies on the HttpOnly session cookie instead.
                delete (error.config.headers as Record<string, string>)['Authorization'];
              }
              return this.client(error.config);
            }
          } catch (refreshError: unknown) {
            // Refresh failed. Only force logout when refresh explicitly says
            // the session is unauthorized/forbidden; otherwise surface error
            // without bouncing the user to login.
            const errorMsg =
              refreshError instanceof Error ? refreshError.message : String(refreshError);
            const refreshStatus =
              axios.isAxiosError(refreshError) && refreshError.response
                ? refreshError.response.status
                : null;
            const shouldExpireSession = refreshStatus === 401 || refreshStatus === 403;
            console.error('❌ api.ts: Token refresh failed', errorMsg);
            this.notifyRefreshFailure(refreshError);
            if (shouldExpireSession && typeof window !== 'undefined') {
              window.dispatchEvent(
                new CustomEvent('auth:session-expired', {
                  detail: { reason: errorMsg },
                })
              );
            } else {
              console.warn(
                '⚠️ api.ts: Refresh failed without auth-invalid status; preserving current session UI state',
                { refreshStatus }
              );
              if (typeof window !== 'undefined') {
                window.dispatchEvent(
                  new CustomEvent('auth:refresh-warning', {
                    detail: {
                      reason: errorMsg,
                      status: refreshStatus,
                    },
                  })
                );
              }
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
    this.markSessionEstablished();
    // Persist token to localStorage for recovery after page refresh
    if (typeof localStorage !== 'undefined') {
      try {
        localStorage.setItem('_dydx_access_token', token);
      } catch (e) {
        console.warn('❌ api.ts: Failed to persist token to localStorage', e);
      }
    }
  }

  private markSessionEstablished(): void {
    this.sessionEstablished = true;
    if (typeof localStorage !== 'undefined') {
      try {
        localStorage.setItem(SESSION_HINT_KEY, 'true');
      } catch (e) {
        console.warn('❌ api.ts: Failed to persist session hint', e);
      }
    }
  }

  hasSessionHint(): boolean {
    if (this.sessionEstablished) {
      return true;
    }

    if (typeof localStorage === 'undefined') {
      return false;
    }

    try {
      return localStorage.getItem(SESSION_HINT_KEY) === 'true';
    } catch (e) {
      console.warn('❌ api.ts: Failed to read session hint', e);
      return false;
    }
  }

  markSessionEstablishedForCookieAuth(): void {
    this.markSessionEstablished();
  }

  shouldAttemptCookieRefresh(): boolean {
    return this.hasSessionHint() || shouldAttemptCookieSessionBootstrap(API_BASE_URL);
  }

  getAccessToken(): string | null {
    return this.accessToken;
  }

  private loadTokenFromStorage(): void {
    if (typeof localStorage !== 'undefined') {
      try {
        const storedToken = localStorage.getItem('_dydx_access_token');
        if (storedToken) {
          this.accessToken = storedToken;
          this.markSessionEstablished();
        }
      } catch (e) {
        console.warn('❌ api.ts: Failed to load token from localStorage', e);
      }
    }
  }

  async refreshAccessToken(): Promise<Token> {
    if (this.activeRefreshPromise) {
      return this.activeRefreshPromise;
    }

    if (Date.now() < this.refreshBlockedUntil) {
      const remainingMs = this.refreshBlockedUntil - Date.now();
      console.debug(
        `🔐 api.ts: refresh attempt suppressed by cooldown (${Math.max(0, remainingMs)}ms remaining)`
      );
      throw new Error('Refresh temporarily blocked after previous failure');
    }

    this.activeRefreshPromise = (async () => {
      let refreshResponse;
      try {
        refreshResponse = await axios.post<ApiResponse<Token> | Token>(
          `${API_BASE_URL}/api/v1/auth/refresh`,
          {},
          {
            withCredentials: true,
            timeout: 4000,
            headers: {
              'Content-Type': 'application/json',
              [traceHeaderName]: attachTraceHeader({}),
            },
          }
        );
      } catch (error) {
        this.refreshBlockedUntil = Date.now() + this.refreshFailureCooldownMs;
        this.accessToken = null;
        this.sessionEstablished = false;
        if (typeof localStorage !== 'undefined') {
          try {
            localStorage.removeItem('_dydx_access_token');
            localStorage.removeItem(SESSION_HINT_KEY);
          } catch (e) {
            console.warn('❌ api.ts: Failed to clear stale session hints after refresh failure', e);
          }
        }
        throw error;
      }

      const refreshPayload = (refreshResponse.data as ApiResponse<Token>)?.data
        ? (refreshResponse.data as ApiResponse<Token>).data
        : (refreshResponse.data as Token);

      if (!refreshPayload) {
        throw new Error('Refresh endpoint did not return a session payload');
      }

      this.refreshBlockedUntil = 0;
      this.markSessionEstablished();
      if (refreshPayload.access_token) {
        this.setToken(refreshPayload.access_token);
      } else {
        // Session-only refresh response — clear any stale JWT so requests
        // fall back to HttpOnly cookie auth rather than sending an expired token.
        this.accessToken = null;
        if (typeof localStorage !== 'undefined') {
          try {
            localStorage.removeItem('_dydx_access_token');
          } catch (_e) {
            // ignore
          }
        }
      }

      return refreshPayload;
    })();

    try {
      return await this.activeRefreshPromise;
    } finally {
      this.activeRefreshPromise = null;
    }
  }

  hasRefreshToken(): boolean {
    return this.sessionEstablished;
  }

  async restoreSession(options: { allowCookieRefresh?: boolean } = {}): Promise<boolean> {
    try {
      // Attempt to load token from localStorage first (recovery after page refresh)
      this.loadTokenFromStorage();
      // If we already have a valid in-memory access token, skip the refresh round-trip.
      if (this.accessToken && this.sessionEstablished) {
        return true;
      }

      if (!(options.allowCookieRefresh ?? this.shouldAttemptCookieRefresh())) {
        return false;
      }

      // Token not in storage, attempt to refresh via HttpOnly session cookie
      await this.refreshAccessToken();
      return true;
    } catch {
      // Clear any stale token from localStorage if refresh fails
      if (typeof localStorage !== 'undefined') {
        try {
          localStorage.removeItem('_dydx_access_token');
          localStorage.removeItem(SESSION_HINT_KEY);
        } catch (e) {
          console.warn('❌ api.ts: Failed to clear token from localStorage', e);
        }
      }
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

    // Clear persisted token from localStorage
    if (typeof localStorage !== 'undefined') {
      try {
        localStorage.removeItem('_dydx_access_token');
        localStorage.removeItem(SESSION_HINT_KEY);
      } catch (e) {
        console.warn('❌ api.ts: Failed to clear token from localStorage during logout', e);
      }
    }

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

  async getPublicAppConfig(): Promise<ApiResponse<PublicAppConfigResponse>> {
    const response = await this.client.get<ApiResponse<PublicAppConfigResponse>>(
      '/api/v1/public/app-config'
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
        this.markSessionEstablished();
      }
      if (payload && payload.access_token) {
        this.setToken(payload.access_token);
      } else {
        // Cookie-session mode (no access_token in login payload): ensure we
        // don't keep sending a stale Bearer token from a previous session.
        this.accessToken = null;
        if (typeof localStorage !== 'undefined') {
          try {
            localStorage.removeItem('_dydx_access_token');
          } catch (_e) {
            // best effort
          }
        }
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
      '/api/v1/users/me',
      {
        _skipAuthHeader: true,
        _allowAccessTokenFallback: true,
      } as RequestConfigWithAuthControl
    );
    const payload = response.data as ApiResponse<UserProfile> | UserProfile;

    if (payload && typeof payload === 'object' && 'success' in payload && 'message' in payload) {
      this.markSessionEstablishedForCookieAuth();
      return payload as ApiResponse<UserProfile>;
    }

    this.markSessionEstablishedForCookieAuth();

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

  async listBacktestExperiments(
    limit: number = 100,
    runLimit: number = 500
  ): Promise<ApiResponse<BacktestExperimentsResponse>> {
    this.ensureTokenLoaded();
    const safeLimit = Number.isFinite(limit) && limit > 0 ? Math.floor(limit) : 100;
    const safeRunLimit = Number.isFinite(runLimit) && runLimit > 0 ? Math.floor(runLimit) : 500;
    const response = await this.client.get<ApiResponse<BacktestExperimentsResponse>>(
      `/api/v1/backtests/experiments?limit=${safeLimit}&run_limit=${safeRunLimit}`
    );
    return response.data;
  }

  async getBacktest(runId: string): Promise<ApiResponse<BacktestDetailsResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse<BacktestDetailsResponse>>(
      `/api/v1/backtests/${runId}`,
      { timeout: 12000 }
    );
    return response.data;
  }

  async listBacktestsByStrategy(
    strategyId: number,
    limit: number = 10
  ): Promise<ApiResponse<BacktestListResponse>> {
    this.ensureTokenLoaded();
    const safeLimit = Number.isFinite(limit) && limit > 0 ? Math.floor(limit) : 10;
    const response = await this.client.get<ApiResponse<BacktestListResponse>>(
      `/api/v1/backtests?strategy_id=${strategyId}&limit=${safeLimit}`
    );
    return response.data;
  }

  async runBacktest(data: BacktestRequest): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const normalizedPayload = normalizeBacktestPayload(data);
    const response = await this.client.post('/api/v1/backtests/run', normalizedPayload);
    guardRunBacktestContract(response.data);
    return response.data;
  }

  async getPerpetualMarkets(limit: number = 0): Promise<ApiResponse<PerpetualMarketsResponse>> {
    this.ensureTokenLoaded();
    const query = limit > 0 ? `?limit=${encodeURIComponent(String(limit))}` : '';
    const response = await this.client.get<ApiResponse<PerpetualMarketsResponse>>(
      `/api/v1/markets/perpetuals${query}`
    );
    const headerValue = (name: string): string => {
      const raw = response.headers?.[name];
      if (typeof raw === 'string') {
        return raw;
      }
      if (Array.isArray(raw) && raw.length > 0) {
        return String(raw[0]);
      }
      return '';
    };

    const isHeaderEnabled = (name: string): boolean => {
      const value = headerValue(name).trim().toLowerCase();
      return value === '1' || value === 'true' || value === 'yes' || value === 'on';
    };

    const payload = response.data;
    const marketsData = payload?.data as PerpetualMarketsResponse | undefined;
    const source = String(marketsData?.source || '')
      .trim()
      .toLowerCase();
    const normalizedMarkets = Array.isArray(marketsData?.markets)
      ? marketsData.markets
      : ([] as string[]);
    const normalizedCount =
      typeof marketsData?.count === 'number' && Number.isFinite(marketsData.count)
        ? marketsData.count
        : normalizedMarkets.length;
    const normalizedSource =
      typeof marketsData?.source === 'string' && marketsData.source.trim().length > 0
        ? marketsData.source
        : 'unknown';

    return {
      ...payload,
      data: {
        ...(marketsData || {}),
        markets: normalizedMarkets,
        count: normalizedCount,
        source: normalizedSource,
        cache_hit: isHeaderEnabled('x-cache-hit'),
        cache_stale: isHeaderEnabled('x-cache-stale') || source === 'cache_stale',
        static_fallback: isHeaderEnabled('x-markets-fallback') || source === 'static_fallback',
      },
    };
  }

  async getArbitrageImprovementMetrics(): Promise<
    ApiResponse<ArbitrageImprovementMetricsResponse>
  > {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse<ArbitrageImprovementMetricsResponse>>(
      '/api/v1/arbitrage/improvement-metrics'
    );
    return response.data;
  }

  async getArbitragePairPriority(
    limit: number = 12
  ): Promise<ApiResponse<ArbitragePairPriorityResponse>> {
    this.ensureTokenLoaded();
    const query = limit > 0 ? `?limit=${encodeURIComponent(String(limit))}` : '';
    const response = await this.client.get<ApiResponse<ArbitragePairPriorityResponse>>(
      `/api/v1/arbitrage/pair-priority${query}`
    );
    return response.data;
  }

  async getArbitrageOpportunityExplain(
    opportunityId: string
  ): Promise<ApiResponse<ArbitrageOpportunityExplainResponse>> {
    this.ensureTokenLoaded();
    const safeId = encodeURIComponent(String(opportunityId || '').trim());
    const response = await this.client.get<ApiResponse<ArbitrageOpportunityExplainResponse>>(
      `/api/v1/arbitrage/opportunity/${safeId}/explain`
    );
    return response.data;
  }

  async getArbitrageRuntimeSettings(): Promise<ArbitrageRuntimeSettingsResponse> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ArbitrageRuntimeSettingsResponse>(
      '/api/v1/settings/arbitrage-runtime'
    );
    return response.data;
  }

  async updateArbitrageRuntimeSettings(
    settings: Partial<ArbitrageRuntimeSettings>
  ): Promise<ArbitrageRuntimeSettingsResponse> {
    this.ensureTokenLoaded();
    const response = await this.client.put<ArbitrageRuntimeSettingsResponse>(
      '/api/v1/settings/arbitrage-runtime',
      { settings }
    );
    return response.data;
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

  async listCeleryTasks(params?: {
    status?: string;
    task_name?: string;
    queue?: string;
    strategy_id?: string;
    backtest_run_id?: string;
    bot_id?: string;
    environment?: string;
  }): Promise<ApiResponse<CeleryTasksResponse>> {
    this.ensureTokenLoaded();
    const search = new URLSearchParams();
    Object.entries(params || {}).forEach(([key, value]) => {
      if (value) search.set(key, value);
    });
    const query = search.toString();
    const response = await this.client.get<ApiResponse<CeleryTasksResponse>>(
      `/api/v1/celery/tasks${query ? `?${query}` : ''}`
    );
    return response.data;
  }

  async getCeleryTask(taskId: string): Promise<ApiResponse<{ task: CeleryTask }>> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse<{ task: CeleryTask }>>(
      `/api/v1/celery/tasks/${encodeURIComponent(taskId)}`
    );
    return response.data;
  }

  async revokeCeleryTask(
    taskId: string,
    terminate = false
  ): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response = await this.client.post<ApiResponse<Record<string, unknown>>>(
      `/api/v1/celery/tasks/${encodeURIComponent(taskId)}/revoke`,
      { terminate }
    );
    return response.data;
  }

  async retryCeleryTask(taskId: string): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response = await this.client.post<ApiResponse<Record<string, unknown>>>(
      `/api/v1/celery/tasks/${encodeURIComponent(taskId)}/retry`
    );
    return response.data;
  }

  async getCeleryWorkers(): Promise<ApiResponse<CeleryWorkersResponse>> {
    this.ensureTokenLoaded();
    const response =
      await this.client.get<ApiResponse<CeleryWorkersResponse>>('/api/v1/celery/workers');
    return response.data;
  }

  async getCeleryQueues(): Promise<ApiResponse<CeleryQueuesResponse>> {
    this.ensureTokenLoaded();
    const response =
      await this.client.get<ApiResponse<CeleryQueuesResponse>>('/api/v1/celery/queues');
    return response.data;
  }

  async getCeleryHealth(): Promise<ApiResponse<CeleryHealthResponse>> {
    this.ensureTokenLoaded();
    const response =
      await this.client.get<ApiResponse<CeleryHealthResponse>>('/api/v1/celery/health');
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
      `/api/v1/backtests/${runId}/status`,
      { timeout: 8000 }
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

  private shouldUseLegacyRouteFallback(error: unknown): boolean {
    if (!(error instanceof AxiosError)) {
      return false;
    }
    const status = error.response?.status;
    return status === 404 || status === 405 || status === 501;
  }

  private logLegacyRouteFallback(
    primaryRoute: string,
    fallbackRoute: string,
    error: unknown
  ): void {
    if (!import.meta.env.DEV) {
      return;
    }

    const debugLegacyFallbacks = String(import.meta.env.VITE_DEBUG_LEGACY_FALLBACKS || '')
      .trim()
      .toLowerCase();
    if (
      debugLegacyFallbacks !== 'true' &&
      debugLegacyFallbacks !== '1' &&
      debugLegacyFallbacks !== 'yes'
    ) {
      return;
    }

    const status = error instanceof AxiosError ? error.response?.status : undefined;
    console.warn('⚠️ api.ts: Legacy route fallback engaged', {
      primaryRoute,
      fallbackRoute,
      status,
    });
  }

  async listAdminUsers(): Promise<ApiResponse<AdminUserListResponse>> {
    try {
      const response = await this.client.get<ApiResponse<AdminUserListResponse>>(
        '/api/v1/backoffice/users'
      );
      return response.data;
    } catch (error: unknown) {
      if (!this.shouldUseLegacyRouteFallback(error)) {
        throw error;
      }
      this.logLegacyRouteFallback('/api/v1/backoffice/users', '/api/v1/admin/users', error);
      const fallback =
        await this.client.get<ApiResponse<AdminUserListResponse>>('/api/v1/admin/users');
      return fallback.data;
    }
  }

  async getAccessControl(): Promise<ApiResponse<AccessControlResponse>> {
    try {
      const response = await this.client.get<ApiResponse<AccessControlResponse>>(
        '/api/v1/backoffice/access-control'
      );
      return response.data;
    } catch (error: unknown) {
      if (!this.shouldUseLegacyRouteFallback(error)) {
        throw error;
      }
      this.logLegacyRouteFallback(
        '/api/v1/backoffice/access-control',
        '/api/v1/admin/access-control',
        error
      );
      const fallback = await this.client.get<ApiResponse<AccessControlResponse>>(
        '/api/v1/admin/access-control'
      );
      return fallback.data;
    }
  }

  async createCustomRole(
    data: CreateCustomRolePayload
  ): Promise<ApiResponse<AccessControlResponse>> {
    try {
      const response = await this.client.post<ApiResponse<AccessControlResponse>>(
        '/api/v1/backoffice/roles',
        data
      );
      return response.data;
    } catch (error: unknown) {
      if (!this.shouldUseLegacyRouteFallback(error)) {
        throw error;
      }
      this.logLegacyRouteFallback('/api/v1/backoffice/roles', '/api/v1/admin/roles', error);
      const fallback = await this.client.post<ApiResponse<AccessControlResponse>>(
        '/api/v1/admin/roles',
        data
      );
      return fallback.data;
    }
  }

  async updateRolePermissions(
    role: string,
    permissionKeys: string[]
  ): Promise<ApiResponse<AccessControlResponse>> {
    const encodedRole = encodeURIComponent(role);
    try {
      const response = await this.client.put<ApiResponse<AccessControlResponse>>(
        `/api/v1/backoffice/roles/${encodedRole}/permissions`,
        { permission_keys: permissionKeys }
      );
      return response.data;
    } catch (error: unknown) {
      if (!this.shouldUseLegacyRouteFallback(error)) {
        throw error;
      }
      this.logLegacyRouteFallback(
        `/api/v1/backoffice/roles/${encodedRole}/permissions`,
        `/api/v1/admin/roles/${encodedRole}/permissions`,
        error
      );
      const fallback = await this.client.put<ApiResponse<AccessControlResponse>>(
        `/api/v1/admin/roles/${encodedRole}/permissions`,
        { permission_keys: permissionKeys }
      );
      return fallback.data;
    }
  }

  async deleteCustomRole(role: string): Promise<ApiResponse<AccessControlResponse>> {
    const encodedRole = encodeURIComponent(role);
    try {
      const response = await this.client.delete<ApiResponse<AccessControlResponse>>(
        `/api/v1/backoffice/roles/${encodedRole}`
      );
      return response.data;
    } catch (error: unknown) {
      if (!this.shouldUseLegacyRouteFallback(error)) {
        throw error;
      }
      this.logLegacyRouteFallback(
        `/api/v1/backoffice/roles/${encodedRole}`,
        `/api/v1/admin/roles/${encodedRole}`,
        error
      );
      const fallback = await this.client.delete<ApiResponse<AccessControlResponse>>(
        `/api/v1/admin/roles/${encodedRole}`
      );
      return fallback.data;
    }
  }

  async getAdminUser(userId: number): Promise<ApiResponse<{ user: AdminUser }>> {
    try {
      const response = await this.client.get<ApiResponse<{ user: AdminUser }>>(
        `/api/v1/backoffice/users/${userId}`
      );
      return response.data;
    } catch (error: unknown) {
      if (!this.shouldUseLegacyRouteFallback(error)) {
        throw error;
      }
      this.logLegacyRouteFallback(
        `/api/v1/backoffice/users/${userId}`,
        `/api/v1/admin/users/${userId}`,
        error
      );
      const fallback = await this.client.get<ApiResponse<{ user: AdminUser }>>(
        `/api/v1/admin/users/${userId}`
      );
      return fallback.data;
    }
  }

  async createAdminUser(
    data: CreateAdminUserPayload
  ): Promise<ApiResponse<{ user: AdminUser; roles: string[]; onboarding_notice?: string }>> {
    try {
      const response = await this.client.post<
        ApiResponse<{ user: AdminUser; roles: string[]; onboarding_notice?: string }>
      >('/api/v1/backoffice/users', data);
      return response.data;
    } catch (error: unknown) {
      if (!this.shouldUseLegacyRouteFallback(error)) {
        throw error;
      }
      this.logLegacyRouteFallback('/api/v1/backoffice/users', '/api/v1/admin/users', error);
      const fallback = await this.client.post<
        ApiResponse<{ user: AdminUser; roles: string[]; onboarding_notice?: string }>
      >('/api/v1/admin/users', data);
      return fallback.data;
    }
  }

  async updateAdminUserRole(
    userId: number,
    role: string
  ): Promise<ApiResponse<{ user: AdminUser; roles: string[] }>> {
    try {
      const response = await this.client.put<ApiResponse<{ user: AdminUser; roles: string[] }>>(
        `/api/v1/backoffice/users/${userId}/role`,
        { role }
      );
      return response.data;
    } catch (error: unknown) {
      if (!this.shouldUseLegacyRouteFallback(error)) {
        throw error;
      }
      this.logLegacyRouteFallback(
        `/api/v1/backoffice/users/${userId}/role`,
        `/api/v1/admin/users/${userId}`,
        error
      );
      const fallback = await this.client.put<ApiResponse<{ user: AdminUser; roles: string[] }>>(
        `/api/v1/admin/users/${userId}`,
        { role }
      );
      return fallback.data;
    }
  }

  async updateAdminUserStatus(
    userId: number,
    isActive: boolean
  ): Promise<ApiResponse<{ user: AdminUser; roles: string[] }>> {
    try {
      const response = await this.client.put<ApiResponse<{ user: AdminUser; roles: string[] }>>(
        `/api/v1/backoffice/users/${userId}/status`,
        { is_active: isActive }
      );
      return response.data;
    } catch (error: unknown) {
      if (!this.shouldUseLegacyRouteFallback(error)) {
        throw error;
      }
      this.logLegacyRouteFallback(
        `/api/v1/backoffice/users/${userId}/status`,
        `/api/v1/admin/users/${userId}`,
        error
      );
      const fallback = await this.client.put<ApiResponse<{ user: AdminUser; roles: string[] }>>(
        `/api/v1/admin/users/${userId}`,
        { is_active: isActive }
      );
      return fallback.data;
    }
  }

  async resetAdminUserPassword(
    userId: number,
    password?: string
  ): Promise<ApiResponse<{ user: AdminUser; temporary_password?: string; notice: string }>> {
    const response = await this.client.post<
      ApiResponse<{ user: AdminUser; temporary_password?: string; notice: string }>
    >(`/api/v1/backoffice/users/${userId}/reset-password`, password ? { password } : {});
    return response.data;
  }

  async updateAdminUser(
    userId: number,
    data: UpdateAdminUserPayload
  ): Promise<ApiResponse<{ user: AdminUser; roles: string[] }>> {
    try {
      const response = await this.client.put<ApiResponse<{ user: AdminUser; roles: string[] }>>(
        `/api/v1/backoffice/users/${userId}`,
        data
      );
      return response.data;
    } catch (error: unknown) {
      if (!this.shouldUseLegacyRouteFallback(error)) {
        throw error;
      }
      this.logLegacyRouteFallback(
        `/api/v1/backoffice/users/${userId}`,
        `/api/v1/admin/users/${userId}`,
        error
      );
      const fallback = await this.client.put<ApiResponse<{ user: AdminUser; roles: string[] }>>(
        `/api/v1/admin/users/${userId}`,
        data
      );
      return fallback.data;
    }
  }

  async resetAdminUserMFA(userId: number): Promise<ApiResponse<ResetAdminUserMFAResponse>> {
    try {
      const response = await this.client.post<ApiResponse<ResetAdminUserMFAResponse>>(
        `/api/v1/backoffice/users/${userId}/reset-mfa`,
        {}
      );
      return response.data;
    } catch (error: unknown) {
      if (!this.shouldUseLegacyRouteFallback(error)) {
        throw error;
      }
      this.logLegacyRouteFallback(
        `/api/v1/backoffice/users/${userId}/reset-mfa`,
        `/api/v1/admin/users/${userId}/reset-mfa`,
        error
      );
      const fallback = await this.client.post<ApiResponse<ResetAdminUserMFAResponse>>(
        `/api/v1/admin/users/${userId}/reset-mfa`,
        {}
      );
      return fallback.data;
    }
  }

  async initializeSettings(): Promise<ApiResponse> {
    const response = await this.client.post<ApiResponse>('/api/v1/settings/initialize', {});
    return response.data;
  }

  async listIBInvitationTokens(
    limit: number = 100,
    offset: number = 0
  ): Promise<ApiResponse<IBInvitationTokenListResponse>> {
    const base = getCurrentPortalType() === 'ib' ? '/api/v1/ib' : '/api/v1/admin/ib';
    const response = await this.client.get<ApiResponse<IBInvitationTokenListResponse>>(
      `${base}/invitations?limit=${limit}&offset=${offset}`
    );
    return response.data;
  }

  async createIBInvitationToken(
    payload: CreateIBInvitationTokenPayload
  ): Promise<ApiResponse<{ token: IBInvitationToken }>> {
    const base = getCurrentPortalType() === 'ib' ? '/api/v1/ib' : '/api/v1/admin/ib';
    const response = await this.client.post<ApiResponse<{ token: IBInvitationToken }>>(
      `${base}/invitations`,
      payload
    );
    return response.data;
  }

  async revokeIBInvitationToken(tokenCode: string): Promise<ApiResponse<Record<string, unknown>>> {
    const base = getCurrentPortalType() === 'ib' ? '/api/v1/ib' : '/api/v1/admin/ib';
    const response = await this.client.post<ApiResponse<Record<string, unknown>>>(
      `${base}/invitations/${encodeURIComponent(tokenCode)}/revoke`,
      {}
    );
    return response.data;
  }

  async getPortalOverview(): Promise<ApiResponse<PortalOverviewResponse>> {
    const response =
      await this.client.get<ApiResponse<PortalOverviewResponse>>('/api/v1/portal/overview');
    return response.data;
  }

  async getIBDashboard(): Promise<ApiResponse<PortalOverviewResponse>> {
    try {
      const response =
        await this.client.get<ApiResponse<PortalOverviewResponse>>('/api/v1/ib/dashboard');
      return response.data;
    } catch (error: unknown) {
      if (!this.shouldUseLegacyRouteFallback(error)) {
        throw error;
      }
      this.logLegacyRouteFallback('/api/v1/ib/dashboard', '/api/v1/portal/overview', error);
      const fallback =
        await this.client.get<ApiResponse<PortalOverviewResponse>>('/api/v1/portal/overview');
      return fallback.data;
    }
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
    try {
      const response = await this.client.get<ApiResponse<CRMSummaryResponse>>(
        '/api/v1/backoffice/crm/summary'
      );
      return response.data;
    } catch (error: unknown) {
      if (!this.shouldUseLegacyRouteFallback(error)) {
        throw error;
      }
      this.logLegacyRouteFallback(
        '/api/v1/backoffice/crm/summary',
        '/api/v1/admin/crm/summary',
        error
      );
      const fallback = await this.client.get<ApiResponse<CRMSummaryResponse>>(
        '/api/v1/admin/crm/summary'
      );
      return fallback.data;
    }
  }

  async getBotAPIStats(): Promise<ApiResponse<BotAPIStatsResponse>> {
    try {
      const response = await this.client.get<ApiResponse<BotAPIStatsResponse>>(
        '/api/v1/admin/bot-api-stats'
      );
      return response.data;
    } catch (error: unknown) {
      if (!this.shouldUseLegacyRouteFallback(error)) {
        throw error;
      }
      this.logLegacyRouteFallback(
        '/api/v1/admin/bot-api-stats',
        '/api/v1/backoffice/bot-api-stats',
        error
      );
      const fallback = await this.client.get<ApiResponse<BotAPIStatsResponse>>(
        '/api/v1/backoffice/bot-api-stats'
      );
      return fallback.data;
    }
  }

  async getCRMUsersTable(): Promise<ApiResponse<CRMUsersTableResponse>> {
    try {
      const response = await this.client.get<ApiResponse<CRMUsersTableResponse>>(
        '/api/v1/backoffice/crm/clients'
      );
      return response.data;
    } catch (error: unknown) {
      if (!this.shouldUseLegacyRouteFallback(error)) {
        throw error;
      }
      this.logLegacyRouteFallback(
        '/api/v1/backoffice/crm/clients',
        '/api/v1/admin/crm/users',
        error
      );
      const fallback =
        await this.client.get<ApiResponse<CRMUsersTableResponse>>('/api/v1/admin/crm/users');
      return fallback.data;
    }
  }

  async getCRMHierarchyTable(): Promise<ApiResponse<PartnerHierarchyResponse>> {
    try {
      const response = await this.client.get<ApiResponse<PartnerHierarchyResponse>>(
        '/api/v1/backoffice/crm/hierarchy'
      );
      return response.data;
    } catch (error: unknown) {
      if (!this.shouldUseLegacyRouteFallback(error)) {
        throw error;
      }
      this.logLegacyRouteFallback(
        '/api/v1/backoffice/crm/hierarchy',
        '/api/v1/admin/crm/hierarchy',
        error
      );
      const fallback = await this.client.get<ApiResponse<PartnerHierarchyResponse>>(
        '/api/v1/admin/crm/hierarchy'
      );
      return fallback.data;
    }
  }

  async getCRMSecurityEvents(
    limit: number = 50,
    offset: number = 0
  ): Promise<ApiResponse<CRMSecurityEventsResponse>> {
    try {
      const response = await this.client.get<ApiResponse<CRMSecurityEventsResponse>>(
        `/api/v1/backoffice/crm/security-events?limit=${limit}&offset=${offset}`
      );
      return response.data;
    } catch (error: unknown) {
      if (!this.shouldUseLegacyRouteFallback(error)) {
        throw error;
      }
      this.logLegacyRouteFallback(
        '/api/v1/backoffice/crm/security-events',
        '/api/v1/admin/crm/security-events',
        error
      );
      const fallback = await this.client.get<ApiResponse<CRMSecurityEventsResponse>>(
        `/api/v1/admin/crm/security-events?limit=${limit}&offset=${offset}`
      );
      return fallback.data;
    }
  }

  async reviewPartnerApplication(
    applicationId: number,
    payload: ReviewPartnerApplicationPayload
  ): Promise<ApiResponse<{ application: PartnerApplication }>> {
    try {
      const response = await this.client.post<ApiResponse<{ application: PartnerApplication }>>(
        `/api/v1/backoffice/crm/applications/${applicationId}/review`,
        payload
      );
      return response.data;
    } catch (error: unknown) {
      if (!this.shouldUseLegacyRouteFallback(error)) {
        throw error;
      }
      this.logLegacyRouteFallback(
        `/api/v1/backoffice/crm/applications/${applicationId}/review`,
        `/api/v1/admin/crm/applications/${applicationId}/review`,
        error
      );
      const fallback = await this.client.post<ApiResponse<{ application: PartnerApplication }>>(
        `/api/v1/admin/crm/applications/${applicationId}/review`,
        payload
      );
      return fallback.data;
    }
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
    try {
      const response = await this.client.put<ApiResponse<{ metric: PartnerCommissionMetric }>>(
        `/api/v1/backoffice/crm/commission-metrics/${userId}`,
        payload
      );
      return response.data;
    } catch (error: unknown) {
      if (!this.shouldUseLegacyRouteFallback(error)) {
        throw error;
      }
      this.logLegacyRouteFallback(
        `/api/v1/backoffice/crm/commission-metrics/${userId}`,
        `/api/v1/admin/crm/commission-metrics/${userId}`,
        error
      );
      const fallback = await this.client.put<ApiResponse<{ metric: PartnerCommissionMetric }>>(
        `/api/v1/admin/crm/commission-metrics/${userId}`,
        payload
      );
      return fallback.data;
    }
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
    endDate?: string,
    resolution?: '1min' | '1hour'
  ): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    const params = new URLSearchParams();
    if (market) params.append('market', market);
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    if (resolution) params.append('resolution', resolution);

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

  private buildBacktestAnalyticsSummaryFromAnalytics(
    runId: string,
    analyticsResponse: ApiResponse
  ): ApiResponse {
    const data =
      analyticsResponse &&
      typeof analyticsResponse === 'object' &&
      analyticsResponse.data &&
      typeof analyticsResponse.data === 'object'
        ? analyticsResponse.data
        : {};

    const numericValue = (...candidates: unknown[]): number | undefined => {
      for (const candidate of candidates) {
        if (typeof candidate === 'number' && Number.isFinite(candidate)) {
          return candidate;
        }
      }
      return undefined;
    };

    const winRateCandidate = numericValue(
      (data as Record<string, unknown>).win_rate,
      (data as Record<string, unknown>).winRate
    );
    const normalizedWinRate =
      typeof winRateCandidate === 'number'
        ? winRateCandidate >= 0 && winRateCandidate <= 1
          ? winRateCandidate * 100
          : winRateCandidate
        : 0;

    const tradesFromArray = Array.isArray((data as Record<string, unknown>).trades)
      ? ((data as Record<string, unknown>).trades as unknown[]).length
      : 0;
    const totalTrades =
      numericValue(
        (data as Record<string, unknown>).total_trades,
        (data as Record<string, unknown>).totalTrades
      ) ?? tradesFromArray;
    const totalPnlUsd =
      numericValue(
        (data as Record<string, unknown>).total_pnl_usd,
        (data as Record<string, unknown>).total_pnl
      ) ?? 0;

    return {
      success: true,
      message: analyticsResponse.message || 'Backtest analytics summary fetched successfully',
      data: {
        run_id: String((data as Record<string, unknown>).run_id || runId),
        total_pnl_usd: totalPnlUsd,
        total_pnl: totalPnlUsd,
        total_trades: totalTrades,
        win_rate: normalizedWinRate,
        updated_at:
          typeof (data as Record<string, unknown>).updated_at === 'string'
            ? (data as Record<string, unknown>).updated_at
            : analyticsResponse.timestamp,
      },
      timestamp: analyticsResponse.timestamp || new Date().toISOString(),
      trace_id: analyticsResponse.trace_id,
    };
  }

  async getBacktestAnalyticsSummary(runId: string): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    try {
      const response = await this.client.get<ApiResponse>(
        `/api/v1/backtests/${runId}/analytics/summary`
      );
      return response.data;
    } catch (error: unknown) {
      if (!this.shouldUseLegacyRouteFallback(error)) {
        throw error;
      }

      this.logLegacyRouteFallback(
        `/api/v1/backtests/${runId}/analytics/summary`,
        `/api/v1/backtests/${runId}/analytics`,
        error
      );

      const analyticsResponse = await this.getBacktestAnalytics(runId);
      return this.buildBacktestAnalyticsSummaryFromAnalytics(runId, analyticsResponse);
    }
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

  async getBotSummary(
    instanceId: string,
    include: string = 'stats,positions,trades',
    limit: number = 20
  ): Promise<ApiResponse> {
    this.ensureTokenLoaded();
    try {
      const params = new URLSearchParams();
      if (include) {
        params.set('include', include);
      }
      if (Number.isFinite(limit) && limit > 0) {
        params.set('limit', String(limit));
      }
      const query = params.toString();
      const response = await this.client.get<ApiResponse>(
        `/api/v1/bots/${instanceId}/summary${query ? `?${query}` : ''}`
      );
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
    if (!token && !this.accessToken) {
      this.loadTokenFromStorage();
    }
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

  async getAIMarketStatus(): Promise<ApiResponse<AIMarketStatusResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse<AIMarketStatusResponse>>(
      '/api/v1/ai/market-filters/status'
    );
    return response.data;
  }

  async saveAIMarketKey(data: AIKeyPayload): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response = await this.client.put<ApiResponse<Record<string, unknown>>>(
      '/api/v1/ai/market-filters/key',
      data
    );
    return response.data;
  }

  async saveAIMarketSharedKey(data: AIKeyPayload): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response = await this.client.put<ApiResponse<Record<string, unknown>>>(
      '/api/v1/ai/market-filters/shared-key',
      data
    );
    return response.data;
  }

  async deleteAIMarketKey(
    provider: AIMarketProvider
  ): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response = await this.client.delete<ApiResponse<Record<string, unknown>>>(
      `/api/v1/ai/market-filters/key/${encodeURIComponent(provider)}`
    );
    return response.data;
  }

  async deleteAIMarketSharedKey(
    provider: AIMarketProvider
  ): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response = await this.client.delete<ApiResponse<Record<string, unknown>>>(
      `/api/v1/ai/market-filters/shared-key/${encodeURIComponent(provider)}`
    );
    return response.data;
  }

  async selectAIMarkets(
    data: AIMarketSelectionRequest
  ): Promise<ApiResponse<AIMarketSelectionResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.post<ApiResponse<AIMarketSelectionResponse>>(
      '/api/v1/ai/market-filters/select',
      data
    );
    return response.data;
  }

  async explainBacktest(data: AIBacktestExplainRequest): Promise<ApiResponse<AITextResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.post<ApiResponse<AITextResponse>>(
      '/api/v1/ai/backtests/explain',
      data
    );
    return response.data;
  }

  async suggestStrategyParams(data: AISuggestParamsRequest): Promise<ApiResponse<AITextResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.post<ApiResponse<AITextResponse>>(
      '/api/v1/ai/strategies/suggest-params',
      data
    );
    return response.data;
  }

  async getRuntimeDigest(data: AIRuntimeDigestRequest): Promise<ApiResponse<AITextResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.post<ApiResponse<AITextResponse>>(
      '/api/v1/ai/runtime/digest',
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
    return this.getTelegramUserStatus();
  }

  async getTelegramUserStatus(): Promise<ApiResponse<TelegramStatusResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse<TelegramStatusResponse>>(
      '/api/v1/telegram/user/status'
    );
    return response.data;
  }

  async getTelegramGlobalStatus(): Promise<ApiResponse<TelegramStatusResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.get<ApiResponse<TelegramStatusResponse>>(
      '/api/v1/telegram/global/status'
    );
    return response.data;
  }

  async saveTelegramConfig(
    data: TelegramConfigPayload
  ): Promise<ApiResponse<TelegramStatusResponse>> {
    return this.saveTelegramUserConfig(data);
  }

  async saveTelegramUserConfig(
    data: TelegramConfigPayload
  ): Promise<ApiResponse<TelegramStatusResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.put<ApiResponse<TelegramStatusResponse>>(
      '/api/v1/telegram/user/config',
      data
    );
    return response.data;
  }

  async saveTelegramGlobalConfig(
    data: TelegramConfigPayload
  ): Promise<ApiResponse<TelegramStatusResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.put<ApiResponse<TelegramStatusResponse>>(
      '/api/v1/telegram/global/config',
      data
    );
    return response.data;
  }

  async deleteTelegramConfig(): Promise<ApiResponse<Record<string, unknown>>> {
    return this.deleteTelegramUserConfig();
  }

  async deleteTelegramUserConfig(): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response = await this.client.delete<ApiResponse<Record<string, unknown>>>(
      '/api/v1/telegram/user/config'
    );
    return response.data;
  }

  async deleteTelegramGlobalConfig(): Promise<ApiResponse<Record<string, unknown>>> {
    this.ensureTokenLoaded();
    const response = await this.client.delete<ApiResponse<Record<string, unknown>>>(
      '/api/v1/telegram/global/config'
    );
    return response.data;
  }

  async preflightTelegramUserDelivery(
    data?: Partial<TelegramConfigPayload>
  ): Promise<ApiResponse<TelegramPreflightResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.post<ApiResponse<TelegramPreflightResponse>>(
      '/api/v1/telegram/user/preflight',
      data ?? undefined
    );
    return response.data;
  }

  async preflightTelegramGlobalDelivery(
    data?: Partial<TelegramConfigPayload>
  ): Promise<ApiResponse<TelegramPreflightResponse>> {
    this.ensureTokenLoaded();
    const response = await this.client.post<ApiResponse<TelegramPreflightResponse>>(
      '/api/v1/telegram/global/preflight',
      data ?? undefined
    );
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
