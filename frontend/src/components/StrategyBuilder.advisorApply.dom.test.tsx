// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import StrategyBuilder from './StrategyBuilder';

const mocks = vi.hoisted(() => ({
  api: {
    getAIMarketStatus: vi.fn(),
    getPerpetualMarkets: vi.fn(),
    getStrategy: vi.fn(),
    suggestStrategyParams: vi.fn(),
    updateStrategy: vi.fn(),
  },
}));

vi.mock('../api', () => ({
  default: mocks.api,
  DYDX_CANDLE_RESOLUTION_OPTIONS: [
    { value: '1HOUR', label: '1 hour' },
    { value: '4HOURS', label: '4 hours' },
  ],
  normalizeDydxCandleResolution: (value: string) => value,
}));

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

const savedStrategy = {
  id: 7,
  name: 'Pairs Alpha',
  category: 'pairs_trading',
  description: 'Saved strategy',
  is_public: false,
  runtime_network: 'testnet',
  runtime_subaccount: 0,
  selected_markets: ['BTC-USD', 'ETH-USD'],
  pair_selection_mode: 'cointegration',
  resolution: '1HOUR',
  zscore_threshold: 1.5,
  stats_window: 21,
  max_half_life: 24,
  usd_per_trade: 10,
  usd_min_collateral: 100,
  close_at_zscore_cross: true,
  find_cointegrated_pairs: true,
  manage_exits: true,
  place_trades: true,
  abort_all_positions: false,
  max_positions: 5,
  max_drawdown_pct: 0,
  stop_loss_pct: 2,
  take_profit_pct: 5,
  trailing_stop_pct: 0,
  rebalance_interval_hours: 24,
  position_timeout_hours: 72,
  initial_amount: 300,
  max_history_days: 90,
  transaction_fee: 0.0005,
  slippage: 0.001,
};

const suggestions = [
  {
    parameter: 'usd_per_trade',
    label: 'Size per trade',
    unit: 'USD',
    current: 10,
    suggested: 50,
    rationale: 'Larger clips keep the fee share of each trade lower.',
    evidence: 'Fees were 9% of the average gross move at 10 USD.',
    risk: 'money',
    backtest_only: false,
  },
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
  {
    parameter: 'risk_free_rate',
    label: 'Risk-free rate',
    unit: '',
    current: 0.02,
    suggested: 0.03,
    rationale: 'Matches the current funding baseline.',
    evidence: 'Sharpe in the saved runs assumed 2%.',
    risk: 'normal',
    backtest_only: true,
  },
];

const suggestResponse = () => ({
  success: true,
  data: {
    provider: 'grok',
    model: 'grok-4.7',
    used_ai: true,
    content: suggestions
      .map(
        (item, index) =>
          `${index + 1}. ${item.parameter}: Current '${String(item.current)}' -> Suggested '${String(item.suggested)}'.`
      )
      .join('\n'),
    summary: 'Trade larger clips on slower candles.',
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

const renderBuilder = () =>
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={['/strategies/7/edit']}>
        <Routes>
          <Route path="/strategies/:id/edit" element={<StrategyBuilder />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );

// The trade-size input has no id; the field spread gives it its name.
const tradeSizeInput = (): HTMLInputElement => {
  const input = document.querySelector<HTMLInputElement>('input[name="usd_per_trade"]');
  if (!input) {
    throw new Error('usd_per_trade input not rendered');
  }
  return input;
};

const openForm = async () => {
  expect(await screen.findByDisplayValue('Pairs Alpha')).toBeVisible();
  await waitFor(() =>
    expect(screen.getByLabelText('AI provider for parameter suggestions')).toHaveValue('grok')
  );
  // Trade size and the behaviour toggles live in the advanced section.
  fireEvent.click(screen.getByRole('button', { name: /Advanced Settings/ }));
  expect(tradeSizeInput()).toHaveValue(10);
  expect(screen.getByLabelText('Close at Z-Score Cross')).toBeChecked();
  expect(screen.getByLabelText(/Candle Resolution/)).toHaveValue('1HOUR');
};

const confirmDialog = async () => {
  const dialog = await screen.findByRole('dialog', { name: 'Confirm AI parameter updates' });
  fireEvent.click(within(dialog).getByRole('button', { name: 'Confirm Apply (Enter)' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
};

describe('StrategyBuilder: applying AI parameter suggestions', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    Object.values(mocks.api).forEach((mock) => mock.mockReset());
    mocks.api.getAIMarketStatus.mockResolvedValue({
      data: { providers: [providerStatus('grok', true), providerStatus('deepseek', false)] },
    });
    mocks.api.getPerpetualMarkets.mockResolvedValue({
      success: true,
      data: { markets: ['BTC-USD', 'ETH-USD', 'SOL-USD'], market_details: [] },
    });
    mocks.api.getStrategy.mockResolvedValue({ success: true, data: savedStrategy });
    mocks.api.suggestStrategyParams.mockResolvedValue(suggestResponse());
  });

  afterEach(() => cleanup());

  it('writes number, boolean and string suggestions into the form and marks the rest', async () => {
    renderBuilder();
    await openForm();

    fireEvent.click(screen.getByRole('button', { name: 'Suggest Parameters' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Review & Apply All' }));
    await confirmDialog();

    expect(mocks.api.suggestStrategyParams).toHaveBeenCalledWith({
      provider: 'grok',
      strategy_id: 7,
      max_suggestions: 8,
    });
    expect(tradeSizeInput()).toHaveValue(50);
    expect(screen.getByLabelText('Close at Z-Score Cross')).not.toBeChecked();
    expect(screen.getByLabelText(/Candle Resolution/)).toHaveValue('4HOURS');

    // risk_free_rate has no field on this form: the toast counts it and the
    // advisor row leaves the pending state with a note instead of a button.
    expect(
      screen.getByText('✅ Applied 3 AI suggestions (1 not editable on this page)')
    ).toBeVisible();
    expect(screen.getByText('3 of 4 suggestions applied ✓')).toBeVisible();
    expect(screen.getByText('Risk-free rate')).toBeVisible();
    expect(screen.getByText('Not editable on this page')).toBeVisible();
    expect(screen.queryByText('Size per trade')).toBeNull();
    expect(screen.queryByRole('button', { name: /^Apply / })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Review & Apply All' })).toBeNull();
    // The advisor sits inside the builder form; none of its buttons submit it.
    expect(mocks.api.updateStrategy).not.toHaveBeenCalled();
  });

  it('applies a single boolean suggestion without touching the other fields', async () => {
    renderBuilder();
    await openForm();

    fireEvent.click(screen.getByRole('button', { name: 'Suggest Parameters' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Apply Close at Z-score cross' }));
    await confirmDialog();

    expect(screen.getByLabelText('Close at Z-Score Cross')).not.toBeChecked();
    expect(tradeSizeInput()).toHaveValue(10);
    expect(screen.getByLabelText(/Candle Resolution/)).toHaveValue('1HOUR');
    expect(screen.getByText('✅ Applied 1 AI suggestion')).toBeVisible();
    expect(screen.getByText('3 suggestions pending')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Apply Close at Z-score cross' })).toBeNull();
    expect(mocks.api.updateStrategy).not.toHaveBeenCalled();
  });
});
