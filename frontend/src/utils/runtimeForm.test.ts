import { describe, expect, it } from 'vitest';
import {
  buildRuntimeCreatePayload,
  initialRuntimeCreateForm,
  MAINNET_CHAIN_ID,
  TESTNET_CHAIN_ID,
} from './runtimeForm';

const filled = (overrides = {}) => ({
  ...initialRuntimeCreateForm(),
  instance_id: 'desk-1',
  address: 'dydx1example',
  mnemonic: 'unit test words only',
  ...overrides,
});

describe('manual runtime form', () => {
  it('starts on testnet so real funds are an explicit choice', () => {
    expect(initialRuntimeCreateForm().chain_id).toBe(TESTNET_CHAIN_ID);
  });

  it('derives network and is_testnet from the chain id (no contradiction possible)', () => {
    const testnet = buildRuntimeCreatePayload(filled());
    const mainnet = buildRuntimeCreatePayload(filled({ chain_id: MAINNET_CHAIN_ID }));

    expect(testnet.ok && testnet.payload.credentials.network).toBe('testnet');
    expect(testnet.ok && testnet.payload.trading_params.is_testnet).toBe(true);
    expect(mainnet.ok && mainnet.payload.credentials.network).toBe('mainnet');
    expect(mainnet.ok && mainnet.payload.trading_params.is_testnet).toBe(false);
  });

  it('rejects an unknown chain id instead of guessing a network', () => {
    const result = buildRuntimeCreatePayload(filled({ chain_id: 'dydx-something' }));
    expect(result.ok).toBe(false);
  });

  it.each([
    ['zscore_threshold', Number.NaN],
    ['max_half_life', Number.NaN],
    ['usd_per_trade', Number.NaN],
    ['usd_per_trade', 0],
    ['usd_per_trade', -5],
    ['max_half_life', Number.POSITIVE_INFINITY],
  ])('rejects %s = %s (a cleared number input parses to NaN)', (field, value) => {
    const result = buildRuntimeCreatePayload(filled({ [field]: value }));
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.title).toBe('Invalid trading parameters');
  });

  it('requires id, address and secret phrase', () => {
    expect(buildRuntimeCreatePayload(filled({ mnemonic: '' })).ok).toBe(false);
  });
});
