/**
 * Entry halt
 *
 * A live bot stops opening new pairs on a subaccount after an emergency close
 * failed, because a position leg may be open without its hedge. Exits keep
 * running. The halt stays until an operator has checked the account on dYdX and
 * cleared it, so everything here is read defensively: a payload this screen
 * cannot fully read must never turn into a halt that can be acknowledged away.
 */

import type { EntryHalt, EntryHaltState } from '../api';

export const ENTRY_HALT_NOTE_MAX_LENGTH = 280;

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const toText = (value: unknown): string => (typeof value === 'string' ? value.trim() : '');

/**
 * Reads the halt record. Returns null unless the id, the network and the
 * subaccount are all usable: the operator acknowledges one exact account, so a
 * record that does not name it is not offered for clearing.
 */
const normalizeEntryHalt = (value: unknown): EntryHalt | null => {
  if (!isRecord(value)) {
    return null;
  }

  const id = Number(value.id);
  const network = toText(value.network).toLowerCase();
  const subaccountNumber = Number(value.subaccount_number);
  if (
    !Number.isInteger(id) ||
    id <= 0 ||
    (network !== 'testnet' && network !== 'mainnet') ||
    value.subaccount_number === null ||
    value.subaccount_number === undefined ||
    !Number.isInteger(subaccountNumber) ||
    subaccountNumber < 0
  ) {
    return null;
  }

  return {
    id,
    instance_id: toText(value.instance_id),
    network,
    address: toText(value.address),
    subaccount_number: subaccountNumber,
    reason: toText(value.reason),
    details: isRecord(value.details) ? value.details : {},
    halted_at: toText(value.halted_at),
  };
};

/** Reads the `data` of an entry-halt response. Null means the state is unknown. */
export const normalizeEntryHaltState = (value: unknown): EntryHaltState | null => {
  if (!isRecord(value)) {
    return null;
  }

  return {
    halted: value.halted === true,
    unverified: value.unverified === true,
    halt: normalizeEntryHalt(value.halt),
  };
};

/** True when the state is something an operator has to see. */
export const isEntryHaltVisible = (state: EntryHaltState | null | undefined): boolean =>
  Boolean(state && (state.halted || state.unverified));

/**
 * Strategy-managed runtimes are named `strategy-<userId>-<strategyId>` by the
 * backend. Returns the strategy id, or null for any other instance id.
 */
export const strategyIdFromInstanceId = (instanceId: string | undefined): number | null => {
  const match = /^strategy-\d+-(\d+)$/.exec(instanceId ?? '');
  if (!match) {
    return null;
  }
  const strategyId = Number(match[1]);
  return Number.isSafeInteger(strategyId) && strategyId > 0 ? strategyId : null;
};

/** `BTC-USD / ETH-USD` from the halt details, or null when no market is named. */
export const entryHaltPairLabel = (details: Record<string, unknown>): string | null => {
  const markets = [toText(details.market_1), toText(details.market_2)].filter(
    (market) => market.length > 0
  );
  return markets.length > 0 ? markets.join(' / ') : null;
};

/** The raw failure text from the halt details, or null when there is none. */
export const entryHaltErrorText = (details: Record<string, unknown>): string | null => {
  const error = details.error;
  if (error === null || error === undefined) {
    return null;
  }
  if (typeof error === 'string') {
    return error.trim().length > 0 ? error.trim() : null;
  }
  if (typeof error === 'number' || typeof error === 'boolean') {
    return String(error);
  }
  try {
    return JSON.stringify(error, null, 2);
  } catch {
    return null;
  }
};

/** `Testnet · subaccount 0` */
export const entryHaltAccountLabel = (halt: EntryHalt): string =>
  `${halt.network === 'mainnet' ? 'Mainnet' : 'Testnet'} · subaccount ${halt.subaccount_number}`;

/** Local date and time of the halt, or null when the timestamp is unusable. */
export const formatEntryHaltTime = (haltedAt: string): string | null => {
  if (!haltedAt) {
    return null;
  }
  const parsed = new Date(haltedAt);
  return Number.isNaN(parsed.getTime()) ? null : parsed.toLocaleString();
};
