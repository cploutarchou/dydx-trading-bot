import type {
  CodexAssetContextRequest,
  CodexAssetIntel,
  CodexTokenSummary,
} from '../../api';
import type { BacktestRun } from '../backtests/intelligence';

export interface CodexNetworkOption {
  id: number;
  label: string;
  shortLabel: string;
}

export const CODEX_NETWORK_OPTIONS: CodexNetworkOption[] = [
  { id: 1, label: 'Ethereum', shortLabel: 'ETH' },
  { id: 42161, label: 'Arbitrum', shortLabel: 'ARB' },
  { id: 8453, label: 'Base', shortLabel: 'BASE' },
  { id: 10, label: 'Optimism', shortLabel: 'OP' },
  { id: 137, label: 'Polygon', shortLabel: 'POLY' },
];

export const formatUsd = (value: number): string =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    notation: Math.abs(value) >= 1_000_000 ? 'compact' : 'standard',
    maximumFractionDigits: Math.abs(value) >= 100 ? 0 : 2,
  }).format(value || 0);

export const formatPct = (value: number): string =>
  `${value >= 0 ? '+' : ''}${(value || 0).toFixed(1)}%`;

export const confidenceTone = (confidenceHint?: string): string => {
  switch (confidenceHint) {
    case 'high':
      return 'text-emerald-300';
    case 'medium':
      return 'text-cyan-300';
    case 'flagged':
      return 'text-red-300';
    default:
      return 'text-amber-300';
  }
};

export const normalizeAssetSymbol = (rawValue?: string | null): string | null => {
  if (!rawValue) return null;
  const trimmed = rawValue.trim().toUpperCase();
  if (!trimmed) return null;

  const firstSegment = trimmed.split(/[/-]/)[0]?.trim();
  if (!firstSegment) return null;
  return firstSegment || null;
};

export const buildCodexAssetContextRequest = (
  inputs: Array<{ label?: string; symbol?: string | null; address?: string; network_id?: number }>,
  defaultNetworkId?: number
): CodexAssetContextRequest => ({
  network_id: defaultNetworkId,
  assets: inputs
    .map((input) => ({
      label: input.label,
      symbol: normalizeAssetSymbol(input.symbol ?? undefined) ?? undefined,
      address: input.address,
      network_id: input.network_id,
    }))
    .filter((input) => input.symbol || input.address),
});

export const pickResolvedIntel = (items: CodexAssetIntel[] | undefined): CodexTokenSummary[] =>
  (items ?? [])
    .map((item) => item.token)
    .filter((token): token is CodexTokenSummary => Boolean(token));

export const buildStrategyIntelRequest = (
  strategies: Array<{ name?: string; benchmark_symbol?: string | null }>,
  defaultNetworkId = 1
): CodexAssetContextRequest =>
  buildCodexAssetContextRequest(
    strategies.map((strategy) => ({
      label: strategy.name ?? 'Strategy',
      symbol: strategy.benchmark_symbol ?? undefined,
    })),
    defaultNetworkId
  );

export const buildBacktestIntelRequest = (
  runs: BacktestRun[],
  defaultNetworkId = 1
): CodexAssetContextRequest =>
  buildCodexAssetContextRequest(
    runs.map((run) => ({
      label: run.strategy_name ?? run.name ?? run.run_id,
      symbol:
        typeof run.request?.benchmark_symbol === 'string'
          ? run.request.benchmark_symbol
          : undefined,
    })),
    defaultNetworkId
  );
