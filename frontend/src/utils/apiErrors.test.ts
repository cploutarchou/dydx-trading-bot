import { describe, expect, it } from 'vitest';
import { humanizeApiError } from './apiErrors';

const httpError = (status?: number, message = 'Request failed with status code 502', code?: string) => {
  const error = new Error(message) as Error & { response?: { status?: number }; code?: string };
  if (status !== undefined) error.response = { status };
  if (code) error.code = code;
  return error;
};

describe('humanizeApiError', () => {
  it('maps upstream gateway failures to an actionable sentence', () => {
    expect(humanizeApiError(httpError(502))).toBe(
      'An upstream service is unreachable. Verify the bot service is running, then retry.'
    );
  });

  it('maps 401/403 to session/permission guidance', () => {
    expect(humanizeApiError(httpError(401))).toContain('session may have expired');
    expect(humanizeApiError(httpError(403))).toContain('does not have permission');
  });

  it('includes the status code for unmapped statuses', () => {
    expect(humanizeApiError(httpError(418))).toContain('status 418');
  });

  it('maps network errors when only the axios code survives', () => {
    expect(humanizeApiError(httpError(undefined, 'Network Error', 'ERR_NETWORK'))).toContain(
      'backend could not be reached'
    );
  });

  it('keeps a readable message when the status was stripped', () => {
    expect(humanizeApiError(httpError(undefined))).toContain('status 502');
  });

  it('passes through meaningful Error messages', () => {
    expect(humanizeApiError(new Error('Choose a start date that comes before the end date.'))).toBe(
      'Choose a start date that comes before the end date.'
    );
  });

  it('handles strings and unknown shapes without throwing', () => {
    expect(humanizeApiError('service restarting')).toBe('service restarting');
    expect(humanizeApiError({ weird: true })).toContain('Something went wrong');
    expect(humanizeApiError(null)).toContain('Something went wrong');
  });

  it('prefixes an optional surface context', () => {
    expect(humanizeApiError(httpError(503), 'Arbitrage intelligence')).toMatch(
      /^Arbitrage intelligence — /
    );
  });
});
