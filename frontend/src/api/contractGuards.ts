type UnknownRecord = Record<string, unknown>;

export interface ContractValidationResult {
  ok: boolean;
  missingKeys: string[];
}

const isRecord = (value: unknown): value is UnknownRecord =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const unwrapEnvelopeData = (payload: unknown): UnknownRecord => {
  if (!isRecord(payload)) return {};
  if (isRecord(payload.data)) return payload.data;
  return payload;
};

const validateRequiredKeys = (payload: unknown, keys: string[]): ContractValidationResult => {
  const target = unwrapEnvelopeData(payload);
  const missingKeys = keys.filter((key) => !(key in target));
  return {
    ok: missingKeys.length === 0,
    missingKeys,
  };
};

const throwContractError = (
  endpoint: string,
  validation: ContractValidationResult,
  payload: unknown
): never => {
  // Log the payload once to help backend/frontend contract triage.
  console.error(`❌ Contract guard failed for ${endpoint}`, {
    missingKeys: validation.missingKeys,
    payload,
  });
  throw new Error(
    `Contract validation failed for ${endpoint}. Missing keys: ${validation.missingKeys.join(', ')}`
  );
};

export const contractSnapshots = {
  runBacktest: ['run_id'],
  listBacktests: ['backtests'],
  backtestStatus: ['run_id', 'status', 'progress_pct'],
  syncHealth: ['runs'],
} as const;

export const guardRunBacktestContract = (payload: unknown): void => {
  const validation = validateRequiredKeys(payload, [...contractSnapshots.runBacktest]);
  if (!validation.ok) {
    throwContractError('POST /api/v1/backtests/run', validation, payload);
  }
};

export const guardListBacktestsContract = (payload: unknown): void => {
  const validation = validateRequiredKeys(payload, [...contractSnapshots.listBacktests]);
  if (!validation.ok) {
    throwContractError('GET /api/v1/backtests', validation, payload);
  }
};

export const guardBacktestStatusContract = (payload: unknown): void => {
  const validation = validateRequiredKeys(payload, [...contractSnapshots.backtestStatus]);
  if (!validation.ok) {
    throwContractError('GET /api/v1/backtests/:run_id/status', validation, payload);
  }
};

export const guardSyncHealthContract = (payload: unknown): void => {
  const validation = validateRequiredKeys(payload, [...contractSnapshots.syncHealth]);
  if (!validation.ok) {
    throwContractError('GET /api/v1/backtests/sync-health', validation, payload);
  }
};

