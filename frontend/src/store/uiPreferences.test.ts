import { describe, expect, it } from 'vitest';
import { resolveTheme } from './uiPreferences';

describe('ui preference theme helpers', () => {
  it('forces dark mode while light mode is temporarily disabled', () => {
    expect(resolveTheme('light')).toBe('dark');
    expect(resolveTheme('dark')).toBe('dark');
    expect(resolveTheme('system')).toBe('dark');
  });
});
