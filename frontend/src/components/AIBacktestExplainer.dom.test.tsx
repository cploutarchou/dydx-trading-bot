// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AIBacktestExplainer } from './AIBacktestExplainer';

const mocks = vi.hoisted(() => ({
  api: {
    getAIMarketStatus: vi.fn(),
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

const renderExplainer = (runId = 'run-1') =>
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <AIBacktestExplainer runId={runId} />
    </QueryClientProvider>
  );

describe('AIBacktestExplainer', () => {
  beforeEach(() => {
    Object.values(mocks.api).forEach((mock) => mock.mockReset());
    mocks.api.getAIMarketStatus.mockResolvedValue({
      data: { providers: [providerStatus('grok', true), providerStatus('deepseek', false)] },
    });
  });

  afterEach(() => cleanup());

  it('sends the run id and renders the evidence, narrative and improvements', async () => {
    mocks.api.explainBacktest.mockResolvedValue({
      success: true,
      data: {
        provider: 'grok',
        model: 'grok-4.7',
        used_ai: true,
        content:
          'The run closed 41 trades on 6 pairs; losses cluster in the last week.\nImprovements:\n1. Widen the entry threshold.\n2. Cap open pairs at 3.\n3. Shorten the timeout.',
        evidence_summary: {
          completed_runs: 1,
          trades_analysed: 41,
          pairs_analysed: 6,
          live_closed_trades: 0,
          live_open_positions: 0,
          live_available: false,
          cointegrated_pairs: 0,
          data_notes: ['Exit reasons are missing for 3 trades.'],
        },
      },
    });
    renderExplainer();
    await waitFor(() =>
      expect(screen.getByLabelText('AI provider for backtest explanation')).toHaveValue('grok')
    );

    fireEvent.click(screen.getByRole('button', { name: 'Explain with AI' }));

    expect(await screen.findByText(/closed 41 trades on 6 pairs/)).toBeVisible();
    expect(mocks.api.explainBacktest).toHaveBeenCalledTimes(1);
    expect(mocks.api.explainBacktest).toHaveBeenCalledWith({ provider: 'grok', run_id: 'run-1' });
    const evidence = screen.getByRole('list', { name: 'Evidence' });
    expect(within(evidence).getByText('1 completed run')).toBeVisible();
    expect(within(evidence).getByText('41 trades')).toBeVisible();
    expect(within(evidence).getByText('6 pairs')).toBeVisible();
    expect(within(evidence).queryByText(/live:/)).toBeNull();
    expect(screen.getByText('Exit reasons are missing for 3 trades.')).toBeVisible();
    expect(screen.getByText('Suggested Improvements')).toBeVisible();
    expect(screen.getByText(/Widen the entry threshold/)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Regenerate' })).toBeVisible();
  });

  it('keeps the button disabled without a run id', async () => {
    renderExplainer('');
    await waitFor(() =>
      expect(screen.getByLabelText('AI provider for backtest explanation')).toHaveValue('grok')
    );

    expect(screen.getByRole('button', { name: 'Explain with AI' })).toBeDisabled();
    expect(mocks.api.explainBacktest).not.toHaveBeenCalled();
  });
});
