import { describe, expect, it } from 'vitest';
import {
    PRODUCTION_API_BASE_URL,
    STAGING_API_BASE_URL,
    resolveApiBaseUrl,
    resolveBackendUrl,
    resolveBackendWebSocketUrl,
    shouldAttemptCookieSessionBootstrap,
} from './origin';

describe('backend origin helpers', () => {
  it.each([
    'staging.executionlab.io',
    'staging-admin.executionlab.io',
    'staging-anything.executionlab.io',
  ])('routes staging hostname %s to the staging API', (hostname) => {
    expect(
      resolveApiBaseUrl({
        dev: false,
        locationLike: { protocol: 'https:', host: hostname, hostname },
        buildTimeApiBaseUrl: '',
        runtimeConfig: null,
      })
    ).toBe(STAGING_API_BASE_URL);
  });

  it.each(['executionlab.io', 'www.executionlab.io', 'app.executionlab.io', 'admin.executionlab.io'])(
    'routes production hostname %s to the production API',
    (hostname) => {
      expect(
        resolveApiBaseUrl({
          dev: false,
          locationLike: { protocol: 'https:', host: hostname, hostname },
          buildTimeApiBaseUrl: '',
          runtimeConfig: null,
        })
      ).toBe(PRODUCTION_API_BASE_URL);
    }
  );

  it('uses local API configuration for localhost development', () => {
    expect(
      resolveApiBaseUrl({
        dev: true,
        locationLike: { protocol: 'http:', host: 'localhost:5173', hostname: 'localhost' },
        buildTimeApiBaseUrl: 'http://localhost:8888',
        runtimeConfig: null,
      })
    ).toBe('http://localhost:8888');
  });

  it('prioritizes valid deployment runtime configuration over hostname detection', () => {
    expect(
      resolveApiBaseUrl({
        dev: false,
        locationLike: {
          protocol: 'https:',
          host: 'staging.executionlab.io',
          hostname: 'staging.executionlab.io',
        },
        buildTimeApiBaseUrl: '',
        runtimeConfig: { apiBaseUrl: STAGING_API_BASE_URL },
      })
    ).toBe(STAGING_API_BASE_URL);
  });

  it('rejects unapproved configured API URLs and safely falls back to production', () => {
    expect(
      resolveApiBaseUrl({
        dev: false,
        locationLike: {
          protocol: 'https:',
          host: 'executionlab.io',
          hostname: 'executionlab.io',
        },
        buildTimeApiBaseUrl: 'https://attacker.example.com',
        runtimeConfig: { apiBaseUrl: 'https://evil.executionlab.io' },
      })
    ).toBe(PRODUCTION_API_BASE_URL);
  });

  it('rejects staging API configuration on production hostnames', () => {
    expect(
      resolveApiBaseUrl({
        dev: false,
        locationLike: {
          protocol: 'https:',
          host: 'app.executionlab.io',
          hostname: 'app.executionlab.io',
        },
        buildTimeApiBaseUrl: STAGING_API_BASE_URL,
        runtimeConfig: { apiBaseUrl: STAGING_API_BASE_URL },
      })
    ).toBe(PRODUCTION_API_BASE_URL);
  });

  it('does not require window during SSR-safe resolution', () => {
    expect(
      resolveApiBaseUrl({
        dev: false,
        buildTimeApiBaseUrl: '',
        runtimeConfig: null,
        locationLike: undefined,
      })
    ).toBe(PRODUCTION_API_BASE_URL);
  });

  it('routes login, whitelist, admin, and websocket consumers through the same staging host', () => {
    const baseUrl = resolveApiBaseUrl({
      dev: false,
      locationLike: {
        protocol: 'https:',
        host: 'staging-admin.executionlab.io',
        hostname: 'staging-admin.executionlab.io',
      },
      buildTimeApiBaseUrl: '',
      runtimeConfig: null,
    });

    expect(resolveBackendUrl('/api/v1/auth/login', baseUrl)).toBe(
      'https://api.staging.executionlab.io/api/v1/auth/login'
    );
    expect(resolveBackendUrl('/api/v1/public/ico/whitelist', baseUrl)).toBe(
      'https://api.staging.executionlab.io/api/v1/public/ico/whitelist'
    );
    expect(resolveBackendUrl('/api/v1/admin/ico/readiness', baseUrl)).toBe(
      'https://api.staging.executionlab.io/api/v1/admin/ico/readiness'
    );
    expect(resolveBackendWebSocketUrl('/ws/strategies', 'jwt-token', baseUrl)).toBe(
      'wss://api.staging.executionlab.io/ws/strategies?access_token=jwt-token'
    );
  });

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
      resolveBackendWebSocketUrl(
        '/api/v1/backtests/run-123/live',
        'jwt-token',
        'http://localhost:8888'
      )
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
        host: 'app.executionlab.io',
      })
    ).toBe('wss://app.executionlab.io/ws/strategies?access_token=jwt-token');
  });

  it('preserves explicit websocket URLs while normalizing auth query params', () => {
    expect(resolveBackendWebSocketUrl('wss://backend.executionlab.io/ws/bots/bot-1', 'jwt-token')).toBe(
      'wss://backend.executionlab.io/ws/bots/bot-1?access_token=jwt-token'
    );
  });

  it('attempts cookie session bootstrap for hosted https deployments even without local hints', () => {
    expect(
      shouldAttemptCookieSessionBootstrap('https://api.executionlab.io', {
        protocol: 'https:',
        host: 'executionlab.io',
      })
    ).toBe(true);
  });

  it('avoids cookie session bootstrap for localhost development flows', () => {
    expect(
      shouldAttemptCookieSessionBootstrap('http://localhost:8888', {
        protocol: 'http:',
        host: 'localhost:5173',
      })
    ).toBe(false);
  });

  it('attempts cookie session bootstrap for secure same-origin proxy deployments', () => {
    expect(
      shouldAttemptCookieSessionBootstrap('', {
        protocol: 'https:',
        host: 'executionlab.io',
      })
    ).toBe(true);
  });
});
