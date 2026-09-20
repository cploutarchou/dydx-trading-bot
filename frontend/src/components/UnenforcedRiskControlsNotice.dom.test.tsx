// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { UnenforcedRiskControl } from '../api';
import { UnenforcedRiskControlsNotice } from './UnenforcedRiskControlsNotice';

const maxDrawdown: UnenforcedRiskControl = {
  field: 'max_drawdown_pct',
  value: 15,
  message: 'max_drawdown_pct=15 is not enforced by the live runtime.',
};
const trailingStop: UnenforcedRiskControl = {
  field: 'trailing_stop_pct',
  value: 1,
  message: 'trailing_stop_pct=1 is not enforced by the live runtime.',
};
const unknownControl: UnenforcedRiskControl = {
  field: 'max_daily_loss_pct',
  value: 4,
  message: 'max_daily_loss_pct=4 is not enforced by the live runtime.',
};

describe('UnenforcedRiskControlsNotice', () => {
  afterEach(() => cleanup());

  it('renders nothing when there are no controls', () => {
    const { container } = render(
      <UnenforcedRiskControlsNotice
        controls={[]}
        network="testnet"
        busy={false}
        error={null}
        confirmLabel="Turn off and start bot"
        onConfirm={vi.fn()}
      />
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('lists each limit with a friendly label and its value as a percentage', () => {
    render(
      <UnenforcedRiskControlsNotice
        controls={[maxDrawdown, trailingStop]}
        network="testnet"
        busy={false}
        error={null}
        confirmLabel="Turn off and start bot"
        onConfirm={vi.fn()}
      />
    );

    expect(
      screen.getByRole('heading', { name: 'These risk limits are not available on live bots yet' })
    ).toBeVisible();
    expect(screen.getByText('Max drawdown').closest('li')).toHaveTextContent('Max drawdown15%');
    expect(screen.getByText('Trailing stop').closest('li')).toHaveTextContent('Trailing stop1%');
    expect(screen.getByText(/refuses to start with a limit it cannot enforce/)).toBeVisible();
    expect(screen.getByText(/The backtest did not apply these limits either/)).toBeVisible();
    expect(screen.getByText(/Live bots do enforce: stop loss, take profit/)).toBeVisible();
  });

  it('keeps the confirm button disabled until the acknowledgement is ticked', () => {
    const onConfirm = vi.fn();
    render(
      <UnenforcedRiskControlsNotice
        controls={[maxDrawdown, trailingStop]}
        network="testnet"
        busy={false}
        error={null}
        confirmLabel="Turn off and start bot"
        onConfirm={onConfirm}
      />
    );

    const checkbox = screen.getByRole('checkbox', {
      name: 'I understand this live bot will run without: Max drawdown, Trailing stop.',
    });
    const confirm = screen.getByRole('button', { name: 'Turn off and start bot' });

    expect(checkbox).not.toBeChecked();
    expect(confirm).toBeDisabled();
    fireEvent.click(confirm);
    expect(onConfirm).not.toHaveBeenCalled();

    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();
    expect(confirm).toBeEnabled();

    fireEvent.click(checkbox);
    expect(confirm).toBeDisabled();
  });

  it('passes only the resolvable fields to onConfirm', () => {
    const onConfirm = vi.fn();
    render(
      <UnenforcedRiskControlsNotice
        controls={[maxDrawdown, unknownControl, trailingStop]}
        network="testnet"
        busy={false}
        error={null}
        confirmLabel="Turn off for this strategy"
        onConfirm={onConfirm}
      />
    );

    // The unknown limit stays a plain blocker and is not part of the acknowledgement.
    expect(screen.getByText(`• ${unknownControl.message}`)).toBeVisible();
    fireEvent.click(
      screen.getByRole('checkbox', {
        name: 'I understand this live bot will run without: Max drawdown, Trailing stop.',
      })
    );
    fireEvent.click(screen.getByRole('button', { name: 'Turn off for this strategy' }));

    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onConfirm).toHaveBeenCalledWith(['max_drawdown_pct', 'trailing_stop_pct']);
  });

  it('renders an unknown field as a plain blocker without a checkbox or button', () => {
    render(
      <UnenforcedRiskControlsNotice
        controls={[unknownControl]}
        network="testnet"
        busy={false}
        error={null}
        confirmLabel="Turn off and start bot"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByText(`• ${unknownControl.message}`)).toBeVisible();
    expect(screen.queryByRole('checkbox')).toBeNull();
    expect(screen.queryByRole('button')).toBeNull();
    // Nothing is known about how the backtest treated a limit this screen does not recognise.
    expect(screen.queryByText(/The backtest did not apply these limits either/)).toBeNull();
  });

  it('spells out real funds in the acknowledgement on mainnet', () => {
    render(
      <UnenforcedRiskControlsNotice
        controls={[maxDrawdown]}
        network="mainnet"
        busy={false}
        error={null}
        confirmLabel="Turn off and start bot"
        onConfirm={vi.fn()}
      />
    );

    expect(
      screen.getByRole('checkbox', {
        name: 'I understand this MAINNET bot will trade real funds without: Max drawdown.',
      })
    ).not.toBeChecked();
    expect(screen.queryByText(/this live bot will run without/)).toBeNull();
  });

  it('drops a testnet acknowledgement when the network switches to mainnet', () => {
    const props = {
      controls: [maxDrawdown],
      busy: false,
      error: null,
      confirmLabel: 'Turn off for this strategy',
      onConfirm: vi.fn(),
    };
    const { rerender } = render(<UnenforcedRiskControlsNotice {...props} network="testnet" />);

    fireEvent.click(screen.getByRole('checkbox'));
    expect(screen.getByRole('button', { name: 'Turn off for this strategy' })).toBeEnabled();

    rerender(<UnenforcedRiskControlsNotice {...props} network="mainnet" />);

    expect(screen.getByRole('checkbox')).not.toBeChecked();
    expect(screen.getByRole('button', { name: 'Turn off for this strategy' })).toBeDisabled();
  });

  it('disables the controls while busy and announces the error', () => {
    const onCancel = vi.fn();
    const props = {
      controls: [maxDrawdown],
      network: 'testnet' as const,
      confirmLabel: 'Turn off and start bot',
      onConfirm: vi.fn(),
      onCancel,
    };
    const { rerender } = render(
      <UnenforcedRiskControlsNotice {...props} busy={false} error={null} />
    );

    fireEvent.click(screen.getByRole('checkbox'));
    rerender(<UnenforcedRiskControlsNotice {...props} busy error={null} />);

    expect(screen.getByRole('checkbox')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Working...' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled();

    rerender(<UnenforcedRiskControlsNotice {...props} busy={false} error="Strategy not found" />);

    expect(screen.getByRole('alert')).toHaveTextContent('Strategy not found');
    expect(screen.getByRole('button', { name: 'Turn off and start bot' })).toBeEnabled();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
