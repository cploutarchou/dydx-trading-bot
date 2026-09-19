/**
 * Manual runtime creation form: defaults, network derivation and validation.
 *
 * The network is derived from the chain id so the payload can never say
 * "mainnet chain" and "testnet" at the same time, and the form starts on
 * testnet: trading real funds has to be an explicit choice.
 */

export const TESTNET_CHAIN_ID = 'dydx-testnet-4';
export const MAINNET_CHAIN_ID = 'dydx-mainnet-1';

export interface RuntimeCreateForm {
  instance_id: string;
  chain_id: string;
  address: string;
  mnemonic: string;
  zscore_threshold: number;
  max_half_life: number;
  usd_per_trade: number;
}

export const initialRuntimeCreateForm = (): RuntimeCreateForm => ({
  instance_id: '',
  chain_id: TESTNET_CHAIN_ID,
  address: '',
  mnemonic: '',
  zscore_threshold: 1.5,
  max_half_life: 24,
  usd_per_trade: 10,
});

/** Only the known mainnet chain id is mainnet; anything else is treated as testnet. */
export const isTestnetChain = (chainId: string): boolean => chainId !== MAINNET_CHAIN_ID;

const isPositiveNumber = (value: number): boolean => Number.isFinite(value) && value > 0;

export type RuntimeCreateResult =
  | { ok: true; payload: ReturnType<typeof toPayload> }
  | { ok: false; title: string; message: string };

const toPayload = (form: RuntimeCreateForm) => {
  const isTestnet = isTestnetChain(form.chain_id);
  return {
    instance_id: form.instance_id,
    name: form.instance_id,
    credentials: {
      address: form.address,
      mnemonic: form.mnemonic,
      network: isTestnet ? ('testnet' as const) : ('mainnet' as const),
      chain_id: form.chain_id,
      secret_phrase: form.mnemonic,
    },
    trading_params: {
      is_testnet: isTestnet,
      zscore_threshold: form.zscore_threshold,
      max_half_life: form.max_half_life,
      usd_per_trade: form.usd_per_trade,
      max_positions: 5,
      slippage_tolerance: 0.001,
      risk_multiplier: 1,
    },
  };
};

export const buildRuntimeCreatePayload = (form: RuntimeCreateForm): RuntimeCreateResult => {
  if (!form.instance_id || !form.address || !form.mnemonic) {
    return {
      ok: false,
      title: 'Runtime details missing',
      message:
        'Complete the runtime ID, wallet address, and secret phrase before creating a new bot.',
    };
  }
  if (form.chain_id !== TESTNET_CHAIN_ID && form.chain_id !== MAINNET_CHAIN_ID) {
    return {
      ok: false,
      title: 'Unknown network',
      message: 'Choose dYdX Testnet or dYdX Mainnet.',
    };
  }
  if (
    !isPositiveNumber(form.zscore_threshold) ||
    !isPositiveNumber(form.max_half_life) ||
    !isPositiveNumber(form.usd_per_trade)
  ) {
    return {
      ok: false,
      title: 'Invalid trading parameters',
      message:
        'Z-score threshold, max half-life and USD per trade must be numbers greater than zero.',
    };
  }
  return { ok: true, payload: toPayload(form) };
};
