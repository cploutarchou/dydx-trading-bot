/// <reference types="node" />

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import {
  CryptoBackground,
  cryptoBackgroundIntensityOrder,
  getCryptoBackgroundPreset,
  getCryptoBackgroundRuntimeMode,
  getCryptoBackgroundStaticReason,
  getCryptoBackgroundVariantForIcoDocument,
  resolveCryptoBackgroundVariant,
} from './CryptoBackground';

describe('CryptoBackground variants', () => {
  it('selects whitepaper and tokenomics document variants from real ICO document slugs', () => {
    expect(getCryptoBackgroundVariantForIcoDocument('whitepaper')).toBe('whitepaper');
    expect(getCryptoBackgroundVariantForIcoDocument('tokenomics')).toBe('tokenomics');
    expect(getCryptoBackgroundVariantForIcoDocument('privacy-notice')).toBe('ico');
    expect(getCryptoBackgroundVariantForIcoDocument(undefined)).toBe('ico');
  });

  it('keeps page-specific intensity presets ordered from quietest to strongest', () => {
    expect(cryptoBackgroundIntensityOrder).toEqual([
      'login',
      'whitepaper',
      'tokenomics',
      'ico',
      'launch',
    ]);
    expect(getCryptoBackgroundPreset('login').intensity).toBe('minimal');
    expect(getCryptoBackgroundPreset('whitepaper').intensity).toBe('low');
    expect(getCryptoBackgroundPreset('tokenomics').intensity).toBe('medium-low');
    expect(getCryptoBackgroundPreset('ico').density).toBeGreaterThan(
      getCryptoBackgroundPreset('whitepaper').density
    );
  });

  it('falls back to launch for invalid variants', () => {
    expect(resolveCryptoBackgroundVariant('unknown')).toBe('launch');
    expect(getCryptoBackgroundPreset('unknown').variant).toBe('launch');
  });

  it('uses static fallback for reduced motion, save data, hidden pages, weak devices, and context failure', () => {
    expect(getCryptoBackgroundRuntimeMode({ reducedMotion: true })).toBe('static');
    expect(getCryptoBackgroundStaticReason({ reducedMotion: true })).toBe('reduced-motion');
    expect(getCryptoBackgroundStaticReason({ saveData: true })).toBe('save-data');
    expect(getCryptoBackgroundStaticReason({ unsuitableDevice: true })).toBe('device');
    expect(getCryptoBackgroundStaticReason({ hidden: true })).toBe('hidden');
    expect(getCryptoBackgroundStaticReason({ contextFailed: true })).toBe('context-failed');
    expect(getCryptoBackgroundRuntimeMode({})).toBe('animated');
  });

  it('renders safely during SSR without touching browser-only APIs', () => {
    const html = renderToString(<CryptoBackground variant="whitepaper" />);

    expect(html).toContain('data-crypto-background="true"');
    expect(html).toContain('data-variant="whitepaper"');
    expect(html).toContain('aria-hidden="true"');
  });

  it('keeps decorative layers out of print output', () => {
    const publicPageCss = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf-8');

    expect(publicPageCss).toContain('@media print');
    expect(publicPageCss).toContain('.crypto-background');
    expect(publicPageCss).toContain('display: none !important');
  });
});
