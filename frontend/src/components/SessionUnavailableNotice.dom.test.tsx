// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SessionUnavailableNotice } from './SessionUnavailableNotice';

const storeState = {
  initializeSession: vi.fn(() => Promise.resolve()),
  logout: vi.fn(),
  sessionLoading: false,
};

vi.mock('../store/auth', () => ({
  useAuthStore: (selector: (state: typeof storeState) => unknown) => selector(storeState),
}));

describe('SessionUnavailableNotice', () => {
  beforeEach(() => {
    storeState.initializeSession.mockClear();
    storeState.logout.mockClear();
    storeState.sessionLoading = false;
  });

  afterEach(() => {
    cleanup();
  });

  it('says the user is still signed in and retries the bootstrap on demand', () => {
    render(<SessionUnavailableNotice />);

    expect(screen.getByRole('alert')).toHaveTextContent('You have not been signed out');

    fireEvent.click(screen.getByRole('button', { name: 'Retry now' }));

    expect(storeState.initializeSession).toHaveBeenCalledTimes(1);
    expect(storeState.logout).not.toHaveBeenCalled();
  });

  it('only ends the session through the explicit sign out', () => {
    render(<SessionUnavailableNotice />);

    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));

    expect(storeState.logout).toHaveBeenCalledTimes(1);
    expect(storeState.initializeSession).not.toHaveBeenCalled();
  });

  it('disables retry while a bootstrap pass is already running', () => {
    storeState.sessionLoading = true;

    render(<SessionUnavailableNotice />);

    expect(screen.getByRole('button', { name: 'Retrying…' })).toBeDisabled();
  });
});
