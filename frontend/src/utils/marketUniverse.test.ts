import { describe, expect, it } from 'vitest';
import type { PerpetualMarketDetail } from '../api';
import { formatMarketVolume, pairCount, volumeByTicker } from './marketUniverse';

const detail = (ticker: string, volume: number | null): PerpetualMarketDetail => ({
  ticker,
  status: 'ACTIVE',
  volume_24h: volume,
  open_interest: null,
  open_interest_usd: null,
  next_funding_rate: null,
  oracle_price: null,
  trades_24h: null,
});

describe('pairCount', () => {
  it('counts every unordered pair of the selection', () => {
    expect(pairCount(0)).toBe(0);
    expect(pairCount(1)).toBe(0);
    expect(pairCount(2)).toBe(1);
    expect(pairCount(3)).toBe(3);
    expect(pairCount(5)).toBe(10);
  });
});

describe('formatMarketVolume', () => {
  it('formats volumes compactly and hides unknown ones', () => {
    expect(formatMarketVolume(2377823.0794)).toBe('$2.4M');
    expect(formatMarketVolume(1_500_000_000)).toBe('$1.5B');
    expect(formatMarketVolume(84_400)).toBe('$84K');
    expect(formatMarketVolume(12.4)).toBe('$12');
    expect(formatMarketVolume(0)).toBe('$0');
    expect(formatMarketVolume(null)).toBeNull();
    expect(formatMarketVolume(undefined)).toBeNull();
    expect(formatMarketVolume(Number.NaN)).toBeNull();
    expect(formatMarketVolume(-1)).toBeNull();
  });
});

describe('volumeByTicker', () => {
  it('maps tickers to their volume and tolerates a missing details list', () => {
    const volumes = volumeByTicker([detail('BTC-USD', 2_000_000), detail('NEW-USD', null)]);
    expect(volumes.get('BTC-USD')).toBe(2_000_000);
    expect(volumes.get('NEW-USD')).toBeNull();
    expect(volumes.has('ETH-USD')).toBe(false);
    expect(volumeByTicker(undefined).size).toBe(0);
  });
});
