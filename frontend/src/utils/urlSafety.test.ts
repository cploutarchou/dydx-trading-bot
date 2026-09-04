import { describe, expect, it } from 'vitest';
import { httpsUrl, platformHost } from './urlSafety';

describe('url safety helpers', () => {
  it('httpsUrl accepts only well-formed https URLs', () => {
    expect(httpsUrl('https://www.coindesk.com/article')).toBe('https://www.coindesk.com/article');
    expect(httpsUrl('javascript:alert(1)')).toBeUndefined();
    expect(httpsUrl('http://insecure.example.com')).toBeUndefined();
    expect(httpsUrl('data:text/html,evil')).toBeUndefined();
    expect(httpsUrl(undefined)).toBeUndefined();
    expect(httpsUrl('')).toBeUndefined();
  });

  it('platformHost keeps platform-owned hosts and rejects others', () => {
    expect(platformHost('crm.executionlab.io', 'app.executionlab.io')).toBe('crm.executionlab.io');
    expect(platformHost('https://ib.executionlab.io/', 'app.executionlab.io')).toBe(
      'ib.executionlab.io'
    );
    expect(platformHost('evil.example.net', 'app.executionlab.io')).toBe('app.executionlab.io');
    // look-alike suffixes must not pass
    expect(platformHost('executionlab.io.evil.net', 'app.executionlab.io')).toBe(
      'app.executionlab.io'
    );
    expect(platformHost('', 'app.executionlab.io')).toBe('app.executionlab.io');
  });
});
