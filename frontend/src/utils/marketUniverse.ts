/**
 * Helpers for the market pickers.
 *
 * The perpetual markets route returns the tradable universe sorted by 24 h
 * volume with a `market_details` record per ticker. The pickers show the
 * volume beside each market and tell the operator how many pairs a selection
 * really produces: every pair from the selected markets runs, not only the
 * first five shown in the preview.
 */

import type { PerpetualMarketDetail } from '../api';

/** Number of unordered pairs a selection of `marketCount` markets produces. */
export const pairCount = (marketCount: number): number =>
  marketCount < 2 ? 0 : (marketCount * (marketCount - 1)) / 2;

/** Compact USD volume label, or null when the volume is unknown. */
export const formatMarketVolume = (volume: number | null | undefined): string | null => {
  if (volume === null || volume === undefined || !Number.isFinite(volume) || volume < 0) {
    return null;
  }
  if (volume >= 1e9) {
    return `$${(volume / 1e9).toFixed(1)}B`;
  }
  if (volume >= 1e6) {
    return `$${(volume / 1e6).toFixed(1)}M`;
  }
  if (volume >= 1e3) {
    return `$${Math.round(volume / 1e3)}K`;
  }
  return `$${Math.round(volume)}`;
};

/** Ticker to 24 h volume, from the route's `market_details` when present. */
export const volumeByTicker = (
  details: readonly PerpetualMarketDetail[] | undefined
): Map<string, number | null> => {
  const volumes = new Map<string, number | null>();
  for (const detail of details ?? []) {
    if (typeof detail?.ticker === 'string' && detail.ticker.length > 0) {
      volumes.set(detail.ticker, typeof detail.volume_24h === 'number' ? detail.volume_24h : null);
    }
  }
  return volumes;
};
