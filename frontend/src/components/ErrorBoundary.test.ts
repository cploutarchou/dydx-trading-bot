import { describe, expect, it } from 'vitest';
import { shouldIgnoreGlobalError } from './ErrorBoundary';

describe('shouldIgnoreGlobalError', () => {
  it('ignores ResizeObserver noise', () => {
    expect(
      shouldIgnoreGlobalError({
        message: 'ResizeObserver loop limit exceeded',
        filename: '',
        target: null,
      } as ErrorEvent)
    ).toBe(true);
  });

  it('does not ignore regular application errors', () => {
    expect(
      shouldIgnoreGlobalError({
        message: 'Cannot read properties of undefined (reading \'map\')',
        filename: 'https://executionlab.io/assets/index.js',
        target: null,
      } as ErrorEvent)
    ).toBe(false);
  });
});
