// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { EntryHalt, EntryHaltState } from '../api';
import { EntryHaltNotice } from './EntryHaltNotice';

vi.mock('../api/hooks', () => ({
  useStrategyEntryHalt: () => ({ data: undefined }),
  useClearStrategyEntryHaltMutation: () => ({ mutate: vi.fn(), isPending: false }),
}));

const halt: EntryHalt = {
  id: 3,
  kind: 'unhedged_exposure',
  instance_id: 'strategy-85-2',
  network: 'testnet',
  address: 'dydx1example',
  subaccount_number: 0,
  reason: 'Failed to close hedged position for AVAX-USD',
  details: {
    market_1: 'AVAX-USD',
    market_2: 'FIL-USD',
    error: 'code 2001: Reduce-only orders cannot increase the position size',
  },
  halted_at: '2026-09-21T16:45:00+00:00',
};

const halted: EntryHaltState = { halted: true, unverified: false, halt };

const drawdownHalt: EntryHalt = {
  id: 7,
  kind: 'max_drawdown',
  instance_id: 'strategy-85-3',
  network: 'testnet',
  address: 'dydx1example',
  subaccount_number: 0,
  reason: 'max drawdown reached: equity 979.00 is 2.10% below its peak 1,000.00 (limit 2%)',
  details: {
    kind: 'max_drawdown',
    equity: 979,
    peak_equity: 1000,
    drawdown_pct: 2.1,
    limit_pct: 2,
  },
  halted_at: '2026-09-23T16:45:00+00:00',
};

describe('EntryHaltNotice', () => {
  afterEach(() => cleanup());

  it('renders nothing when entries are not halted or the state is unknown', () => {
    const { container, rerender } = render(
      <EntryHaltNotice
        state={{ halted: false, unverified: false, halt: null }}
        busy={false}
        error={null}
        onClear={vi.fn()}
      />
    );
    expect(container).toBeEmptyDOMElement();

    rerender(<EntryHaltNotice state={null} busy={false} error={null} onClear={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('shows the account, the pair, the reason and the raw failure', () => {
    render(<EntryHaltNotice state={halted} busy={false} error={null} onClear={vi.fn()} />);

    expect(screen.getByRole('heading', { name: 'New entries are halted' })).toBeVisible();
    expect(screen.getByText('Testnet · subaccount 0')).toBeVisible();
    expect(screen.getByText('AVAX-USD / FIL-USD')).toBeVisible();
    expect(screen.getByText('Failed to close hedged position for AVAX-USD')).toBeVisible();
    expect(screen.getByText(/code 2001: Reduce-only orders/)).toBeVisible();
    expect(screen.getByText(/keeps managing open positions and exits/)).toBeVisible();
  });

  it('clears only after the acknowledgement is ticked, and passes the note', () => {
    const onClear = vi.fn();
    render(<EntryHaltNotice state={halted} busy={false} error={null} onClear={onClear} />);

    const clearButton = screen.getByRole('button', { name: 'Clear halt and resume entries' });
    expect(clearButton).toBeDisabled();
    fireEvent.click(clearButton);
    expect(onClear).not.toHaveBeenCalled();

    fireEvent.click(
      screen.getByRole('checkbox', { name: /I checked testnet subaccount 0 on dYdX/ })
    );
    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'no AVAX position on chain' },
    });
    expect(clearButton).toBeEnabled();
    fireEvent.click(clearButton);
    expect(onClear).toHaveBeenCalledWith('no AVAX position on chain');
  });

  it('asks for the acknowledgement again when a different halt replaces the first', () => {
    const { rerender } = render(
      <EntryHaltNotice state={halted} busy={false} error={null} onClear={vi.fn()} />
    );
    fireEvent.click(screen.getByRole('checkbox'));
    expect(screen.getByRole('button', { name: 'Clear halt and resume entries' })).toBeEnabled();

    rerender(
      <EntryHaltNotice
        state={{ ...halted, halt: { ...halt, id: 4 } }}
        busy={false}
        error={null}
        onClear={vi.fn()}
      />
    );
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    expect(screen.getByRole('button', { name: 'Clear halt and resume entries' })).toBeDisabled();
  });

  it('names real funds in the mainnet acknowledgement', () => {
    render(
      <EntryHaltNotice
        state={{ ...halted, halt: { ...halt, network: 'mainnet', subaccount_number: 2 } }}
        busy={false}
        error={null}
        onClear={vi.fn()}
      />
    );
    expect(
      screen.getByRole('checkbox', { name: /I checked MAINNET subaccount 2 on dYdX.*real funds/ })
    ).toBeVisible();
  });

  it.each<[string, EntryHaltState]>([
    ['unverified', { halted: true, unverified: true, halt: null }],
    ['halted without a readable record', { halted: true, unverified: false, halt: null }],
  ])('offers nothing to clear when the state is %s', (_label, state) => {
    render(<EntryHaltNotice state={state} busy={false} error={null} onClear={vi.fn()} />);

    expect(
      screen.getByRole('heading', { name: 'Entry halt state could not be read' })
    ).toBeVisible();
    expect(screen.queryByRole('checkbox')).toBeNull();
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('explains a max drawdown halt with its figures and its own acknowledgement', () => {
    const onClear = vi.fn();
    render(
      <EntryHaltNotice
        state={{ halted: true, unverified: false, halt: drawdownHalt }}
        busy={false}
        error={null}
        onClear={onClear}
      />
    );

    expect(
      screen.getByRole('heading', { name: 'New entries are halted: max drawdown reached' })
    ).toBeVisible();
    expect(screen.getByText('$979.00')).toBeVisible();
    expect(screen.getByText('$1,000.00')).toBeVisible();
    expect(screen.getByText(/2\.1% \(limit 2%\)/)).toBeVisible();
    expect(screen.getByText(/starts a new drawdown measurement/)).toBeVisible();
    // Nothing about unhedged legs: that is a different check.
    expect(screen.queryByText(/without its hedge/)).toBeNull();

    const clearButton = screen.getByRole('button', { name: 'Clear halt and resume entries' });
    expect(clearButton).toBeDisabled();
    fireEvent.click(
      screen.getByRole('checkbox', {
        name: /I reviewed testnet subaccount 0 .*drawdown measured from its current equity/,
      })
    );
    fireEvent.click(clearButton);
    expect(onClear).toHaveBeenCalledWith('');
  });

  it('names real funds in the mainnet drawdown acknowledgement', () => {
    render(
      <EntryHaltNotice
        state={{
          halted: true,
          unverified: false,
          halt: { ...drawdownHalt, network: 'mainnet', subaccount_number: 1 },
        }}
        busy={false}
        error={null}
        onClear={vi.fn()}
      />
    );
    expect(
      screen.getByRole('checkbox', { name: /I reviewed MAINNET subaccount 1 .*Real funds/ })
    ).toBeVisible();
  });

  it('shows a failed clear and locks the form while busy', () => {
    render(<EntryHaltNotice state={halted} busy error="Bot API unavailable" onClear={vi.fn()} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Bot API unavailable');
    expect(screen.getByRole('checkbox')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Working...' })).toBeDisabled();
  });
});
