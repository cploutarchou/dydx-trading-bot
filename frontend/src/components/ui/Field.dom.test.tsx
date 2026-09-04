// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { Field } from './Field';

describe('Field', () => {
  afterEach(() => cleanup());

  it('associates the label with the control so getByLabelText resolves', () => {
    render(
      <Field label="USD Per Trade">
        <input type="number" defaultValue={10} />
      </Field>
    );
    const input = screen.getByLabelText('USD Per Trade') as HTMLInputElement;
    expect(input.tagName).toBe('INPUT');
    expect(input.getAttribute('id')).toBeTruthy();
  });

  it('wires hint and error into aria-describedby and flags aria-invalid', () => {
    render(
      <Field label="Start Date" hint="Trailing window" error="Start must precede end">
        <input type="date" />
      </Field>
    );
    const input = screen.getByLabelText('Start Date');
    const describedBy = input.getAttribute('aria-describedby') ?? '';
    expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(screen.getByText('Trailing window').id).toBeTruthy();
    expect(screen.getByText('Start must precede end').id).toBeTruthy();
    expect(describedBy).toContain(screen.getByText('Trailing window').id);
    expect(describedBy).toContain(screen.getByText('Start must precede end').id);
  });

  it('announces errors with role=alert', () => {
    render(
      <Field label="Mnemonic" error="Phrase is required">
        <input type="password" />
      </Field>
    );
    expect(screen.getByRole('alert')).toHaveTextContent('Phrase is required');
  });

  it('preserves an explicit id on the control instead of generating one', () => {
    render(
      <Field label="Instance ID">
        <input id="bot-instance-id" type="text" />
      </Field>
    );
    expect(screen.getByLabelText('Instance ID').id).toBe('bot-instance-id');
  });

  it('renders a required marker without breaking the accessible name lookup', () => {
    render(
      <Field label="Address" required>
        <input type="text" />
      </Field>
    );
    expect(screen.getByLabelText(/^Address/)).toBeTruthy();
  });
});
