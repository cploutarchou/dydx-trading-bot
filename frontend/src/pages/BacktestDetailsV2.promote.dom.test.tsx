// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { BacktestDetailsV2 } from './BacktestDetailsV2';

const RUN_ID = 'run-12345678-abcd';
const DRAWDOWN_MESSAGE = 'max_drawdown_pct=15 is set but the live runtime cannot enforce it.';
const TRAILING_MESSAGE = 'trailing_stop_pct=1 is set but the live runtime cannot enforce it.';
const KEY_MESSAGE = 'No active dYdX key for testnet.';
const COLLATERAL_MESSAGE = 'Free collateral is below the minimum-collateral guard.';

const mocks = vi.hoisted(() => ({
  api: {
    getBacktest: vi.fn(),
    getStrategy: vi.fn(),
    getBacktestAnalytics: vi.fn(),
    getBacktestPositionSnapshots: vi.fn(),
    getBacktestTradesDetailed: vi.fn(),
    createStrategyFromBacktest: vi.fn(),
    getStrategyStartReadiness: vi.fn(),
    startStrategyRuntime: vi.fn(),
    disableUnenforcedRiskControls: vi.fn(),
  },
  getBacktestStatus: vi.fn(),
}));

vi.mock('../api', () => ({ default: mocks.api }));
vi.mock('../api/botApi', () => ({ botApi: { getBacktestStatus: mocks.getBacktestStatus } }));
vi.mock('../api/hooks', () => ({
  useBacktestProgress: () => ({
    data: undefined,
    lastSocketEvent: null,
    progressPercent: 100,
    progressSource: 'http',
    etaSeconds: null,
    currentPair: null,
    isConnected: false,
  }),
}));
vi.mock('../store/auth', () => ({
  useAuthStore: (selector: (_state: { user: { role: string } }) => unknown) =>
    selector({ user: { role: 'client' } }),
}));
vi.mock('../components/AIBacktestExplainer', () => ({ AIBacktestExplainer: () => null }));
vi.mock('../components/BacktestLightweightChart', () => ({ BacktestLightweightChart: () => null }));
vi.mock('../components/BacktestPositionsPanel', () => ({ BacktestPositionsPanel: () => null }));
vi.mock('../components/BacktestResultsEnhanced', () => ({ BacktestResultsEnhanced: () => null }));
vi.mock('../components/BacktestTradesPanel', () => ({ BacktestTradesPanel: () => null }));

const completedBacktest = {
  run_id: RUN_ID,
  status: 'completed',
  progress_percent: 100,
  total_trades: 12,
  request: { initial_balance: 1000, trading_parameters: { max_drawdown_pct: 15 } },
};

const blockedByRiskControls = (extraBlockers: string[] = []) => ({
  success: true,
  data: {
    ready: false,
    blockers: [DRAWDOWN_MESSAGE, TRAILING_MESSAGE, ...extraBlockers],
    warnings: [],
    unenforced_risk_controls: [
      { field: 'max_drawdown_pct', value: 15, message: DRAWDOWN_MESSAGE },
      { field: 'trailing_stop_pct', value: 1, message: TRAILING_MESSAGE },
    ],
  },
});

const readyReadiness = {
  success: true,
  data: { ready: true, blockers: [], warnings: [], unenforced_risk_controls: [] },
};

let queryClient: QueryClient;

