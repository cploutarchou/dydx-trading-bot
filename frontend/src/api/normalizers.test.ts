import { describe, expect, it } from 'vitest';
import { getEnvelopeList, getEnvelopeValue, toApiRecord } from './normalizers';

describe('API response normalizers', () => {
  it('extracts nested envelope values before root fallback values', () => {
    const payload = {
      status: 'ROOT',
      data: {
        status: 'RUNNING',
      },
    };

    expect(getEnvelopeValue(payload, 'status')).toBe('RUNNING');
  });

  it('falls back to root values when an endpoint is not enveloped', () => {
    expect(getEnvelopeValue({ status: 'COMPLETED' }, 'status')).toBe('COMPLETED');
  });

  it('extracts list payloads from supported nested or root keys', () => {
    expect(getEnvelopeList({ data: { backtests: [{ run_id: 'run-1' }] } }, ['backtests'])).toEqual([
      { run_id: 'run-1' },
    ]);
    expect(getEnvelopeList({ runs: [{ run_id: 'run-2' }] }, ['backtests', 'runs'])).toEqual([
      { run_id: 'run-2' },
    ]);
  });

  it('returns empty objects and lists for malformed payloads', () => {
    expect(toApiRecord(null)).toEqual({});
    expect(getEnvelopeList(null, ['backtests'])).toEqual([]);
  });
});

