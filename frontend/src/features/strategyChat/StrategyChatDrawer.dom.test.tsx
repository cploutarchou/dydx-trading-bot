// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiRequestError } from '../../api/requestError';
import { StrategyChatDrawer } from './StrategyChatDrawer';

const RUNNING_COPY =
  'This strategy is running. The change is saved now and only takes effect after you stop and start it.';

const mocks = vi.hoisted(() => ({
  api: {
    getAIMarketStatus: vi.fn(),
    getStrategyChat: vi.fn(),
    startStrategyChatSession: vi.fn(),
    sendStrategyChatMessage: vi.fn(),
    applyStrategyChatProposal: vi.fn(),
    createStrategyFromChatProposal: vi.fn(),
    dismissStrategyChatProposal: vi.fn(),
  },
}));

vi.mock('../../api', () => ({ default: mocks.api }));

type ChatState = {
  session: Record<string, unknown> | null;
  messages: Array<Record<string, unknown>>;
  runtime_active: boolean;
};

const SESSION = {
  id: 11,
  strategy_id: 7,
  title: 'Pairs Alpha chat',
  created_at: '2026-09-26T10:00:00Z',
  updated_at: '2026-09-26T10:00:00Z',
};

const providerStatus = (provider: string, available: boolean, model: string) => ({
  provider,
  enabled: available,
  available,
  availability_status: available ? 'available' : 'not_configured',
  shared_key_available: available,
  user_key_available: false,
  active_key_source: available ? 'shared' : 'none',
  model,
});

const userMessage = (id: number, content: string) => ({
  id,
  session_id: SESSION.id,
  role: 'user',
  content,
  proposal: null,
  proposal_status: null,
  proposal_result: null,
  provider: '',
  model: '',
  created_at: '2026-09-26T10:00:00Z',
});

const assistantMessage = (id: number, content: string, extra: Record<string, unknown> = {}) => ({
  id,
  session_id: SESSION.id,
  role: 'assistant',
  content,
  proposal: null,
  proposal_status: null,
  proposal_result: null,
  provider: 'grok',
  model: 'grok-4.3',
  created_at: '2026-09-26T10:00:05Z',
  ...extra,
});

const proposal = {
  kind: 'update',
  title: 'Tighter entries',
  summary: 'Trade less often and stop earlier.',
  suggested_name: '',
  changes: [
    {
      field: 'zscore_threshold',
      label: 'Z-score entry threshold',
      unit: '',
      current: 1.5,
      proposed: 2,
      reason: 'Fewer, stronger signals.',
      risk: 'normal',
      backtest_only: false,
    },
    {
      field: 'usd_per_trade',
      label: 'USD per trade',
      unit: 'USD',
      current: 100,
      proposed: 50,
      reason: 'Smaller positions.',
      risk: 'money',
      backtest_only: false,
    },
    {
      field: 'max_drawdown_pct',
      label: 'Max drawdown',
      unit: '%',
      current: 20,
      proposed: 15,
      reason: 'Stop the bot earlier.',
      risk: 'risk_control',
      backtest_only: false,
    },
  ],
  dropped: [{ field: 'place_trades', value: false, reason: 'The assistant cannot change it.' }],
};

const ALL_FIELDS = ['zscore_threshold', 'usd_per_trade', 'max_drawdown_pct'];

const proposalMessage = (extra: Record<string, unknown> = {}) =>
  assistantMessage(2, 'Here is a safer setup.', {
    proposal,
    proposal_status: 'pending',
    ...extra,
  });

// What the fake backend currently stores; GET always reads it, so refetches
// after an apply see the updated proposal just like the real server.
const server = { state: null as ChatState | null };

const setServerState = (state: ChatState) => {
  server.state = state;
};

const setProposalOutcome = (extra: Record<string, unknown>) => {
  const message = proposalMessage(extra);
  if (server.state) {
    server.state = {
      ...server.state,
      messages: server.state.messages.map((item) => (item.id === message.id ? message : item)),
    };
  }
  return message;
};

