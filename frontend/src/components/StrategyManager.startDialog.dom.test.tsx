// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import StrategyManager from './StrategyManager';

const DRAWDOWN_MESSAGE = 'max_drawdown_pct=15 is set but the live runtime cannot enforce it.';
const TRAILING_MESSAGE = 'trailing_stop_pct=1 is set but the live runtime cannot enforce it.';
const KEY_MESSAGE = 'No active dYdX key for testnet.';

const mocks = vi.hoisted(() => ({
  readinessData: { current: null as Record<string, unknown> | null },
  readinessArgs: [] as Array<[number | null, string, boolean]>,
  disableMutateAsync: vi.fn(),
  startMutateAsync: vi.fn(),
}));

vi.mock('../api/hooks', () => ({
  useStrategies: () => ({
    data: [
      {
        id: 7,
        name: 'Pairs Alpha',
        runtime_network: 'testnet',
        runtime_subaccount: 0,
        selected_markets: ['BTC-USD', 'ETH-USD'],
        max_drawdown_pct: 15,
        trailing_stop_pct: 1,
      },
    ],
  }),
  useStrategyRuntimes: () => ({
    data: undefined,
    isSuccess: false,
    isError: false,
    error: null,
    dataUpdatedAt: 0,
    errorUpdatedAt: 0,
    fetchStatus: 'idle',
    byId: new Map(),
  }),
  useStrategyStartReadiness: (strategyId: number | null, network: string, enabled: boolean) => {
    mocks.readinessArgs.push([strategyId, network, enabled]);
    return {
      data:
        enabled && mocks.readinessData.current ? { data: mocks.readinessData.current } : undefined,
      isLoading: false,
      isFetching: false,
      error: null,
    };
  },
  useStartStrategyRuntimeMutation: () => ({ mutateAsync: mocks.startMutateAsync }),
  useStopStrategyRuntimeMutation: () => ({ mutateAsync: vi.fn() }),
  useDisableUnenforcedRiskControlsMutation: () => ({
    mutateAsync: mocks.disableMutateAsync,
    isPending: false,
  }),
  useStrategyEntryHalt: () => ({ data: undefined }),
  useClearStrategyEntryHaltMutation: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock('../api', () => ({
  default: { connectStrategyRuntimeSocket: () => null },
  DYDX_CANDLE_RESOLUTION_OPTIONS: [{ value: '1HOUR', label: '1 hour' }],
  normalizeDydxCandleResolution: (value: string) => value,
}));

vi.mock('./AIRuntimeDigest', () => ({ AIRuntimeDigest: () => null }));
vi.mock('./AIStrategyAdvisor', () => ({ AIStrategyAdvisor: () => null }));
vi.mock('./CodexAssetIntelStrip', () => ({ CodexAssetIntelStrip: () => null }));
vi.mock('../features/strategyChat/StrategyChatDrawer', () => ({ StrategyChatDrawer: () => null }));

const baseReadiness = {
  strategy_id: 7,
  selected_runtime_network: 'testnet',
  selected_subaccount: 0,
  configured_selected_markets: ['BTC-USD', 'ETH-USD'],
  key_exists: true,
  available_collateral: 500,
  equity: 500,
  open_positions: 0,
  usd_per_trade: 10,
  usd_min_collateral: 100,
  capital_allocation_usd: 1000,
  sufficient_for_trade_size: true,
  sufficient_for_min_collateral: true,
  wallet_ready: true,
  account_exists: true,
  warnings: [],
};

const renderManager = () =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <StrategyManager />
      </MemoryRouter>
    </QueryClientProvider>
  );

const openStartDialog = async () => {
  fireEvent.click(await screen.findByRole('button', { name: 'Start Strategy for Pairs Alpha' }));
  return screen.findByRole('dialog', { name: 'Start Pairs Alpha' });
};

describe('StrategyManager start dialog: unenforced risk controls', () => {
  beforeEach(() => {
    mocks.readinessArgs.length = 0;
    mocks.disableMutateAsync.mockReset();
    mocks.startMutateAsync.mockReset();
  });

  afterEach(() => cleanup());

  it('shows the notice, keeps launch disabled and does not repeat the control sentences', async () => {
    mocks.readinessData.current = {
      ...baseReadiness,
      ready: false,
      blockers: [DRAWDOWN_MESSAGE, TRAILING_MESSAGE, KEY_MESSAGE],
      unenforced_risk_controls: [
        { field: 'max_drawdown_pct', value: 15, message: DRAWDOWN_MESSAGE },
        { field: 'trailing_stop_pct', value: 1, message: TRAILING_MESSAGE },
      ],
    };
    renderManager();
    const dialog = await openStartDialog();

    expect(
      within(dialog).getByRole('heading', {
        name: 'These risk limits are not available on live bots yet',
      })
    ).toBeVisible();
    expect(within(dialog).getByText('Launch blockers')).toBeVisible();
    expect(within(dialog).getByText(`• ${KEY_MESSAGE}`)).toBeVisible();
    expect(within(dialog).queryByText(`• ${DRAWDOWN_MESSAGE}`)).toBeNull();
    expect(within(dialog).queryByText(`• ${TRAILING_MESSAGE}`)).toBeNull();
    expect(within(dialog).getByRole('button', { name: 'Launch Runtime' })).toBeDisabled();
    expect(within(dialog).getByText('Backtest capital (not a live limit)')).toBeVisible();
    expect(within(dialog).queryByText('Capital allocation target')).toBeNull();
  });

  it('hides the blocker box when the controls are the only blockers', async () => {
    mocks.readinessData.current = {
      ...baseReadiness,
      ready: false,
      blockers: [DRAWDOWN_MESSAGE],
      unenforced_risk_controls: [
        { field: 'max_drawdown_pct', value: 15, message: DRAWDOWN_MESSAGE },
      ],
    };
    renderManager();
    const dialog = await openStartDialog();

    expect(within(dialog).getByText('Max drawdown')).toBeVisible();
    expect(within(dialog).queryByText('Launch blockers')).toBeNull();
  });

  it('turns the limits off for the dialog strategy and network once acknowledged', async () => {
    mocks.readinessData.current = {
      ...baseReadiness,
      ready: false,
      blockers: [DRAWDOWN_MESSAGE, TRAILING_MESSAGE],
      unenforced_risk_controls: [
        { field: 'max_drawdown_pct', value: 15, message: DRAWDOWN_MESSAGE },
        { field: 'trailing_stop_pct', value: 1, message: TRAILING_MESSAGE },
      ],
    };
    mocks.disableMutateAsync.mockResolvedValue({ success: true, data: { id: 7 } });
    renderManager();
    const dialog = await openStartDialog();

    const confirm = within(dialog).getByRole('button', { name: 'Turn off for this strategy' });
    expect(confirm).toBeDisabled();

    fireEvent.click(within(dialog).getByRole('checkbox'));
    fireEvent.click(confirm);

    await waitFor(() => expect(mocks.disableMutateAsync).toHaveBeenCalledTimes(1));
    expect(mocks.disableMutateAsync).toHaveBeenCalledWith({
      strategyId: 7,
      fields: ['max_drawdown_pct', 'trailing_stop_pct'],
      network: 'testnet',
    });
    // Turning the limits off never launches the runtime by itself.
    expect(mocks.startMutateAsync).not.toHaveBeenCalled();
  });

  it('shows the API error inside the notice when turning the limits off fails', async () => {
    mocks.readinessData.current = {
      ...baseReadiness,
      ready: false,
      blockers: [DRAWDOWN_MESSAGE],
      unenforced_risk_controls: [
        { field: 'max_drawdown_pct', value: 15, message: DRAWDOWN_MESSAGE },
      ],
    };
    mocks.disableMutateAsync.mockRejectedValue(new Error('acknowledged must be true'));
    renderManager();
    const dialog = await openStartDialog();

    fireEvent.click(within(dialog).getByRole('checkbox'));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Turn off for this strategy' }));

    expect(await within(dialog).findByRole('alert')).toHaveTextContent('acknowledged must be true');
  });

  it('renders no notice when the backend reports no unenforced controls', async () => {
    mocks.readinessData.current = {
      ...baseReadiness,
      ready: true,
      blockers: [],
      unenforced_risk_controls: [],
    };
    renderManager();
    const dialog = await openStartDialog();

    expect(
      within(dialog).queryByText('These risk limits are not available on live bots yet')
    ).toBeNull();
    expect(within(dialog).getByRole('button', { name: 'Launch Runtime' })).toBeEnabled();
  });
});
