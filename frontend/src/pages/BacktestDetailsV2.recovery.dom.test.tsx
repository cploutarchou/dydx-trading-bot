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
}));

vi.mock('../api', () => ({ default: mocks.api }));
vi.mock('../api/botApi', () => ({ botApi: { getBacktestStatus: mocks.getBacktestStatus } }));
vi.mock('../api/hooks', () => ({
  useBacktestProgress: () => ({
    data: undefined,
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
});
