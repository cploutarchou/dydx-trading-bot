import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  buildWhitelistMailto,
  formatConfiguredDate,
  getCountdownState,
  isValidContactEmail,
} from './publicPages';

describe('public page utilities', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('builds countdown parts from a configured UTC date', () => {
    const now = Date.parse('2026-09-14T12:00:00Z');
    const countdown = getCountdownState('2026-09-15T14:30:05Z', now);

    expect(countdown.status).toBe('active');
    expect(countdown.parts).toEqual([
      { label: 'Days', value: '01' },
      { label: 'Hours', value: '02' },
      { label: 'Minutes', value: '30' },
      { label: 'Seconds', value: '05' },
    ]);
  });

  it('handles expired and missing ICO countdown dates', () => {
    const now = Date.parse('2026-09-15T12:00:01Z');

    expect(getCountdownState('2026-09-15T12:00:00Z', now).status).toBe('expired');
    expect(getCountdownState('', now).status).toBe('missing');
    expect(getCountdownState('not-a-date', now).parts[0]!.value).toBe('--');
  });

  it('formats the configured date in the configured timezone', () => {
    expect(formatConfiguredDate('2026-09-15T12:00:00Z', 'Asia/Dubai', 'en-US')).toContain(
      'Sep 15, 2026'
    );
  });

  it('validates whitelist email input', () => {
    expect(isValidContactEmail('investor@example.com')).toBe(true);
    expect(isValidContactEmail(' investor@example.com ')).toBe(true);
    expect(isValidContactEmail('missing-domain@')).toBe(false);
    expect(isValidContactEmail('not-an-email')).toBe(false);
  });

  it('builds a whitelist mailto request without approval claims', () => {
    const mailto = buildWhitelistMailto({
      contactEmail: 'launchpad@executionlab.io',
      requesterEmail: 'investor@example.com',
      tokenSymbol: 'EXL',
    });

    expect(mailto).toContain('mailto:launchpad@executionlab.io');
    expect(decodeURIComponent(mailto)).toContain('investor@example.com');
    expect(decodeURIComponent(mailto)).toContain('does not guarantee');
  });

  it('uses a stable current-time default for countdown callers', () => {
    vi.spyOn(Date, 'now').mockReturnValue(Date.parse('2026-09-15T11:59:50Z'));
    const parts = getCountdownState('2026-09-15T12:00:00Z').parts;
    expect(parts[parts.length - 1]?.value).toBe('10');
  });
});
