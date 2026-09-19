import { describe, expect, it } from 'vitest';
import { clearUserScopedQueries, queryClient } from './queryClient';

describe('queryClient defaults', () => {
  it('never retries mutations automatically (trading POSTs are not idempotent)', () => {
    expect(queryClient.getDefaultOptions().mutations?.retry).toBe(0);
  });

  it('clearUserScopedQueries drops user data but keeps the public queries the shell renders from', () => {
    queryClient.setQueryData(['public', 'app-config'], { registration_enabled: true });
    queryClient.setQueryData(['strategies', 'list'], [{ id: 1 }]);
    queryClient.setQueryData(['portal', 'balances'], { usd: 10 });

    clearUserScopedQueries();

    expect(queryClient.getQueryData(['public', 'app-config'])).toEqual({ registration_enabled: true });
    expect(queryClient.getQueryData(['strategies', 'list'])).toBeUndefined();
    expect(queryClient.getQueryData(['portal', 'balances'])).toBeUndefined();
  });
});
