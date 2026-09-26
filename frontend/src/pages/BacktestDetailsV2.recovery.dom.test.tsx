// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { BacktestDetailsV2 } from './BacktestDetailsV2';

const RUN_ID = 'run-d588de9f0885';

const mocks = vi.hoisted(() => ({
  api: {
    getBacktest: vi.fn(),
    getStrategy: vi.fn(),
    getBacktestAnalytics: vi.fn(),
    getBacktestPositionSnapshots: vi.fn(),
    getBacktestTradesDetailed: vi.fn(),
  },
  getBacktestStatus: vi.fn(),
  progressData: undefined as Record<string, unknown> | undefined,
}));

vi.mock('../api', () => ({ default: mocks.api }));
vi.mock('../api/botApi', () => ({ botApi: { getBacktestStatus: mocks.getBacktestStatus } }));
vi.mock('../api/hooks', () => ({
  useBacktestProgress: () => ({
    data: mocks.progressData,
    lastSocketEvent: null,
    progressPercent: 40,
    progressSource: 'http',
    etaSeconds: null,
    currentPair: null,
    isConnected: false,
  }),
}));
vi.mock('../store/auth', () => ({
  useAuthStore: (selector: (_state: { user: { role: string } }) => unknown) =>
    selector({ user: { role: 'admin' } }),
}));
vi.mock('../components/AIBacktestExplainer', () => ({ AIBacktestExplainer: () => null }));
vi.mock('../components/BacktestLightweightChart', () => ({ BacktestLightweightChart: () => null }));
vi.mock('../components/BacktestPositionsPanel', () => ({ BacktestPositionsPanel: () => null }));
vi.mock('../components/BacktestResultsEnhanced', () => ({ BacktestResultsEnhanced: () => null }));
vi.mock('../components/BacktestTradesPanel', () => ({ BacktestTradesPanel: () => null }));

const renderPage = () => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
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

const repairButton = () => screen.queryByRole('button', { name: /Repair & Restart/ });

describe('BacktestDetailsV2 recovery status', () => {
  beforeEach(() => {
    Object.values(mocks.api).forEach((mock) => mock.mockReset());
    mocks.getBacktestStatus.mockReset();
    mocks.progressData = undefined;
    mocks.api.getBacktestAnalytics.mockResolvedValue({ data: {} });
    mocks.api.getBacktestPositionSnapshots.mockResolvedValue({ data: {} });
    mocks.api.getBacktestTradesDetailed.mockResolvedValue({ data: {} });
    mocks.getBacktestStatus.mockResolvedValue({
      run_id: RUN_ID,
      status: 'RUNNING',
      progress_percent: 40,
      updated_at: '0001-01-01T00:00:00Z',
    });
  });

  afterEach(() => cleanup());

  it('loads the run record for an active run and offers no repair when the request is stored', async () => {
    mocks.api.getBacktest.mockResolvedValue({
      data: {
        run_id: RUN_ID,
        status: 'running',
        restartable: false,
        request_available: true,
        request: { start_date: '2026-08-01', end_date: '2026-09-01' },
      },
    });
    renderPage();

    expect(await screen.findByText('Request payload available')).toBeVisible();
    expect(mocks.api.getBacktest).toHaveBeenCalledWith(RUN_ID);
    expect(repairButton()).toBeNull();
    expect(screen.getByRole('button', { name: 'Restart' })).toBeDisabled();
    expect(screen.queryByText(/0001-01-01/)).toBeNull();
  });

  it('says the request was not checked when the run record cannot load', async () => {
    mocks.api.getBacktest.mockRejectedValue(new Error('timeout'));
    renderPage();

    expect(await screen.findByText('Request payload not checked')).toBeVisible();
    expect(screen.queryByText('Request payload missing')).toBeNull();
    expect(repairButton()).toBeNull();
  });

  it('offers repair to an admin only when the bot reports the request missing', async () => {
    mocks.getBacktestStatus.mockResolvedValue({
      run_id: RUN_ID,
      status: 'FAILED',
      progress_percent: 60,
    });
    mocks.api.getBacktest.mockResolvedValue({
      data: {
        run_id: RUN_ID,
        status: 'failed',
        restartable: true,
        request_available: false,
      },
    });
    renderPage();

    expect(await screen.findByText('Request payload missing')).toBeVisible();
    expect(repairButton()).not.toBeNull();
  });

  it('takes request availability from the live status when the detail record lacks it', async () => {
    mocks.progressData = { run_id: RUN_ID, status: 'COMPLETED', request_available: true };
    mocks.api.getBacktest.mockResolvedValue({
      data: { run_id: RUN_ID, status: 'completed', restartable: true },
    });
    renderPage();

    expect(await screen.findByText('Request payload available')).toBeVisible();
    expect(screen.queryByText('Request payload not checked')).toBeNull();
    expect(repairButton()).toBeNull();
  });
});

