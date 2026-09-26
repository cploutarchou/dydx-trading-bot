/**
 * Runtime status derivation for strategy-managed bots.
 *
 * The backend's runtime payload carries the bot's own status for the process,
 * whether the bot answered this poll (`runtime_confirmed`), and whether it
 * still records open positions for a runtime that is not running
 * (`exposure_unconfirmed`). Nothing here upgrades a status: an errored
 * runtime with recorded positions stays "error" and shows the exposure
 * warning, because those rows are what a dead process left behind, not a
 * live count.
 *
 * Heartbeat tones come only from the runtime's own update time. The time the
 * backend last polled says nothing about the process, so it is never used as
 * a heartbeat.
 */

export type StrategyRuntimeStatusValue =
  | 'stopped'
  | 'starting'
  | 'running'
  | 'stopping'
  | 'paused'
  | 'degraded'
  | 'recovering'
  | 'safeguarded'
  | 'error';

export interface StrategyStatus {
  strategyId: number;
  status: StrategyRuntimeStatusValue;
  lastError?: string;
  tradesExecuted?: number;
  pnl?: number;
  winRate?: number;
  openPositions?: number;
  uptimeSeconds?: number;
  startedAt?: string;
  /** The runtime's own last update; absent when the bot reported none. */
  runtimeUpdatedAt?: string;
  /** When the backend last polled; a bookkeeping time, not a heartbeat. */
  updatedAt: string;
  botStatus?: string;
  instanceId?: string;
  network?: string;
  runtimeSubaccount?: number;
  capitalAllocationUsd?: number;
  /** False when the bot could not be reached for this poll; absent means not known. */
  runtimeConfirmed?: boolean;
  /** The last time the bot answered for this runtime. */
  lastConfirmedAt?: string;
  /** True when open positions are recorded for a runtime that is not running. */
  exposureUnconfirmed?: boolean;
}

const ACCEPTED_STATUSES: ReadonlySet<string> = new Set<StrategyRuntimeStatusValue>([
  'running',
  'starting',
  'stopping',
  'paused',
  'degraded',
  'recovering',
  'safeguarded',
  'error',
]);

export const HEARTBEAT_LIVE_THRESHOLD_MS = 30_000;
export const HEARTBEAT_DELAYED_THRESHOLD_MS = 120_000;

export const isRuntimeOperationalStatus = (status: StrategyRuntimeStatusValue): boolean =>
  status === 'running' ||
  status === 'degraded' ||
  status === 'recovering' ||
  status === 'safeguarded';

export const isRuntimeActiveStatus = (status: StrategyRuntimeStatusValue): boolean =>
  isRuntimeOperationalStatus(status) || status === 'starting';

const asNumber = (value: unknown): number | undefined => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
};

const asString = (value: unknown): string | undefined =>
  typeof value === 'string' && value.trim() !== '' ? value : undefined;

/** Maps one backend runtime payload to the status the pages render. */
export const toStrategyStatus = (
  strategyId: number,
  runtimeData: Record<string, unknown> | undefined,
  now: number = Date.now()
): StrategyStatus => {
  const startedAt = asString(runtimeData?.started_at);
  const rawPnl = asNumber(runtimeData?.pnl);
  const rawTrades = asNumber(runtimeData?.trades_executed);
  const rawOpenPositions = asNumber(runtimeData?.open_positions);
  const rawWinRate = asNumber(runtimeData?.win_rate);
  const rawUptimeSeconds = asNumber(runtimeData?.uptime_seconds);
  const updatedAt =
    asString(runtimeData?.last_synced_at) ??
    asString(runtimeData?.updated_at) ??
    new Date(now).toISOString();
  const runtimeUpdatedAt = asString(runtimeData?.runtime_updated_at);
  const normalizedStatus =
    typeof runtimeData?.status === 'string' ? runtimeData.status.toLowerCase() : 'stopped';
  const status = (
    ACCEPTED_STATUSES.has(normalizedStatus) ? normalizedStatus : 'stopped'
  ) as StrategyRuntimeStatusValue;
  const rawLastError =
    typeof runtimeData?.last_error === 'string' ? runtimeData.last_error.trim() : '';
  const runtimeConfirmed = runtimeData?.runtime_confirmed !== false;
  const openPositions =
    rawOpenPositions !== undefined ? Math.max(0, Math.floor(rawOpenPositions)) : undefined;
  const exposureUnconfirmed =
    runtimeData?.exposure_unconfirmed === true ||
    (runtimeData?.exposure_unconfirmed === undefined &&
      !isRuntimeActiveStatus(status) &&
      (openPositions ?? 0) > 0);

  const computedUptimeSeconds =
    rawUptimeSeconds !== undefined
      ? rawUptimeSeconds
      : startedAt && isRuntimeOperationalStatus(status)
        ? Math.max(0, Math.floor((now - new Date(startedAt).getTime()) / 1000))
        : undefined;

  return {
    strategyId,
    status,
    lastError: status === 'error' && rawLastError ? rawLastError : undefined,
    updatedAt,
    runtimeUpdatedAt,
    startedAt,
    tradesExecuted: rawTrades !== undefined ? Math.max(0, Math.floor(rawTrades)) : undefined,
    pnl: rawPnl,
    winRate:
      rawWinRate !== undefined ? (rawWinRate <= 1 ? rawWinRate * 100 : rawWinRate) : undefined,
    openPositions,
    uptimeSeconds:
      computedUptimeSeconds !== undefined
        ? Math.max(0, Math.floor(computedUptimeSeconds))
        : undefined,
    botStatus: asString(runtimeData?.bot_status),
    instanceId: asString(runtimeData?.instance_id),
    network: asString(runtimeData?.network),
    runtimeSubaccount:
      typeof runtimeData?.runtime_subaccount === 'number'
        ? runtimeData.runtime_subaccount
        : undefined,
    capitalAllocationUsd:
      typeof runtimeData?.capital_allocation_usd === 'number'
        ? runtimeData.capital_allocation_usd
        : undefined,
    runtimeConfirmed,
    lastConfirmedAt: asString(runtimeData?.last_confirmed_at),
    exposureUnconfirmed,
  };
};

