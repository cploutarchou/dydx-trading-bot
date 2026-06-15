import { describe, expect, it } from 'vitest';
import { canSubmitLoginForm, getLoginFormErrors } from './loginForm';

describe('login form helpers', () => {
  it('requires username and password before submission', () => {
    expect(getLoginFormErrors({ username: '', password: '' })).toEqual({
      username: 'Enter your username or email.',
      password: 'Enter your password.',
    });
  });

  it('trims username but preserves password input semantics', () => {
    expect(getLoginFormErrors({ username: ' operator@example.com ', password: 'secret' })).toEqual({
      username: '',
      password: '',
    });
  });

  it('disables submission while incomplete or loading', () => {
    expect(canSubmitLoginForm({ username: '', password: 'secret', loading: false })).toBe(false);
    expect(canSubmitLoginForm({ username: 'operator', password: '', loading: false })).toBe(false);
    expect(canSubmitLoginForm({ username: 'operator', password: 'secret', loading: true })).toBe(
      false
    );
    expect(canSubmitLoginForm({ username: 'operator', password: 'secret', loading: false })).toBe(
      true
    );
  });
});
