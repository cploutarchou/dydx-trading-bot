import { beforeAll, describe, expect, it } from 'vitest';

let parseJsonResponse: typeof import('./enhancedClient').parseJsonResponse;
let resolveEnhancedApiUrl: typeof import('./enhancedClient').resolveEnhancedApiUrl;

beforeAll(async () => {
  Object.defineProperty(globalThis, 'localStorage', {
    value: {
      getItem: () => null,
      setItem: () => undefined,
      removeItem: () => undefined,
      clear: () => undefined,
    },
    configurable: true,
  });
  Object.defineProperty(globalThis, 'document', {
    value: { cookie: '' },
    configurable: true,
  });

  ({ parseJsonResponse, resolveEnhancedApiUrl } = await import('./enhancedClient'));
});

describe('enhanced API client helpers', () => {
  it('resolves bot API requests against the configured backend URL', () => {
    expect(resolveEnhancedApiUrl('/api/v1/bots', 'http://localhost:8888')).toBe(
      'http://localhost:8888/api/v1/bots'
    );
  });

  it('throws a readable error when HTML is returned instead of JSON', async () => {
    const response = new Response('<!doctype html><html><body>Not JSON</body></html>', {
      status: 200,
      headers: {
        'Content-Type': 'text/html',
      },
    });

    await expect(parseJsonResponse(response)).rejects.toThrow(/expected json/i);
  });
});
