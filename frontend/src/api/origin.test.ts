import { describe, expect, it } from 'vitest';
import { resolveBackendUrl, resolveBackendWebSocketUrl } from './origin';

describe('backend origin helpers', () => {
  it('resolves relative API requests against the backend origin', () => {
    expect(resolveBackendUrl('/api/v1/backtests', 'http://localhost:8888')).toBe(
      'http://localhost:8888/api/v1/backtests'
    );
  });

  it('keeps relative API paths when using the dev proxy', () => {
    expect(resolveBackendUrl('/api/v1/backtests', '')).toBe('/api/v1/backtests');
  });

  it('builds websocket URLs against the backend origin with access_token auth', () => {
    expect(
      resolveBackendWebSocketUrl('/api/v1/backtests/run-123/live', 'jwt-token', 'http://localhost:8888')
    ).toBe('ws://localhost:8888/api/v1/backtests/run-123/live?access_token=jwt-token');
  });

  it('keeps runtime websocket traffic on the backend origin rather than the bot service origin', () => {
    expect(resolveBackendWebSocketUrl('/ws/strategies', 'jwt-token', 'http://localhost:8888')).toBe(
      'ws://localhost:8888/ws/strategies?access_token=jwt-token'
    );
  });

  it('falls back to the current browser origin when using the dev proxy', () => {
    expect(
      resolveBackendWebSocketUrl('/ws/strategies', 'jwt-token', '', {
        protocol: 'https:',
        host: 'app.example.com',
      })
    ).toBe('wss://app.example.com/ws/strategies?access_token=jwt-token');
  });

  it('preserves explicit websocket URLs while normalizing auth query params', () => {
    expect(
      resolveBackendWebSocketUrl('wss://backend.example.com/ws/bots/bot-1', 'jwt-token')
    ).toBe('wss://backend.example.com/ws/bots/bot-1?access_token=jwt-token');
  });
});
