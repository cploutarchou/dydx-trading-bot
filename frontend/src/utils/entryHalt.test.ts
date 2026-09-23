import { describe, expect, it } from 'vitest';
import {
  entryHaltErrorText,
  entryHaltPairLabel,
  isEntryHaltVisible,
  normalizeEntryHaltState,
  strategyIdFromInstanceId,
} from './entryHalt';

const record = {
  id: 3,
  instance_id: 'strategy-85-2',
  network: 'TESTNET',
  address: 'dydx1example',
  subaccount_number: 0,
  reason: ' emergency close failed ',
  details: { market_1: 'AVAX-USD', market_2: 'FIL-USD' },
  halted_at: '2026-09-21T16:45:00+00:00',
};

describe('normalizeEntryHaltState', () => {
  it('reads a halt and tidies its text', () => {
    const state = normalizeEntryHaltState({ halted: true, unverified: false, halt: record });

    expect(state?.halted).toBe(true);
    expect(state?.halt).toMatchObject({
      id: 3,
      network: 'testnet',
      subaccount_number: 0,
      reason: 'emergency close failed',
    });
  });

  it('returns null for a payload that is not an object: unknown, not "not halted"', () => {
    expect(normalizeEntryHaltState(undefined)).toBeNull();
    expect(normalizeEntryHaltState('halted')).toBeNull();
    expect(isEntryHaltVisible(null)).toBe(false);
  });

  it.each([
    ['no id', { ...record, id: undefined }],
    ['an unknown network', { ...record, network: 'devnet' }],
    ['no subaccount', { ...record, subaccount_number: null }],
    ['a negative subaccount', { ...record, subaccount_number: -1 }],
  ])('keeps the halt visible but drops a record with %s', (_label, halt) => {
    const state = normalizeEntryHaltState({ halted: true, unverified: false, halt });

    expect(state?.halt).toBeNull();
    expect(isEntryHaltVisible(state)).toBe(true);
  });

  it('only treats literal true as halted or unverified', () => {
    const state = normalizeEntryHaltState({ halted: 'false', unverified: 1, halt: null });

    expect(state).toEqual({ halted: false, unverified: false, halt: null });
    expect(isEntryHaltVisible(state)).toBe(false);
  });
});

describe('entry halt details', () => {
  it('labels the pair from whichever markets are named', () => {
    expect(entryHaltPairLabel(record.details)).toBe('AVAX-USD / FIL-USD');
    expect(entryHaltPairLabel({ market_1: 'AVAX-USD' })).toBe('AVAX-USD');
    expect(entryHaltPairLabel({})).toBeNull();
  });

  it('renders the failure whatever its type', () => {
    expect(entryHaltErrorText({ error: ' code 2001 ' })).toBe('code 2001');
    expect(entryHaltErrorText({ error: { code: 2001 } })).toContain('"code": 2001');
    expect(entryHaltErrorText({ error: '' })).toBeNull();
    expect(entryHaltErrorText({})).toBeNull();
  });
});

describe('strategyIdFromInstanceId', () => {
  it('reads the strategy id of a strategy-managed runtime only', () => {
    expect(strategyIdFromInstanceId('strategy-85-2')).toBe(2);
    expect(strategyIdFromInstanceId('bot-flow-1')).toBeNull();
    expect(strategyIdFromInstanceId('strategy-85-0')).toBeNull();
    expect(strategyIdFromInstanceId(undefined)).toBeNull();
  });
});