export type HeartbeatTone = 'live' | 'delayed' | 'stale' | 'unknown';

/**
 * Tone for a runtime's own update time. Without one the tone is unknown:
 * the poll time is not a heartbeat, so it never stands in for it.
 */
export const resolveHeartbeatTone = (
  heartbeatAt: string | undefined,
  webSocketConnected: boolean,
  now: number = Date.now()
): { tone: HeartbeatTone; label: string } => {
  if (!heartbeatAt) {
    return { tone: 'unknown', label: 'No runtime heartbeat reported' };
  }

  const parsed = new Date(heartbeatAt);
  if (Number.isNaN(parsed.getTime())) {
    return { tone: 'unknown', label: 'Invalid heartbeat timestamp' };
  }

  const ageMs = now - parsed.getTime();
  if (ageMs <= HEARTBEAT_LIVE_THRESHOLD_MS && webSocketConnected) {
    return { tone: 'live', label: 'Live updates healthy' };
  }

  if (ageMs <= HEARTBEAT_DELAYED_THRESHOLD_MS) {
    return { tone: 'delayed', label: 'Updates slightly delayed' };
  }

  return { tone: 'stale', label: 'Updates stale, check runtime' };
};

export const toHeartbeatAgeSeconds = (
  heartbeatAt: string | undefined,
  now: number = Date.now()
): number | null => {
  if (!heartbeatAt) {
    return null;
  }
  const parsed = new Date(heartbeatAt);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return Math.max(0, Math.floor((now - parsed.getTime()) / 1000));
};

export interface RuntimeHealthSummary {
  /** Runtimes the totals cover: the active ones only. */
  scopedCount: number;
  totalPnl?: number;
  totalOpenPositions?: number;
  longestUptimeSeconds?: number;
  latestRuntimeUpdate?: string;
  /** Active runtimes whose own update time is older than the delayed threshold, or missing. */
  staleRuntimeCount: number;
  /** Runtimes that are not running but still record open positions. */
  unconfirmedExposureCount: number;
  /** Positions recorded on those runtimes; not live, check the exchange. */
  unconfirmedExposurePositions: number;
  /** Runtimes the bot could not be asked about in the last poll. */
  unconfirmedRuntimeCount: number;
}

/**
 * Header totals over the active runtimes only. A stopped or errored runtime
 * never contributes positions or uptime; what it still records is reported
 * separately as unconfirmed exposure.
 */
export const summarizeRuntimeHealth = (
  statuses: readonly StrategyStatus[],
  now: number = Date.now()
): RuntimeHealthSummary => {
  const activeStatuses = statuses.filter((status) => isRuntimeActiveStatus(status.status));

  const hasPnlData = activeStatuses.some((status) => status.pnl !== undefined);
  const hasOpenPositionData = activeStatuses.some((status) => status.openPositions !== undefined);
  const hasUptimeData = activeStatuses.some((status) => status.uptimeSeconds !== undefined);

  const latestUpdateMs = activeStatuses.reduce<number | null>((latest, status) => {
    if (!status.runtimeUpdatedAt) return latest;
    const parsedMs = new Date(status.runtimeUpdatedAt).getTime();
    if (Number.isNaN(parsedMs)) return latest;
    if (latest === null || parsedMs > latest) return parsedMs;
    return latest;
  }, null);

  const exposed = statuses.filter((status) => status.exposureUnconfirmed === true);

  return {
    scopedCount: activeStatuses.length,
    totalPnl: hasPnlData
      ? activeStatuses.reduce((sum, status) => sum + (status.pnl ?? 0), 0)
      : undefined,
    totalOpenPositions: hasOpenPositionData
      ? activeStatuses.reduce((sum, status) => sum + (status.openPositions ?? 0), 0)
      : undefined,
    longestUptimeSeconds: hasUptimeData
      ? activeStatuses.reduce((max, status) => Math.max(max, status.uptimeSeconds ?? 0), 0)
      : undefined,
    latestRuntimeUpdate:
      latestUpdateMs !== null ? new Date(latestUpdateMs).toISOString() : undefined,
    staleRuntimeCount: activeStatuses.filter((status) => {
      const age = toHeartbeatAgeSeconds(status.runtimeUpdatedAt, now);
      return age === null || age * 1000 > HEARTBEAT_DELAYED_THRESHOLD_MS;
    }).length,
    unconfirmedExposureCount: exposed.length,
    unconfirmedExposurePositions: exposed.reduce(
      (sum, status) => sum + (status.openPositions ?? 0),
      0
    ),
    unconfirmedRuntimeCount: statuses.filter((status) => status.runtimeConfirmed === false).length,
  };
};
