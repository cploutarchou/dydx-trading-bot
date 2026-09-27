// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import StrategyBuilder from './StrategyBuilder';

const mocks = vi.hoisted(() => ({
  api: {
    getAIMarketStatus: vi.fn(),
    getPerpetualMarkets: vi.fn(),
    getStrategy: vi.fn(),
    selectAIMarkets: vi.fn(),
  },
}));

vi.mock('../api', () => ({
  default: mocks.api,
  DYDX_CANDLE_RESOLUTION_OPTIONS: [{ value: '1HOUR', label: '1 hour' }],
  normalizeDydxCandleResolution: (value: string) => value,
}));

vi.mock('./AIStrategyAdvisor', () => ({ AIStrategyAdvisor: () => null }));

const MARKETS = ['BTC-USD', 'ETH-USD', 'SOL-USD'];

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

const selectionResponse = () => ({
  success: true,
  data: {
    provider: 'grok',
    mode: 'ai_recommended',
    source: 'ai',
    selected_markets: ['BTC-USD', 'ETH-USD'],
    rationale: 'Deep books and a long shared history.',
    confidence: 0.8,
    used_ai: true,
    basis: {
      universe_count: 3,
      ranked_count: 3,
      network: 'mainnet',
      source: 'indexer',
      criteria_used: ['volume', 'liquidity'],
      criteria_unavailable: ['cointegration'],
    },
    pairs: [
      {
        market_1: 'BTC-USD',
        market_2: 'ETH-USD',
        reason: 'Tightest spread over the last 5 runs.',
        source: 'strategy_history',
      },
    ],
    market_stats: [],
    dropped_count: 0,
  },
  timestamp: '2026-09-27T10:00:00Z',
});

const renderBuilder = (path: string) =>
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/strategies/new" element={<StrategyBuilder />} />
          <Route path="/strategies/:id/edit" element={<StrategyBuilder />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );

const clickAIPick = async () => {
  const button = await screen.findByRole('button', { name: 'AI Pick' });
  await waitFor(() => expect(button).toBeEnabled());
  await waitFor(() =>
    expect(screen.getByLabelText('AI market filter provider')).toHaveValue('grok')
  );
  fireEvent.click(button);
};

describe('StrategyBuilder AI market selection', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    Object.values(mocks.api).forEach((mock) => mock.mockReset());
    mocks.api.getAIMarketStatus.mockResolvedValue({
      data: { providers: [providerStatus('grok', true), providerStatus('deepseek', false)] },
    });
    mocks.api.getPerpetualMarkets.mockResolvedValue({
      success: true,
      data: { markets: MARKETS, market_details: [] },
    });
    mocks.api.getStrategy.mockResolvedValue({ success: true, data: savedStrategy });
    mocks.api.selectAIMarkets.mockResolvedValue(selectionResponse());
  });

  afterEach(() => cleanup());

  it('sends the strategy id when editing and shows the basis and pairs under the rationale', async () => {
    renderBuilder('/strategies/7/edit');
    await clickAIPick();

    expect(await screen.findByText('Deep books and a long shared history.')).toBeVisible();
    expect(mocks.api.selectAIMarkets).toHaveBeenCalledTimes(1);
    expect(mocks.api.selectAIMarkets).toHaveBeenCalledWith(
      expect.objectContaining({
        provider: 'grok',
        mode: 'ai_recommended',
        markets: MARKETS,
        strategy_id: 7,
      })
    );
    expect(
      screen.getByText(
        'Ranked 3 of 3 mainnet markets · data: indexer · not available: cointegration'
      )
    ).toBeVisible();
    expect(screen.getByText('Pairs the model pointed at')).toBeVisible();
    expect(screen.getByText('BTC-USD / ETH-USD')).toBeVisible();
    expect(screen.getByText(/Tightest spread over the last 5 runs\./)).toBeVisible();
    expect(screen.getByText(/this strategy’s backtests/)).toBeVisible();
  });

  it('drops the basis and pairs once the market list is edited by hand', async () => {
    renderBuilder('/strategies/7/edit');
    await clickAIPick();
    expect(await screen.findByText('Pairs the model pointed at')).toBeVisible();
    expect(screen.getByLabelText('ETH-USD')).toBeChecked();

    fireEvent.click(screen.getByLabelText('ETH-USD'));

    expect(screen.getByLabelText('ETH-USD')).not.toBeChecked();
    expect(screen.queryByText('Pairs the model pointed at')).toBeNull();
    expect(screen.queryByText('BTC-USD / ETH-USD')).toBeNull();
    expect(screen.queryByText(/Ranked 3 of 3/)).toBeNull();
    // The model's own words about its pick stay; the note on what the pick
    // was based on described a list that no longer exists.
    expect(screen.getByText('Deep books and a long shared history.')).toBeVisible();
  });

  it('sends no strategy id for a new strategy and tolerates a reply without basis or pairs', async () => {
    mocks.api.selectAIMarkets.mockResolvedValue({
      success: true,
      data: {
        provider: 'grok',
        mode: 'ai_recommended',
        source: 'ai',
        selected_markets: ['ETH-USD', 'SOL-USD'],
        rationale: 'Two liquid markets.',
        confidence: 0.6,
        used_ai: true,
      },
    });
    renderBuilder('/strategies/new');
    await clickAIPick();

    expect(await screen.findByText('Two liquid markets.')).toBeVisible();
    const payload = mocks.api.selectAIMarkets.mock.calls[0]?.[0] as Record<string, unknown>;
    expect(payload).not.toHaveProperty('strategy_id');
    expect(screen.queryByText(/Ranked \d+ of \d+/)).toBeNull();
    expect(screen.queryByText('Pairs the model pointed at')).toBeNull();
  });
});