const newQueryClient = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });

const renderDrawer = (onClose = vi.fn(), queryClient = newQueryClient()) => {
  const { unmount } = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <StrategyChatDrawer strategyId={7} strategyName="Pairs Alpha" onClose={onClose} />
      </MemoryRouter>
    </QueryClientProvider>
  );
  return { onClose, queryClient, unmount };
};

const SEND_MUTATION_KEY = ['strategy-chat', 7, 'send'];

// Seed a settled send in the mutation cache, as a drawer that was closed
// mid-turn would leave behind.
const seedSend = (
  queryClient: QueryClient,
  status: 'error' | 'success',
  content: string,
  submittedAt: number
) => {
  const error = status === 'error' ? new ApiRequestError('AI timed out', 504, 'AI_TIMEOUT') : null;
  queryClient.getMutationCache().build(
    queryClient,
    { mutationKey: SEND_MUTATION_KEY },
    {
      context: undefined,
      data: undefined,
      error,
      failureCount: error ? 1 : 0,
      failureReason: error,
      isPaused: false,
      status,
      variables: { session_id: SESSION.id, content, provider: 'grok' },
      submittedAt,
    }
  );
};

const findComposer = () => screen.findByRole('textbox', { name: 'Message' });

describe('StrategyChatDrawer', () => {
  beforeEach(() => {
    Object.values(mocks.api).forEach((mock) => mock.mockReset());
    // DeepSeek is listed first by the backend; Grok must still be the default.
    mocks.api.getAIMarketStatus.mockResolvedValue({
      data: {
        providers: [
          providerStatus('deepseek', true, 'deepseek-v4'),
          providerStatus('grok', true, 'grok-4.3'),
          providerStatus('openai', false, 'gpt'),
        ],
      },
    });
    setServerState({ session: SESSION, messages: [], runtime_active: false });
    mocks.api.getStrategyChat.mockImplementation(async () => ({
      success: true,
      data: server.state,
    }));
  });

  afterEach(() => cleanup());

  it('renders the conversation with the proposal, its risk badges and dropped changes', async () => {
    setServerState({
      session: SESSION,
      messages: [userMessage(1, 'How is it doing?'), proposalMessage()],
      runtime_active: false,
    });
    renderDrawer();

    const dialog = await screen.findByRole('dialog', { name: 'Strategy assistant Pairs Alpha' });
    expect(await within(dialog).findByText('How is it doing?')).toBeVisible();
    expect(within(dialog).getByText('Here is a safer setup.')).toBeVisible();
    expect(within(dialog).getByRole('heading', { name: 'Tighter entries' })).toBeVisible();
    expect(within(dialog).getByText('Changes trade size')).toBeVisible();
    expect(within(dialog).getByText('Changes a risk limit')).toBeVisible();
    expect(within(dialog).getByText('20%')).toBeVisible();
    expect(within(dialog).getByText('15%')).toBeVisible();
    expect(within(dialog).getByText('50 USD')).toBeVisible();
    expect(within(dialog).getByText('place_trades')).toBeVisible();
    for (const name of ['Z-score entry threshold', 'USD per trade', 'Max drawdown']) {
      expect(within(dialog).getByRole('checkbox', { name })).toBeChecked();
    }
    expect(within(dialog).getByText(/not financial advice/)).toBeVisible();
    await waitFor(() => expect(within(dialog).getByLabelText('Provider')).toHaveValue('grok'));
  });

  it('shows the evidence chips under the assistant messages that carry them', async () => {
    setServerState({
      session: SESSION,
      messages: [
        userMessage(1, 'How did my recent backtests do?'),
        assistantMessage(2, 'Three runs completed; the last one lost on two pairs.', {
          evidence_summary: {
            completed_runs: 3,
            trades_analysed: 87,
            pairs_analysed: 7,
            live_closed_trades: 0,
            live_open_positions: 0,
            live_available: false,
            cointegrated_pairs: 2,
            data_notes: ['Live data was not available.'],
          },
        }),
        assistantMessage(3, 'An older reply without evidence.', { evidence_summary: null }),
      ],
      runtime_active: false,
    });
    renderDrawer();

    const dialog = await screen.findByRole('dialog', { name: 'Strategy assistant Pairs Alpha' });
    const evidence = await within(dialog).findByRole('list', { name: 'Evidence' });
    expect(within(evidence).getByText('3 completed runs')).toBeVisible();
    expect(within(evidence).getByText('87 trades')).toBeVisible();
    expect(within(evidence).getByText('7 pairs')).toBeVisible();
    expect(within(evidence).getByText('2 cointegrated pairs')).toBeVisible();
    expect(within(evidence).queryByText(/live:/)).toBeNull();
    // Chat chips stay small: no notes, and only the message with evidence gets them.
    expect(within(dialog).queryByText('Live data was not available.')).toBeNull();
    expect(within(dialog).getAllByRole('list', { name: 'Evidence' })).toHaveLength(1);
    expect(within(dialog).getByText('An older reply without evidence.')).toBeVisible();
  });

  it('sends a message with the session and Grok, and shows the reply', async () => {
    let resolveSend: (value: unknown) => void = () => undefined;
    mocks.api.sendStrategyChatMessage.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveSend = resolve;
        })
    );
    renderDrawer();

    const composer = await findComposer();
    await waitFor(() => expect(composer).toHaveFocus());
    expect(await screen.findByRole('button', { name: 'How can I reduce drawdown?' })).toBeVisible();
    await waitFor(() => expect(screen.getByLabelText('Provider')).toHaveValue('grok'));

    fireEvent.change(composer, { target: { value: 'Is the stop loss too tight?' } });
    expect(screen.getByText('27/4000')).toBeVisible();
    fireEvent.keyDown(composer, { key: 'Enter' });

    expect(await screen.findByText('Grok is thinking…')).toBeVisible();
    expect(mocks.api.sendStrategyChatMessage).toHaveBeenCalledTimes(1);
    expect(mocks.api.sendStrategyChatMessage).toHaveBeenCalledWith(7, {
      session_id: 11,
      content: 'Is the stop loss too tight?',
      provider: 'grok',
    });
    expect(composer).toBeDisabled();
    expect(composer).toHaveValue('');

    await act(async () => {
      resolveSend({
        success: true,
        data: {
          session: SESSION,
          messages: [
            userMessage(3, 'Is the stop loss too tight?'),
            assistantMessage(4, 'It is close to the typical spread move.'),
          ],
        },
      });
    });

    expect(await screen.findByText('It is close to the typical spread move.')).toBeVisible();
    await waitFor(() => expect(screen.queryByText('Grok is thinking…')).toBeNull());
    expect(screen.getAllByText('Is the stop loss too tight?')).toHaveLength(1);
    expect(composer).toBeEnabled();
  });

  it('keeps Shift+Enter as a newline instead of sending', async () => {
    renderDrawer();
    const composer = await findComposer();
    await waitFor(() => expect(screen.getByLabelText('Provider')).toHaveValue('grok'));

    fireEvent.change(composer, { target: { value: 'First line' } });
    fireEvent.keyDown(composer, { key: 'Enter', shiftKey: true });

    expect(mocks.api.sendStrategyChatMessage).not.toHaveBeenCalled();
  });

  it('applies only the checked changes', async () => {
    setServerState({ session: SESSION, messages: [proposalMessage()], runtime_active: false });
    mocks.api.applyStrategyChatProposal.mockImplementation(async () => ({
      success: true,
      data: {
        strategy: { id: 7 },
        message: setProposalOutcome({
          proposal_status: 'applied',
          proposal_result: {
            applied_fields: ['zscore_threshold', 'max_drawdown_pct'],
            at: '2026-09-26T10:01:00Z',
          },
        }),
      },
    }));
    renderDrawer();

    fireEvent.click(await screen.findByRole('checkbox', { name: 'USD per trade' }));
    expect(screen.getByText('2 of 3 selected')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Apply to strategy' }));

    await waitFor(() => expect(mocks.api.applyStrategyChatProposal).toHaveBeenCalledTimes(1));
    expect(mocks.api.applyStrategyChatProposal).toHaveBeenCalledWith(7, 2, {
      fields: ['zscore_threshold', 'max_drawdown_pct'],
    });
    expect(await screen.findByText('Applied 2 changes')).toBeVisible();
    expect(screen.getByText('Not applied')).toBeVisible();
    expect(screen.queryAllByRole('checkbox')).toHaveLength(0);
    expect(screen.queryByRole('button', { name: 'Apply to strategy' })).toBeNull();
  });

  it('asks for the running acknowledgement when the server requires it, then resends', async () => {
    setServerState({ session: SESSION, messages: [proposalMessage()], runtime_active: false });
    mocks.api.applyStrategyChatProposal
      .mockRejectedValueOnce(
        new ApiRequestError('Strategy is running', 409, 'STRATEGY_RUNNING_ACK_REQUIRED')
      )
      .mockImplementationOnce(async () => ({
        success: true,
        data: {
          strategy: { id: 7 },
          message: setProposalOutcome({
            proposal_status: 'applied',
            proposal_result: {
              applied_fields: ALL_FIELDS,
              acknowledged_running: true,
              at: '2026-09-26T10:01:00Z',
            },
          }),
        },
      }));
    renderDrawer();

    fireEvent.click(await screen.findByRole('button', { name: 'Apply to strategy' }));

    expect(await screen.findByText(RUNNING_COPY)).toBeVisible();
    expect(mocks.api.applyStrategyChatProposal).toHaveBeenCalledTimes(1);
    expect(mocks.api.applyStrategyChatProposal).toHaveBeenNthCalledWith(1, 7, 2, {
      fields: ALL_FIELDS,
    });
    expect(screen.queryByRole('alert')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(mocks.api.applyStrategyChatProposal).toHaveBeenCalledTimes(2));
    expect(mocks.api.applyStrategyChatProposal).toHaveBeenNthCalledWith(2, 7, 2, {
      fields: ALL_FIELDS,
      acknowledge_running: true,
    });
    expect(await screen.findByText('Applied 3 changes')).toBeVisible();
    expect(screen.getByText(/Saved while the strategy was running/)).toBeVisible();
  });

  it('shows the running consequence before any call when the strategy is running', async () => {
    setServerState({ session: SESSION, messages: [proposalMessage()], runtime_active: true });
    mocks.api.applyStrategyChatProposal.mockImplementation(async () => ({
      success: true,
      data: {
        strategy: { id: 7 },
        message: setProposalOutcome({
          proposal_status: 'applied',
          proposal_result: {
            applied_fields: ALL_FIELDS,
            acknowledged_running: true,
            at: '2026-09-26T10:01:00Z',
          },
        }),
      },
    }));
    renderDrawer();

    fireEvent.click(await screen.findByRole('button', { name: 'Apply to strategy' }));

    expect(await screen.findByText(RUNNING_COPY)).toBeVisible();
    expect(mocks.api.applyStrategyChatProposal).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(mocks.api.applyStrategyChatProposal).toHaveBeenCalledTimes(1));
    expect(mocks.api.applyStrategyChatProposal).toHaveBeenCalledWith(7, 2, {
      fields: ALL_FIELDS,
      acknowledge_running: true,
    });
    expect(await screen.findByText('Applied 3 changes')).toBeVisible();
  });

  it('creates a new strategy with the chosen name and links to it', async () => {
    setServerState({ session: SESSION, messages: [proposalMessage()], runtime_active: true });
    mocks.api.createStrategyFromChatProposal.mockImplementation(async () => ({
      success: true,
      data: {
        strategy: { id: 99, name: 'Pairs Alpha Safer' },
        message: setProposalOutcome({
          proposal_status: 'created',
          proposal_result: {
            applied_fields: ALL_FIELDS,
            new_strategy_id: 99,
            new_strategy_name: 'Pairs Alpha Safer',
            at: '2026-09-26T10:01:00Z',
          },
        }),
      },
    }));
    renderDrawer();

    fireEvent.click(await screen.findByRole('button', { name: 'Create new strategy' }));
    const nameInput = screen.getByLabelText('New strategy name');
    expect(nameInput).toHaveValue('Pairs Alpha (variant)');

    fireEvent.change(nameInput, { target: { value: '  Pairs Alpha Safer ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create strategy' }));

    await waitFor(() => expect(mocks.api.createStrategyFromChatProposal).toHaveBeenCalledTimes(1));
    expect(mocks.api.createStrategyFromChatProposal).toHaveBeenCalledWith(7, 2, {
      name: 'Pairs Alpha Safer',
      fields: ALL_FIELDS,
    });
    // A new strategy never needs the running acknowledgement.
    expect(screen.queryByText(RUNNING_COPY)).toBeNull();
    expect(await screen.findByText('Created “Pairs Alpha Safer”')).toBeVisible();
    expect(screen.getByRole('link', { name: 'Open strategy' })).toHaveAttribute(
      'href',
      '/strategies/99/edit'
    );
    expect(mocks.api.applyStrategyChatProposal).not.toHaveBeenCalled();
  });

  it('dismisses a proposal', async () => {
    setServerState({ session: SESSION, messages: [proposalMessage()], runtime_active: false });
    mocks.api.dismissStrategyChatProposal.mockImplementation(async () => ({
      success: true,
      data: { message: setProposalOutcome({ proposal_status: 'dismissed' }) },
    }));
    renderDrawer();

    fireEvent.click(await screen.findByRole('button', { name: 'Dismiss' }));

    await waitFor(() => expect(mocks.api.dismissStrategyChatProposal).toHaveBeenCalledWith(7, 2));
    expect(await screen.findByText('Dismissed')).toBeVisible();
    expect(screen.queryAllByRole('checkbox')).toHaveLength(0);
  });

  it('shows the error, keeps the draft and retries it', async () => {
    mocks.api.sendStrategyChatMessage
      .mockRejectedValueOnce(new ApiRequestError('Too many requests', 429, 'CHAT_RATE_LIMITED'))
      .mockResolvedValueOnce({
        success: true,
        data: {
          session: SESSION,
          messages: [userMessage(3, 'Suggest safer settings'), assistantMessage(4, 'Try 2.0.')],
        },
      });
    renderDrawer();
    await waitFor(() => expect(screen.getByLabelText('Provider')).toHaveValue('grok'));

    fireEvent.click(await screen.findByRole('button', { name: 'Suggest safer settings' }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('You are sending messages too quickly.');
    expect(screen.getByRole('textbox', { name: 'Message' })).toHaveValue('Suggest safer settings');

    fireEvent.click(within(alert).getByRole('button', { name: 'Retry' }));

    await waitFor(() => expect(mocks.api.sendStrategyChatMessage).toHaveBeenCalledTimes(2));
    expect(mocks.api.sendStrategyChatMessage).toHaveBeenNthCalledWith(2, 7, {
      session_id: 11,
      content: 'Suggest safer settings',
      provider: 'grok',
    });
    expect(await screen.findByText('Try 2.0.')).toBeVisible();
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getByRole('textbox', { name: 'Message' })).toHaveValue('');
  });

  it('tells the user how to add a Grok key when no provider is available', async () => {
    mocks.api.getAIMarketStatus.mockResolvedValue({
      data: {
        providers: [
          providerStatus('grok', false, 'grok-4.3'),
          providerStatus('deepseek', false, 'deepseek-v4'),
        ],
      },
    });
    renderDrawer();

    expect(
      await screen.findByText(/An admin can add a Grok key in Settings → AI Filters/)
    ).toBeVisible();
    expect(screen.getByRole('textbox', { name: 'Message' })).toBeDisabled();
    expect(await screen.findByRole('button', { name: 'Suggest safer settings' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled();
    expect(screen.queryByLabelText('Provider')).toBeNull();
    expect(mocks.api.sendStrategyChatMessage).not.toHaveBeenCalled();
  });

  it('closes on Escape', async () => {
    const { onClose } = renderDrawer();
    const dialog = await screen.findByRole('dialog');

    fireEvent.keyDown(dialog, { key: 'Escape' });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('closes on Escape from the body while a turn runs', async () => {
    mocks.api.sendStrategyChatMessage.mockImplementation(() => new Promise(() => undefined));
    const { onClose } = renderDrawer();
    const composer = await findComposer();
    await waitFor(() => expect(screen.getByLabelText('Provider')).toHaveValue('grok'));

    fireEvent.change(composer, { target: { value: 'Is the stop loss too tight?' } });
    fireEvent.keyDown(composer, { key: 'Enter' });
    await waitFor(() => expect(composer).toBeDisabled());

    // Browsers drop focus to the body when the focused textarea is disabled.
    fireEvent.keyDown(document.body, { key: 'Escape' });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('closes on Escape after Apply on a running strategy replaced the focused button', async () => {
    setServerState({ session: SESSION, messages: [proposalMessage()], runtime_active: true });
    const { onClose } = renderDrawer();

    fireEvent.click(await screen.findByRole('button', { name: 'Apply to strategy' }));
    expect(await screen.findByText(RUNNING_COPY)).toBeVisible();

    fireEvent.keyDown(document.body, { key: 'Escape' });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('brings Tab back into the dialog when focus is outside it', async () => {
    renderDrawer();
    const composer = await findComposer();
    await waitFor(() => expect(composer).toHaveFocus());
    await waitFor(() => expect(screen.getByLabelText('Provider')).toHaveValue('grok'));

    composer.blur();
    expect(document.body).toHaveFocus();
    fireEvent.keyDown(document.body, { key: 'Tab' });
    expect(screen.getByRole('button', { name: 'Close chat' })).toHaveFocus();

    screen.getByRole('button', { name: 'Close chat' }).blur();
    fireEvent.keyDown(document.body, { key: 'Tab', shiftKey: true });
    // Send is disabled while the draft is empty, so the composer is the last stop.
    expect(composer).toHaveFocus();
  });

  it('restores a send that failed after the drawer was closed', async () => {
    let rejectSend: (reason: unknown) => void = () => undefined;
    mocks.api.sendStrategyChatMessage.mockImplementationOnce(
      () =>
        new Promise((_resolve, reject) => {
          rejectSend = reject;
        })
    );
    const queryClient = newQueryClient();
    const first = renderDrawer(vi.fn(), queryClient);
    const composer = await findComposer();
    await waitFor(() => expect(screen.getByLabelText('Provider')).toHaveValue('grok'));

    fireEvent.change(composer, { target: { value: 'Is the stop loss too tight?' } });
    fireEvent.keyDown(composer, { key: 'Enter' });
    expect(await screen.findByText('Grok is thinking…')).toBeVisible();

    first.unmount();
    await act(async () => {
      rejectSend(new ApiRequestError('AI timed out', 504, 'AI_TIMEOUT'));
    });

    mocks.api.sendStrategyChatMessage.mockResolvedValueOnce({
      success: true,
      data: {
        session: SESSION,
        messages: [userMessage(3, 'Is the stop loss too tight?'), assistantMessage(4, 'No.')],
      },
    });
    renderDrawer(vi.fn(), queryClient);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('The assistant took too long to answer. Try again.');
    expect(screen.getByRole('textbox', { name: 'Message' })).toHaveValue(
      'Is the stop loss too tight?'
    );
    expect(screen.queryByText('Grok is thinking…')).toBeNull();
    // The restore happens once: the failed mutation leaves the cache.
    await waitFor(() =>
      expect(queryClient.getMutationCache().findAll({ status: 'error' })).toHaveLength(0)
    );

    fireEvent.click(within(alert).getByRole('button', { name: 'Retry' }));

    await waitFor(() => expect(mocks.api.sendStrategyChatMessage).toHaveBeenCalledTimes(2));
    expect(mocks.api.sendStrategyChatMessage).toHaveBeenNthCalledWith(2, 7, {
      session_id: 11,
      content: 'Is the stop loss too tight?',
      provider: 'grok',
    });
    expect(await screen.findByText('No.')).toBeVisible();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('ignores a failed send that is older than the last successful one', async () => {
    const queryClient = newQueryClient();
    seedSend(queryClient, 'error', 'Old question', 1_000);
    seedSend(queryClient, 'success', 'Newer question', 2_000);
    renderDrawer(vi.fn(), queryClient);

    const composer = await findComposer();
    await waitFor(() => expect(screen.getByLabelText('Provider')).toHaveValue('grok'));

    expect(composer).toHaveValue('');
    expect(screen.queryByRole('alert')).toBeNull();
    expect(queryClient.getMutationCache().findAll({ status: 'error' })).toHaveLength(1);
  });

  it('keeps the loaded conversation when a refetch fails', async () => {
    setServerState({
      session: SESSION,
      messages: [userMessage(1, 'How is it doing?'), assistantMessage(2, 'Fine so far.')],
      runtime_active: false,
    });
    const { queryClient } = renderDrawer();
    expect(await screen.findByText('How is it doing?')).toBeVisible();

    mocks.api.getStrategyChat.mockRejectedValueOnce(
      new ApiRequestError('Bad gateway', 502, 'INTERNAL_ERROR')
    );
    // Apply and create invalidate ['strategies'], which covers the chat.
    await act(async () => {
      await queryClient.invalidateQueries({ queryKey: ['strategies'] });
    });

    const banner = await screen.findByRole('alert');
    expect(banner).toHaveTextContent('Could not refresh the conversation. Bad gateway');
    expect(screen.getByText('How is it doing?')).toBeVisible();
    expect(screen.getByText('Fine so far.')).toBeVisible();
    expect(screen.getByRole('textbox', { name: 'Message' })).toBeEnabled();

    fireEvent.click(within(banner).getByRole('button', { name: 'Try again' }));

    await waitFor(() => expect(screen.queryByRole('alert')).toBeNull());
    expect(screen.getByText('Fine so far.')).toBeVisible();
    expect(mocks.api.getStrategyChat).toHaveBeenCalledTimes(3);
  });

  it('closes on a backdrop click only when the press started on the backdrop', async () => {
    const { onClose } = renderDrawer();
    const dialog = await screen.findByRole('dialog');
    const backdrop = dialog.parentElement as HTMLElement;

    // A text selection that starts in the drawer and ends over the backdrop.
    fireEvent.pointerDown(dialog);
    fireEvent.click(backdrop);
    expect(onClose).not.toHaveBeenCalled();

    fireEvent.pointerDown(backdrop);
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('offers a retry when the provider status cannot be read', async () => {
    mocks.api.getAIMarketStatus.mockRejectedValueOnce(new Error('Bad gateway'));
    renderDrawer();

    const notice = await screen.findByRole('alert');
    expect(notice).toHaveTextContent('Could not check AI providers.');
    expect(screen.queryByText(/An admin can add a Grok key/)).toBeNull();
    expect(screen.getByRole('textbox', { name: 'Message' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled();
    expect(screen.queryByLabelText('Provider')).toBeNull();

    fireEvent.click(within(notice).getByRole('button', { name: 'Retry' }));

    await waitFor(() => expect(screen.getByLabelText('Provider')).toHaveValue('grok'));
    expect(screen.queryByRole('alert')).toBeNull();
    expect(mocks.api.getAIMarketStatus).toHaveBeenCalledTimes(2);
  });

  it('re-reads the chat after a stale session and retries with the current one', async () => {
    const newSession = { ...SESSION, id: 12 };
    mocks.api.sendStrategyChatMessage
      .mockRejectedValueOnce(new ApiRequestError('Chat session not found', 404, 'NOT_FOUND'))
      .mockResolvedValueOnce({
        success: true,
        data: {
          session: newSession,
          messages: [
            { ...userMessage(3, 'Suggest safer settings'), session_id: 12 },
            { ...assistantMessage(4, 'Try 2.0.'), session_id: 12 },
          ],
        },
      });
    const { queryClient } = renderDrawer();
    await waitFor(() => expect(screen.getByLabelText('Provider')).toHaveValue('grok'));
    // Another tab started a new chat; the server archived session 11.
    setServerState({ session: newSession, messages: [], runtime_active: false });

    fireEvent.click(await screen.findByRole('button', { name: 'Suggest safer settings' }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Chat session not found');
    expect(mocks.api.sendStrategyChatMessage).toHaveBeenNthCalledWith(1, 7, {
      session_id: 11,
      content: 'Suggest safer settings',
      provider: 'grok',
    });
    await waitFor(() =>
      expect(queryClient.getQueryData(['strategies', 7, 'chat'])).toMatchObject({
        session: { id: 12 },
      })
    );
    expect(mocks.api.getStrategyChat).toHaveBeenCalledTimes(2);

    fireEvent.click(within(alert).getByRole('button', { name: 'Retry' }));

    await waitFor(() => expect(mocks.api.sendStrategyChatMessage).toHaveBeenCalledTimes(2));
    expect(mocks.api.sendStrategyChatMessage).toHaveBeenNthCalledWith(2, 7, {
      session_id: 12,
      content: 'Suggest safer settings',
      provider: 'grok',
    });
    expect(await screen.findByText('Try 2.0.')).toBeVisible();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('labels a created result from applied_fields and unchanged_fields', async () => {
    setServerState({
      session: SESSION,
      messages: [
        proposalMessage({
          proposal_status: 'created',
          proposal_result: {
            applied_fields: [],
            unchanged_fields: ['zscore_threshold'],
            new_strategy_id: 99,
            new_strategy_name: 'Pairs Alpha Copy',
            at: '2026-09-26T10:01:00Z',
          },
        }),
      ],
      runtime_active: false,
    });
    renderDrawer();

    const dialog = await screen.findByRole('dialog');
    expect(await within(dialog).findByText('Created “Pairs Alpha Copy”')).toBeVisible();
    const zscoreRow = within(dialog).getByText('Z-score entry threshold').closest('li');
    expect(zscoreRow).toHaveTextContent('Already set');
    expect(zscoreRow).not.toHaveTextContent('Not applied');
    expect(within(dialog).getAllByText('Not applied')).toHaveLength(2);
    expect(within(dialog).getByText('USD per trade').closest('li')).toHaveTextContent(
      'Not applied'
    );
    expect(within(dialog).queryAllByRole('checkbox')).toHaveLength(0);
  });

  it('shows Applied without a count when the stored result is missing', async () => {
    setServerState({
      session: SESSION,
      messages: [proposalMessage({ proposal_status: 'applied', proposal_result: null })],
      runtime_active: false,
    });
    renderDrawer();

    const dialog = await screen.findByRole('dialog');
    expect(await within(dialog).findByText('Applied')).toBeVisible();
    expect(within(dialog).queryByText(/Applied \d/)).toBeNull();
    // Nothing is known to be written, so no change is shown as applied.
    expect(within(dialog).getAllByText('Not applied')).toHaveLength(3);
  });
});
