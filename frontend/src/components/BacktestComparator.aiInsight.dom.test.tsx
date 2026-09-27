// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { BacktestComparator } from './BacktestComparator';

const mocks = vi.hoisted(() => ({
  api: {
    getAIMarketStatus: vi.fn(),
    listBacktests: vi.fn(),
    explainBacktest: vi.fn(),
  },
}));

vi.mock('../api', () => ({ default: mocks.api }));

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

const RUN_A = 'aaaaaaaa-0000-4000-8000-000000000001';
const RUN_B = 'bbbbbbbb-0000-4000-8000-000000000002';
const RUN_C = 'cccccccc-0000-4000-8000-000000000003';

const run = (runId: string) => ({
  run_id: runId,
  total_return_pct: 5,
  total_pnl: 50,
  sharpe_ratio: 1.2,
  win_rate: 55,
  max_drawdown: 8,
  num_trades: 20,
  avg_trade_duration: 4,
  start_date: '2026-01-01T00:00:00Z',
  end_date: '2026-01-31T00:00:00Z',
  created_at: '2026-02-01T00:00:00Z',
  status: 'completed',
});

const narrative = (content: string) => ({ success: true, data: { content, used_ai: true } });

const IDLE_TEXT =
  'Use Refresh AI Insight to generate a narrative from the stored results of the baseline run.';

const renderComparator = () =>
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter>
        <BacktestComparator />
      </MemoryRouter>
    </QueryClientProvider>
  );

// A run card's accessible name starts with the first 8 characters of its id;
// the "Remove <run id>" chips of selected runs do not.
const runCard = (runId: string) =>
  screen.findByRole('button', { name: new RegExp(`^${runId.slice(0, 8)}`) });

const toggleRuns = async (...runIds: string[]) => {
  for (const runId of runIds) {
    fireEvent.click(await runCard(runId));
  }
};

const refreshButton = async () => {
  const button = await screen.findByRole('button', { name: 'Refresh AI Insight' });
  await waitFor(() => expect(button).toBeEnabled());
  return button;
};

describe('BacktestComparator AI insight', () => {
  beforeEach(() => {
    window.localStorage.clear();
    Object.values(mocks.api).forEach((mock) => mock.mockReset());
    mocks.api.getAIMarketStatus.mockResolvedValue({
      data: { providers: [providerStatus('grok', true), providerStatus('deepseek', false)] },
    });
    mocks.api.listBacktests.mockResolvedValue({
      success: true,
      data: { backtests: [run(RUN_A), run(RUN_B), run(RUN_C)] },
    });
  });

  afterEach(() => cleanup());

  it('requests the baseline explanation only when asked, never on selection', async () => {
    mocks.api.explainBacktest.mockResolvedValue(narrative('Baseline narrative.'));
    renderComparator();
    await toggleRuns(RUN_A, RUN_B);

    const refresh = await refreshButton();
    expect(screen.getByText(IDLE_TEXT)).toBeVisible();
    expect(mocks.api.explainBacktest).not.toHaveBeenCalled();

    fireEvent.click(refresh);

    expect(await screen.findByText('Baseline narrative.')).toBeVisible();
    expect(mocks.api.explainBacktest).toHaveBeenCalledTimes(1);
    expect(mocks.api.explainBacktest).toHaveBeenCalledWith({ provider: 'grok', run_id: RUN_A });
  });

  it('clears the error once a later request succeeds', async () => {
    mocks.api.explainBacktest
      .mockRejectedValueOnce(new Error('provider timed out'))
      .mockResolvedValueOnce(narrative('Second attempt.'));
    renderComparator();
    await toggleRuns(RUN_A, RUN_B);

    fireEvent.click(await refreshButton());
    expect(await screen.findByText('provider timed out')).toBeVisible();

    fireEvent.click(await refreshButton());
    expect(await screen.findByText('Second attempt.')).toBeVisible();
    expect(screen.queryByText('provider timed out')).toBeNull();
    expect(mocks.api.explainBacktest).toHaveBeenCalledTimes(2);
  });

  it('hides an insight requested for another baseline run', async () => {
    mocks.api.explainBacktest.mockResolvedValue(narrative('Baseline narrative.'));
    renderComparator();
    await toggleRuns(RUN_A, RUN_B);
    fireEvent.click(await refreshButton());
    expect(await screen.findByText('Baseline narrative.')).toBeVisible();

    // Dropping RUN_A makes RUN_B the baseline; the narrative was about RUN_A.
    await toggleRuns(RUN_A, RUN_C);

    expect(screen.queryByText('Baseline narrative.')).toBeNull();
    expect(screen.getByText(IDLE_TEXT)).toBeVisible();
    expect(mocks.api.explainBacktest).toHaveBeenCalledTimes(1);

    // Back to RUN_A as the baseline: the stored narrative applies again.
    await toggleRuns(RUN_B, RUN_C, RUN_A, RUN_B);

    expect(screen.getByText('Baseline narrative.')).toBeVisible();
    expect(mocks.api.explainBacktest).toHaveBeenCalledTimes(1);
  });

  it('drops the response of a request superseded by clearing the selection', async () => {
    let resolveFirst: (value: unknown) => void = () => undefined;
    mocks.api.explainBacktest
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveFirst = resolve;
          })
      )
      .mockResolvedValueOnce(narrative('Second narrative.'));
    renderComparator();
    await toggleRuns(RUN_A, RUN_B);
    fireEvent.click(await refreshButton());
    expect(await screen.findByText('Refreshing insight...')).toBeVisible();

    fireEvent.click(screen.getByRole('button', { name: 'Clear Selection' }));
    await toggleRuns(RUN_A, RUN_B);
    fireEvent.click(await refreshButton());
    expect(await screen.findByText('Second narrative.')).toBeVisible();

    await act(async () => {
      resolveFirst(narrative('First narrative.'));
    });

    expect(screen.getByText('Second narrative.')).toBeVisible();
    expect(screen.queryByText('First narrative.')).toBeNull();
    expect(mocks.api.explainBacktest).toHaveBeenCalledTimes(2);
  });
});
