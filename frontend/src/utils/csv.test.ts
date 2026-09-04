import { describe, expect, it } from 'vitest';
import { sanitizeCsvCell, toCsvCell } from './csv';

describe('csv export safety', () => {
  it('neutralizes classic formula payloads', () => {
    expect(sanitizeCsvCell('=1+1')).toBe("'=1+1");
    expect(sanitizeCsvCell('+cmd|/C calc')).toBe("'+cmd|/C calc");
    expect(sanitizeCsvCell('@SUM(A1:A2)')).toBe("'@SUM(A1:A2)");
    expect(sanitizeCsvCell('-2+3+cmd|\' /C calc\'!A0')).toBe("'-2+3+cmd|' /C calc'!A0");
  });

  it('keeps genuine numbers untouched (financial exports stay numeric)', () => {
    expect(sanitizeCsvCell('-4.50')).toBe('-4.50');
    expect(sanitizeCsvCell('+1200')).toBe('+1200');
    expect(sanitizeCsvCell('2024-01-01')).toBe('2024-01-01');
  });

  it('leaves ordinary text alone', () => {
    expect(sanitizeCsvCell('BTC-USD')).toBe('BTC-USD');
    expect(sanitizeCsvCell('run-aabb1122')).toBe('run-aabb1122');
  });

  it('toCsvCell quotes commas, escapes quotes, preserves sanitization', () => {
    expect(toCsvCell('a,b')).toBe('"a,b"');
    expect(toCsvCell('say "hi"')).toBe('"say ""hi"""');
    expect(toCsvCell('=HYPERLINK("x")')).toBe('"\'=HYPERLINK(""x"")"');
  });
});
