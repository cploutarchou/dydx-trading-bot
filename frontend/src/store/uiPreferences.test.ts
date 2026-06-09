import { describe, expect, it } from 'vitest';
import { resolveTheme } from './uiPreferences';

describe('ui preference theme helpers', () => {
  it('resolves explicit light and dark themes without changing behavior', () => {
    expect(resolveTheme('light')).toBe('light');
    expect(resolveTheme('dark')).toBe('dark');
  });
});
