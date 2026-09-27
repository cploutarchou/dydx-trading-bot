// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import StrategyManager from './StrategyManager';

const mocks = vi.hoisted(() => ({
  api: {
    connectStrategyRuntimeSocket: () => null,
    getAIMarketStatus: vi.fn(),
    suggestStrategyParams: vi.fn(),
    updateStrategy: vi.fn(),
  },
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
        resolution: '1HOUR',
        candle_resolution: '1HOUR',
        close_at_zscore_cross: true,
        zscore_threshold: 1.5,
        usd_per_trade: 10,
        max_drawdown_pct: 0,
        trailing_stop_pct: 0,
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
  useStrategyStartReadiness: () => ({
    data: undefined,
    isLoading: false,
    isFetching: false,
    error: null,
  }),
  useStartStrategyRuntimeMutation: () => ({ mutateAsync: vi.fn() }),
  useStopStrategyRuntimeMutation: () => ({ mutateAsync: vi.fn() }),
  useDisableUnenforcedRiskControlsMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useStrategyEntryHalt: () => ({ data: undefined }),
  useClearStrategyEntryHaltMutation: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock('../api', () => ({
  default: mocks.api,
  DYDX_CANDLE_RESOLUTION_OPTIONS: [
    { value: '1HOUR', label: '1 hour' },
    { value: '4HOURS', label: '4 hours' },
  ],
  normalizeDydxCandleResolution: (value: string) => value,
}));

vi.mock('./AIRuntimeDigest', () => ({ AIRuntimeDigest: () => null }));
vi.mock('./CodexAssetIntelStrip', () => ({ CodexAssetIntelStrip: () => null }));
vi.mock('../features/strategyChat/StrategyChatDrawer', () => ({ StrategyChatDrawer: () => null }));

const providerStatus = (provider: string, available: boolean) => ({
  provider,
  enabled: available,
  available,
  availability_status: available ? 'available' : 'not_configured',
  shared_key_available: available,
  user_key_available: false,
  active_key_source: available ? 'shared' : 'none',
  model: 'grok-4.3',
  analysis_model: 'grok-4.7',
});

const suggestions = [
  {
    parameter: 'close_at_zscore_cross',
    label: 'Close at Z-score cross',
    unit: '',
    current: true,
    suggested: false,
    rationale: 'Leave the exit to the stop and timeout rules.',
    evidence: '31 of 41 trades closed at the cross before the spread had reverted.',
    risk: 'normal',
    backtest_only: false,
  },
  {
    parameter: 'candle_resolution',
    label: 'Candle resolution',
    unit: '',
    current: '1HOUR',
    suggested: '4HOURS',
    rationale: 'Slower candles smooth the z-score.',
    evidence: 'The 4-hour runs had fewer whipsaw exits.',
    risk: 'normal',
    backtest_only: false,
  },
];

const suggestResponse = () => ({
  success: true,
  data: {
    provider: 'grok',
    model: 'grok-4.7',
    used_ai: true,
    content: [
      "1. close_at_zscore_cross: Current 'true' -> Suggested 'false'.",
      "2. candle_resolution: Current '1HOUR' -> Suggested '4HOURS'.",
    ].join('\n'),
    summary: 'Exit on the rules and use slower candles.',
    suggestions,
    dropped: [],
    data_gaps: [],
    evidence_summary: {
      completed_runs: 4,
      trades_analysed: 41,
      pairs_analysed: 6,
      live_closed_trades: 0,
      live_open_positions: 0,
      live_available: false,
      cointegrated_pairs: 2,
      data_notes: [],
    },
  },
  timestamp: '2026-09-27T10:00:00Z',
});

const renderManager = () =>
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter>
        <StrategyManager />
      </MemoryRouter>
    </QueryClientProvider>
  );

const requestSuggestions = async () => {
  const suggest = await screen.findByRole('button', { name: 'Suggest Parameters' });
  await waitFor(() =>
    expect(screen.getByLabelText('AI provider for parameter suggestions')).toHaveValue('grok')
  );
  fireEvent.click(suggest);
  expect(await screen.findByText('Close at Z-score cross')).toBeVisible();
};

const confirmDialog = async () => {
  const dialog = await screen.findByRole('dialog', { name: 'Confirm AI parameter updates' });
  fireEvent.click(within(dialog).getByRole('button', { name: 'Confirm Apply (Enter)' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
};

const rowFor = (label: string): HTMLElement => {
  const row = screen.getByText(label).closest('li');
  if (!row) {
    throw new Error(`No suggestion row for ${label}`);
  }
  return row;
};

describe('StrategyManager: applying AI parameter suggestions', () => {
  beforeEach(() => {
    window.localStorage.clear();
    mocks.api.getAIMarketStatus.mockReset();
    mocks.api.suggestStrategyParams.mockReset();
    mocks.api.updateStrategy.mockReset();
    mocks.api.getAIMarketStatus.mockResolvedValue({
      data: { providers: [providerStatus('grok', true), providerStatus('deepseek', false)] },
    });
    mocks.api.suggestStrategyParams.mockResolvedValue(suggestResponse());
    mocks.api.updateStrategy.mockResolvedValue({ success: true, data: { id: 7 } });
  });

  afterEach(() => cleanup());

  it('sends a boolean and a string suggestion through the update payload', async () => {
    renderManager();
    await requestSuggestions();

    // Typed values render the way the operator will read them.
    const closeRow = rowFor('Close at Z-score cross');
    expect(within(closeRow).getByText('On')).toBeVisible();
    expect(within(closeRow).getByText('Off')).toBeVisible();
    const resolutionRow = rowFor('Candle resolution');
    expect(within(resolutionRow).getByText('1HOUR')).toBeVisible();
    expect(within(resolutionRow).getByText('4HOURS')).toBeVisible();

    fireEvent.click(screen.getByRole('button', { name: 'Review & Apply All' }));
    await confirmDialog();

    await waitFor(() => expect(mocks.api.updateStrategy).toHaveBeenCalledTimes(1));
    expect(mocks.api.updateStrategy).toHaveBeenCalledWith(
      7,
      expect.objectContaining({
        name: 'Pairs Alpha',
        selected_markets: ['BTC-USD', 'ETH-USD'],
        close_at_zscore_cross: false,
        candle_resolution: '4HOURS',
        resolution: '4HOURS',
      })
    );
    expect(await screen.findByText('All 2 suggestions applied ✓')).toBeVisible();
    expect(screen.getByText('✅ Applied AI suggestions to "Pairs Alpha"')).toBeVisible();
  });

  it('applies a single boolean suggestion and keeps the saved resolution', async () => {
    renderManager();
    await requestSuggestions();

    fireEvent.click(screen.getByRole('button', { name: 'Apply Close at Z-score cross' }));
    await confirmDialog();

    await waitFor(() => expect(mocks.api.updateStrategy).toHaveBeenCalledTimes(1));
    expect(mocks.api.updateStrategy).toHaveBeenCalledWith(
      7,
      expect.objectContaining({
        close_at_zscore_cross: false,
        candle_resolution: '1HOUR',
        resolution: '1HOUR',
      })
    );
    expect(await screen.findByText('1 suggestion pending')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Apply Close at Z-score cross' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Apply Candle resolution' })).toBeVisible();
  });
});