describe('BacktestDetailsV2 risk and data checks', () => {
  beforeEach(() => {
    Object.values(mocks.api).forEach((mock) => mock.mockReset());
    mocks.getBacktestStatus.mockReset();
    mocks.progressData = undefined;
    mocks.api.getBacktestAnalytics.mockResolvedValue({ data: {} });
    mocks.api.getBacktestPositionSnapshots.mockResolvedValue({ data: {} });
    mocks.api.getBacktestTradesDetailed.mockResolvedValue({ data: {} });
    mocks.getBacktestStatus.mockResolvedValue({ run_id: RUN_ID, status: 'COMPLETED' });
  });

  afterEach(() => cleanup());

  it('shows the data source, the drawdown halt, exposure and removed prints', async () => {
    mocks.progressData = {
      run_id: RUN_ID,
      status: 'COMPLETED',
      request_available: true,
      request: {
        initial_balance: 100,
        _task_context: {
          metadata: {
            market_data_network: 'mainnet',
            drawdown_halt: {
              limit_pct: 10,
              reached: true,
              reached_at: '2026-09-02T00:00:00Z',
              trades_skipped: 7,
            },
            open_exposure: {
              peak_open_positions: 12,
              peak_open_notional_usd: 120,
              initial_balance: 100,
              exceeds_balance: true,
            },
            history_fetch_telemetry: { total_bad_prints_dropped: 3, markets: {} },
          },
        },
      },
    };
    mocks.api.getBacktest.mockResolvedValue({
      data: { run_id: RUN_ID, status: 'completed', total_pnl: 5 },
    });
    renderPage();

    expect(await screen.findByText('Market data: mainnet history')).toBeVisible();
    expect(screen.getByText(/Drawdown limit 10% reached 2026-09-02/)).toBeVisible();
    expect(screen.getByText(/7 later entries skipped/)).toBeVisible();
    expect(screen.getByText(/Peak open exposure 12/)).toHaveTextContent('more than the balance');
    expect(screen.getByText(/3 bad price prints removed/)).toBeVisible();
    expect(screen.getByText(/on \$100(\.00)? starting balance/)).toBeVisible();
    expect(screen.queryByText(/test capital/)).toBeNull();
  });

  it('says the checks were not recorded for an older run', async () => {
    mocks.api.getBacktest.mockResolvedValue({ data: { run_id: RUN_ID, status: 'completed' } });
    renderPage();

    expect(await screen.findByText(/Not recorded: this run predates these checks/)).toBeVisible();
    expect(screen.getByText('Starting balance not loaded yet')).toBeVisible();
  });
});

describe('BacktestDetailsV2 tab badges', () => {
  beforeEach(() => {
    Object.values(mocks.api).forEach((mock) => mock.mockReset());
    mocks.getBacktestStatus.mockReset();
    mocks.progressData = undefined;
    mocks.getBacktestStatus.mockResolvedValue({ run_id: RUN_ID, status: 'COMPLETED' });
    mocks.api.getBacktest.mockResolvedValue({
      data: { run_id: RUN_ID, status: 'completed', total_trades: 12 },
    });
  });

  afterEach(() => cleanup());

  it('says "Not loaded" for tabs that load on first open, not "Loading…"', async () => {
    renderPage();

    await screen.findByText('12 trades');
    expect(screen.queryByText('Loading…')).toBeNull();
    expect(screen.getAllByText('Not loaded')).toHaveLength(2);
    // Nothing is fetched until the tab is opened.
    expect(mocks.api.getBacktestAnalytics).not.toHaveBeenCalled();
    expect(mocks.api.getBacktestPositionSnapshots).not.toHaveBeenCalled();
  });
});
