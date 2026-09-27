// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Strategy } from '../store/strategies';
import { AIStrategyAdvisor } from './AIStrategyAdvisor';

const mocks = vi.hoisted(() => ({
  api: {
    getAIMarketStatus: vi.fn(),
    suggestStrategyParams: vi.fn(),
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

const strategy: Strategy = {
  id: 7,
  name: 'Pairs Alpha',
  runtime_network: 'testnet',
  runtime_subaccount: 0,
  selected_markets: ['BTC-USD', 'ETH-USD'],
  zscore_threshold: 1.5,
  usd_per_trade: 100,
  max_drawdown_pct: 20,
  max_history_days: 90,
};

const evidenceSummary = {
  completed_runs: 5,
  trades_analysed: 312,
  pairs_analysed: 12,
  live_closed_trades: 9,
  live_open_positions: 2,
  live_available: true,
  cointegrated_pairs: 4,
  data_notes: ['Fees are unknown for 2 trades.'],
};

const suggestions = [
  {
    parameter: 'usd_per_trade',
    label: 'Size per trade',
    unit: 'USD',
    current: 100,
    suggested: 50,
    rationale: 'Smaller positions keep single losses small.',
    evidence: 'Average losing trade 4.1 USD over 312 trades.',
    risk: 'money',
    backtest_only: false,
  },
  {
    parameter: 'max_drawdown_pct',
    label: 'Maximum drawdown',
    unit: '%',
    current: 20,
    suggested: 15,
    rationale: 'Stops the bot before the worst observed drawdown.',
    evidence: 'Worst run drawdown 18.2%.',
    risk: 'risk_control',
    backtest_only: false,
  },
  {
    parameter: 'max_history_days',
    label: 'Backtest history',
    unit: 'days',
    current: 90,
    suggested: 120,
    rationale: 'More history for the statistics window.',
    evidence: '5 completed runs used 90 days each.',
    risk: 'normal',
    backtest_only: true,
  },
];

const RENDERED_LINES = [
  "1. usd_per_trade: Current '100' -> Suggested '50'. Rationale: smaller positions.",
  "2. max_drawdown_pct: Current '20' -> Suggested '15'. Rationale: earlier stop.",
].join('\n');

const structuredResponse = () => ({
  success: true,
  data: {
    provider: 'grok',
    model: 'grok-4.7',
    used_ai: true,
    content: RENDERED_LINES,
    summary: 'Trade smaller and stop earlier.',
    suggestions,
    dropped: [{ parameter: 'place_trades', reason: 'not an editable parameter' }],
    data_gaps: ['No mainnet live trades yet.'],
    evidence_summary: evidenceSummary,
  },
  timestamp: '2026-09-27T10:00:00Z',
});

const renderAdvisor = (props: Partial<React.ComponentProps<typeof AIStrategyAdvisor>> = {}) => {
  const onApplyParams = vi.fn(async (params: Partial<Strategy>) =>
    Object.keys(params).map((key) => key as keyof Strategy)
  );
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <AIStrategyAdvisor strategy={strategy} onApplyParams={onApplyParams} {...props} />
    </QueryClientProvider>
  );
  return { onApplyParams };
};

const runButton = () => screen.getByRole('button', { name: 'Suggest Parameters' });

const waitForProvider = async () => {
  await waitFor(() =>
    expect(screen.getByLabelText('AI provider for parameter suggestions')).toHaveValue('grok')
  );
};

describe('AIStrategyAdvisor', () => {
  beforeEach(() => {
    window.localStorage.clear();
    Object.values(mocks.api).forEach((mock) => mock.mockReset());
    mocks.api.getAIMarketStatus.mockResolvedValue({
      data: { providers: [providerStatus('grok', true), providerStatus('deepseek', false)] },
    });
  });

  afterEach(() => cleanup());

  it('sends the strategy id only and renders the evidence, gaps and typed rows', async () => {
    mocks.api.suggestStrategyParams.mockResolvedValue(structuredResponse());
    renderAdvisor();
    await waitForProvider();

    fireEvent.click(runButton());

    expect(await screen.findByText('5 completed runs')).toBeVisible();
    expect(mocks.api.suggestStrategyParams).toHaveBeenCalledTimes(1);
    expect(mocks.api.suggestStrategyParams).toHaveBeenCalledWith({
      provider: 'grok',
      strategy_id: 7,
      max_suggestions: 8,
    });
    const payload = mocks.api.suggestStrategyParams.mock.calls[0]?.[0] as Record<string, unknown>;
    for (const forbidden of [
      'runtime_subaccount',
      'current_params',
      'recent_backtests',
      'last_error',
      'strategy_name',
    ]) {
      expect(payload).not.toHaveProperty(forbidden);
    }

    // Evidence chips, notes and data gaps.
    const evidence = screen.getByRole('list', { name: 'Evidence' });
    expect(within(evidence).getByText('312 trades')).toBeVisible();
    expect(within(evidence).getByText('12 pairs')).toBeVisible();
    expect(within(evidence).getByText('4 cointegrated pairs')).toBeVisible();
    expect(within(evidence).getByText('live: 9 closed, 2 open')).toBeVisible();
    expect(screen.getByText('Fees are unknown for 2 trades.')).toBeVisible();
    expect(screen.getByText('Data gaps')).toBeVisible();
    expect(screen.getByText('No mainnet live trades yet.')).toBeVisible();
    expect(screen.getByText('Trade smaller and stop earlier.')).toBeVisible();

    // Structured rows with labels, units, evidence and the chat's badge semantics.
    expect(screen.getByText('3 suggestions pending')).toBeVisible();
    expect(screen.getByText('Size per trade')).toBeVisible();
    expect(screen.getByText('100 USD')).toBeVisible();
    expect(screen.getByText('50 USD')).toBeVisible();
    expect(screen.getByText('20%')).toBeVisible();
    expect(screen.getByText('15%')).toBeVisible();
    expect(screen.getByText('Average losing trade 4.1 USD over 312 trades.')).toBeVisible();
    expect(screen.getByText('Changes trade size')).toBeVisible();
    expect(screen.getByText('Changes a risk limit')).toBeVisible();
    expect(screen.getByText('Backtest only')).toBeVisible();
    expect(screen.getByText('place_trades')).toBeVisible();
    // The rendered lines repeat the rows, so they stay hidden.
    expect(screen.queryByText(/Current '100'/)).toBeNull();
  });

  it('applies the selected keys with typed values from the structured suggestions', async () => {
    mocks.api.suggestStrategyParams.mockResolvedValue(structuredResponse());
    const { onApplyParams } = renderAdvisor();
    await waitForProvider();

    fireEvent.click(runButton());
    fireEvent.click(await screen.findByRole('button', { name: 'Apply Size per trade' }));

    const dialog = await screen.findByRole('dialog', { name: 'Confirm AI parameter updates' });
    expect(within(dialog).getByText('100 USD')).toBeVisible();
    expect(within(dialog).getByText('50 USD')).toBeVisible();
    expect(within(dialog).getByText('Average losing trade 4.1 USD over 312 trades.')).toBeVisible();
    expect(within(dialog).getByText('Changes trade size')).toBeVisible();

    fireEvent.click(within(dialog).getByRole('button', { name: 'Confirm Apply (Enter)' }));

    await waitFor(() => expect(onApplyParams).toHaveBeenCalledTimes(1));
    expect(onApplyParams).toHaveBeenCalledWith({ usd_per_trade: 50 });
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(screen.queryByRole('button', { name: 'Apply Size per trade' })).toBeNull();
    expect(screen.getByText('2 suggestions pending')).toBeVisible();

    fireEvent.click(screen.getByRole('button', { name: 'Review & Apply All' }));
    const allDialog = await screen.findByRole('dialog', { name: 'Confirm AI parameter updates' });
    expect(within(allDialog).getByText('2 fields pending')).toBeVisible();
    fireEvent.click(within(allDialog).getByRole('button', { name: 'Confirm Apply (Enter)' }));

    await waitFor(() => expect(onApplyParams).toHaveBeenCalledTimes(2));
    expect(onApplyParams).toHaveBeenNthCalledWith(2, {
      max_drawdown_pct: 15,
      max_history_days: 120,
    });
    expect(await screen.findByText('All 3 suggestions applied ✓')).toBeVisible();
  });

  it('marks the keys the parent did not apply as not editable on this page', async () => {
    mocks.api.suggestStrategyParams.mockResolvedValue(structuredResponse());
    const onApplyParams = vi.fn(async () => ['usd_per_trade'] as Array<keyof Strategy>);
    renderAdvisor({ onApplyParams });
    await waitForProvider();

    fireEvent.click(runButton());
    fireEvent.click(await screen.findByRole('button', { name: 'Review & Apply All' }));
    const dialog = await screen.findByRole('dialog', { name: 'Confirm AI parameter updates' });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Confirm Apply (Enter)' }));

    await waitFor(() => expect(onApplyParams).toHaveBeenCalledTimes(1));
    expect(onApplyParams).toHaveBeenCalledWith({
      usd_per_trade: 50,
      max_drawdown_pct: 15,
      max_history_days: 120,
    });
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());

    // The applied row is gone; the two the parent skipped leave the pending
    // state with a note in place of their Apply button.
    expect(screen.getByText('1 of 3 suggestions applied ✓')).toBeVisible();
    expect(screen.queryByText('Size per trade')).toBeNull();
    expect(screen.getByText('Maximum drawdown')).toBeVisible();
    expect(screen.getByText('Backtest history')).toBeVisible();
    expect(screen.getAllByText('Not editable on this page')).toHaveLength(2);
    expect(screen.queryByRole('button', { name: /^Apply / })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Review & Apply All' })).toBeNull();
    expect(screen.queryByText(/No suggestions were applied/)).toBeNull();
  });

  it('uses the first available provider when the status is already cached on mount', async () => {
    mocks.api.suggestStrategyParams.mockResolvedValue(structuredResponse());
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(['ai-market-filters', 'status'], {
      providers: [providerStatus('grok', true), providerStatus('deepseek', false)],
    });
    render(
      <QueryClientProvider client={queryClient}>
        <AIStrategyAdvisor strategy={strategy} onApplyParams={vi.fn()} />
      </QueryClientProvider>
    );

    // The default (deepseek) is not available; nothing changes after mount
    // that could repair it, so the fallback has to hold on the first render.
    expect(screen.getByLabelText('AI provider for parameter suggestions')).toHaveValue('grok');
    fireEvent.click(runButton());

    expect(await screen.findByText('5 completed runs')).toBeVisible();
    expect(mocks.api.suggestStrategyParams).toHaveBeenCalledWith({
      provider: 'grok',
      strategy_id: 7,
      max_suggestions: 8,
    });
  });

  it('asks for the strategy to be saved first in create mode', async () => {
    renderAdvisor({ strategy: { ...strategy, id: -1, name: 'Draft Strategy' } });
    await waitForProvider();

    expect(
      screen.getByText('Save the strategy first to get suggestions based on its backtests.')
    ).toBeVisible();
    expect(runButton()).toBeDisabled();
    fireEvent.click(runButton());
    expect(mocks.api.suggestStrategyParams).not.toHaveBeenCalled();
  });

  it('shows the server text and the evidence when the analysis was unavailable', async () => {
    mocks.api.suggestStrategyParams.mockResolvedValue({
      success: true,
      data: {
        provider: 'grok',
        model: 'grok-4.7',
        used_ai: false,
        content: 'AI analysis unavailable: the provider did not answer in time.',
        summary: '',
        suggestions: [],
        dropped: [],
        data_gaps: [],
        evidence_summary: {
          completed_runs: 3,
          trades_analysed: 0,
          pairs_analysed: 0,
          live_closed_trades: 0,
          live_open_positions: 0,
          live_available: false,
          cointegrated_pairs: 0,
          data_notes: [],
        },
      },
    });
    renderAdvisor();
    await waitForProvider();

    fireEvent.click(runButton());

    expect(
      await screen.findByText('AI analysis unavailable: the provider did not answer in time.')
    ).toBeVisible();
    const evidence = screen.getByRole('list', { name: 'Evidence' });
    expect(within(evidence).getByText('3 completed runs')).toBeVisible();
    expect(within(evidence).queryByText(/live:/)).toBeNull();
    // The provider is configured, so the missing-key hint would be wrong here.
    expect(screen.queryByText(/No key is configured/)).toBeNull();
    expect(screen.queryByRole('button', { name: /^Apply / })).toBeNull();
  });

  it('falls back to the numbered lines when the reply has no structured suggestions', async () => {
    mocks.api.suggestStrategyParams.mockResolvedValue({
      success: true,
      data: { provider: 'grok', used_ai: true, content: RENDERED_LINES },
    });
    const { onApplyParams } = renderAdvisor();
    await waitForProvider();

    fireEvent.click(runButton());

    expect(await screen.findByText(/Current '100'/)).toBeVisible();
    expect(screen.getByText('2 suggestions pending')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Apply max_drawdown_pct' }));
    const dialog = await screen.findByRole('dialog', { name: 'Confirm AI parameter updates' });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Confirm Apply (Enter)' }));

    await waitFor(() => expect(onApplyParams).toHaveBeenCalledWith({ max_drawdown_pct: 15 }));
  });

  it('shows the backend error text when the request fails', async () => {
    mocks.api.suggestStrategyParams.mockRejectedValue(
      new Error('CHAT_RATE_LIMITED: too many requests, try again in a minute')
    );
    renderAdvisor();
    await waitForProvider();

    fireEvent.click(runButton());

    expect(
      await screen.findByText('CHAT_RATE_LIMITED: too many requests, try again in a minute')
    ).toBeVisible();
  });
});
