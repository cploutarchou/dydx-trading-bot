import { describe, expect, it } from 'vitest';
import { queryClient } from './queryClient';

describe('queryClient defaults', () => {
  it('never retries mutations automatically (trading POSTs are not idempotent)', () => {
    expect(queryClient.getDefaultOptions().mutations?.retry).toBe(0);
  });
});
