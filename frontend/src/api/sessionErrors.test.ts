import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios';
import { describe, expect, it } from 'vitest';
import { describeSessionError, isAuthRejection } from './sessionErrors';
import { traceHeaderName } from './trace';

const responseError = (
  status: number,
  headers: Record<string, string> = {},
  data: unknown = {}
): AxiosError =>
  new AxiosError(
    `Request failed with status code ${status}`,
    'ERR_BAD_RESPONSE',
    undefined,
    undefined,
    {
      status,
      statusText: '',
      headers,
      data,
      config: { headers: new AxiosHeaders() },
    } as AxiosResponse
  );

describe('isAuthRejection', () => {
  it('is true only for a 401 or 403 response', () => {
    expect(isAuthRejection(responseError(401))).toBe(true);
    expect(isAuthRejection(responseError(403))).toBe(true);
    expect(isAuthRejection(responseError(404))).toBe(false);
    expect(isAuthRejection(responseError(429))).toBe(false);
    expect(isAuthRejection(responseError(500))).toBe(false);
    expect(isAuthRejection(responseError(502))).toBe(false);
  });

  it('never treats a request that got no answer as a rejection', () => {
    expect(isAuthRejection(new AxiosError('Network Error', 'ERR_NETWORK'))).toBe(false);
    expect(isAuthRejection(new AxiosError('timeout of 4000ms exceeded', 'ECONNABORTED'))).toBe(
      false
    );
    expect(isAuthRejection(new AxiosError('canceled', 'ERR_CANCELED'))).toBe(false);
    expect(isAuthRejection(new Error('restoreSession timed out after 10000ms'))).toBe(false);
    expect(isAuthRejection(undefined)).toBe(false);
    expect(isAuthRejection(null)).toBe(false);
  });
});

describe('describeSessionError', () => {
  it('reads the trace id from the response header', () => {
    const summary = describeSessionError(
      responseError(503, { [traceHeaderName.toLowerCase()]: 'req-abc123' })
    );
    expect(summary).toEqual({
      message: 'Request failed with status code 503',
      status: 503,
      traceId: 'req-abc123',
    });
  });

  it('falls back to the trace id in the body, then to null', () => {
    expect(describeSessionError(responseError(500, {}, { trace_id: 'req-body' })).traceId).toBe(
      'req-body'
    );
    expect(describeSessionError(new AxiosError('Network Error', 'ERR_NETWORK'))).toEqual({
      message: 'Network Error',
      status: null,
      traceId: null,
    });
  });

  it('summarises a plain error without a status', () => {
    expect(describeSessionError(new Error('restoreSession timed out after 10000ms'))).toEqual({
      message: 'restoreSession timed out after 10000ms',
      status: null,
      traceId: null,
    });
    expect(describeSessionError('boom').message).toBe('boom');
  });
});
