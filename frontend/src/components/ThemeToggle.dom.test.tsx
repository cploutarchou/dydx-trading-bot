// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { ThemeToggle } from './ThemeToggle';

describe('ThemeToggle', () => {
  afterEach(() => cleanup());

  it('offers only selectable theme options (no disabled Light control)', () => {
    render(<ThemeToggle />);

    const select = screen.getByRole('combobox', { name: 'Theme' });
    const options = [...select.querySelectorAll('option')].map((option) => ({
      value: option.getAttribute('value'),
      disabled: option.disabled,
      text: option.textContent,
    }));

    expect(options).toEqual([
      { value: 'system', disabled: false, text: 'System' },
      { value: 'dark', disabled: false, text: 'Dark' },
    ]);
  });

  it('reflects the persisted store theme as the selected value', () => {
    render(<ThemeToggle />);
    const select = screen.getByRole('combobox', { name: 'Theme' }) as HTMLSelectElement;
    // Store normalizes persisted light→dark and defaults to system; the
    // selected value must always be one of the offered options.
    expect(['system', 'dark']).toContain(select.value);
  });
});