const renderPage = () => {
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/backtest/${RUN_ID}`]}>
        <Routes>
          <Route path="/backtest/:runId" element={<BacktestDetailsV2 />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
};

const findStartBotButton = () => screen.findByRole('button', { name: 'Start Bot' });

const findNotice = async () =>
  (
    await screen.findByRole('heading', {
      name: 'These risk limits are not available on live bots yet',
    })
  ).closest('section') as HTMLElement;

describe('BacktestDetailsV2 promote to live: unenforced risk controls', () => {
  beforeEach(() => {
    Object.values(mocks.api).forEach((mock) => mock.mockReset());
    mocks.getBacktestStatus.mockReset();

    mocks.getBacktestStatus.mockResolvedValue({ data: { status: 'completed' } });
    mocks.api.getBacktest.mockResolvedValue({ data: completedBacktest });
    mocks.api.getStrategy.mockResolvedValue({ data: { id: 42, name: 'Live candidate' } });
    mocks.api.getBacktestAnalytics.mockResolvedValue({ data: {} });
    mocks.api.getBacktestPositionSnapshots.mockResolvedValue({ data: {} });
    mocks.api.getBacktestTradesDetailed.mockResolvedValue({ data: {} });
    mocks.api.createStrategyFromBacktest.mockResolvedValue({ data: { id: 42 } });
    mocks.api.startStrategyRuntime.mockResolvedValue({ data: { instance_id: 'inst-1' } });
    mocks.api.disableUnenforcedRiskControls.mockResolvedValue({ data: { id: 42 } });
  });

  afterEach(() => cleanup());

  it('describes what a live bot enforces instead of promising the same risk limits', async () => {
    renderPage();
    await findStartBotButton();

    expect(
      screen.getByText(/Max drawdown and trailing stop are not available on live bots yet\./)
    ).toBeVisible();
    expect(screen.queryByText(/same markets, risk limits, timeframe/)).toBeNull();
  });

  it('asks before starting, then turns the limits off and starts the same strategy', async () => {
    mocks.api.getStrategyStartReadiness
      .mockResolvedValueOnce(blockedByRiskControls())
      .mockResolvedValueOnce(readyReadiness);
    renderPage();

    fireEvent.click(await findStartBotButton());
    const notice = await findNotice();

    expect(mocks.api.startStrategyRuntime).not.toHaveBeenCalled();
    expect(mocks.api.disableUnenforcedRiskControls).not.toHaveBeenCalled();
    // The controls own their sentences: no run-on error repeating them.
    expect(screen.queryByText(new RegExp(DRAWDOWN_MESSAGE.slice(0, 24)))).toBeNull();

    const confirm = within(notice).getByRole('button', { name: 'Turn off and start bot' });
    expect(confirm).toBeDisabled();
    fireEvent.click(within(notice).getByRole('checkbox'));
    fireEvent.click(confirm);

    await waitFor(() => expect(mocks.api.startStrategyRuntime).toHaveBeenCalledTimes(1));
    expect(mocks.api.disableUnenforcedRiskControls).toHaveBeenCalledWith(
      42,
      ['max_drawdown_pct', 'trailing_stop_pct'],
      'testnet'
    );
    expect(mocks.api.startStrategyRuntime).toHaveBeenCalledWith(42, 'testnet');
    expect(mocks.api.createStrategyFromBacktest).toHaveBeenCalledTimes(1);
    expect(
      await screen.findByText(
        'Live bot started for strategy #42 (inst-1). Turned off on this strategy: Max drawdown, Trailing stop.'
      )
    ).toBeVisible();
    expect(
      screen.queryByRole('heading', {
        name: 'These risk limits are not available on live bots yet',
      })
    ).toBeNull();
  });

  it('lists the remaining blockers when the bot is still not ready afterwards', async () => {
    mocks.api.getStrategyStartReadiness
      .mockResolvedValueOnce(blockedByRiskControls())
      .mockResolvedValueOnce({
        success: true,
        data: {
          ready: false,
          blockers: [KEY_MESSAGE, COLLATERAL_MESSAGE],
          warnings: [],
          unenforced_risk_controls: [],
        },
      });
    renderPage();

    fireEvent.click(await findStartBotButton());
    const notice = await findNotice();
    fireEvent.click(within(notice).getByRole('checkbox'));
    fireEvent.click(within(notice).getByRole('button', { name: 'Turn off and start bot' }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('The live bot cannot start yet:');
    expect(
      within(alert)
        .getAllByRole('listitem')
        .map((item) => item.textContent)
    ).toEqual([`• ${KEY_MESSAGE}`, `• ${COLLATERAL_MESSAGE}`]);
    expect(mocks.api.startStrategyRuntime).not.toHaveBeenCalled();
    expect(
      screen.getByText('Turned off on strategy #42: Max drawdown, Trailing stop.')
    ).toBeVisible();
    expect(
      screen.queryByRole('heading', {
        name: 'These risk limits are not available on live bots yet',
      })
    ).toBeNull();
  });

  it('keeps the notice and shows the API error when turning the limits off fails', async () => {
    mocks.api.getStrategyStartReadiness.mockResolvedValue(blockedByRiskControls());
    mocks.api.disableUnenforcedRiskControls.mockRejectedValue(
      new Error('acknowledged must be true')
    );
    renderPage();

    fireEvent.click(await findStartBotButton());
    const notice = await findNotice();
    fireEvent.click(within(notice).getByRole('checkbox'));
    fireEvent.click(within(notice).getByRole('button', { name: 'Turn off and start bot' }));

    expect(await within(notice).findByRole('alert')).toHaveTextContent('acknowledged must be true');
    expect(mocks.api.getStrategyStartReadiness).toHaveBeenCalledTimes(1);
    expect(mocks.api.startStrategyRuntime).not.toHaveBeenCalled();
  });

  it('reuses the created strategy on retry even after the run metadata is refetched', async () => {
    mocks.api.getStrategyStartReadiness.mockResolvedValue(blockedByRiskControls([KEY_MESSAGE]));
    renderPage();

    fireEvent.click(await findStartBotButton());
    const notice = await findNotice();
    // Other blockers are visible next to the decision, not hidden behind it.
    expect(screen.getByRole('alert')).toHaveTextContent('Also blocking the live bot:');
    expect(screen.getByText(`• ${KEY_MESSAGE}`)).toBeVisible();

    fireEvent.click(within(notice).getByRole('button', { name: 'Cancel' }));
    await waitFor(() =>
      expect(
        screen.queryByRole('heading', {
          name: 'These risk limits are not available on live bots yet',
        })
      ).toBeNull()
    );
    expect(screen.queryByRole('alert')).toBeNull();

    // The server does not link the run to the promoted strategy, so a metadata
    // refetch drops the client-side strategy_id patch.
    queryClient.setQueryData(['backtests', 'detail', RUN_ID, 'meta'], { ...completedBacktest });

    fireEvent.click(await findStartBotButton());
    await findNotice();

    expect(mocks.api.createStrategyFromBacktest).toHaveBeenCalledTimes(1);
    expect(mocks.api.getStrategyStartReadiness).toHaveBeenCalledTimes(2);
    expect(mocks.api.getStrategyStartReadiness).toHaveBeenLastCalledWith(42, 'testnet');
  });

  it('drops a pending decision when the runtime network changes', async () => {
    mocks.api.getStrategyStartReadiness.mockResolvedValue(blockedByRiskControls());
    renderPage();

    fireEvent.click(await findStartBotButton());
    await findNotice();

    fireEvent.change(screen.getByLabelText('Runtime network'), { target: { value: 'mainnet' } });

    expect(
      screen.queryByRole('heading', {
        name: 'These risk limits are not available on live bots yet',
      })
    ).toBeNull();
    expect(mocks.api.disableUnenforcedRiskControls).not.toHaveBeenCalled();
  });
});
