import { useQuery } from '@tanstack/react-query';
import { Activity, Loader2 } from 'lucide-react';
import api, { type CodexAssetContextRequest } from '../api';
import { confidenceTone, formatPct, formatUsd } from '../features/codex/marketIntel';

interface CodexAssetIntelStripProps {
  title?: string;
  request: CodexAssetContextRequest;
  compact?: boolean;
}

export function CodexAssetIntelStrip({
  title = 'Market Intel',
  request,
  compact = false,
}: CodexAssetIntelStripProps) {
  const hasAssets = request.assets.length > 0;

  const intelQuery = useQuery({
    queryKey: ['codex', 'assets', request],
    queryFn: async () => {
      const response = await api.resolveCodexAssetContext(request);
      return response.data;
    },
    staleTime: 60_000,
    enabled: hasAssets,
  });

  const items = (intelQuery.data?.items ?? []).filter((item) => item.token);

  if (!hasAssets || items.length === 0) {
    if (intelQuery.isLoading) {
      return (
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Loading market intel...
        </div>
      );
    }
    return null;
  }

  return (
    <div className={`rounded-xl border border-slate-700/60 bg-slate-900/45 ${compact ? 'p-3' : 'p-4'}`}>
      <div className="mb-3 flex items-center gap-2">
        <Activity className="h-4 w-4 text-cyan-300" />
        <p className="text-sm font-semibold text-white">{title}</p>
      </div>
      <div className={`grid gap-3 ${compact ? 'grid-cols-1' : 'grid-cols-1 md:grid-cols-2'}`}>
        {items.map((item) => (
          <div key={`${item.label}-${item.token?.id}`} className="rounded-lg border border-slate-700/60 bg-slate-950/60 px-3 py-2.5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-white">{item.label}</p>
                <p className="text-xs text-slate-400">
                  {item.token?.symbol} · {formatUsd(item.token?.price_usd ?? 0)}
                </p>
              </div>
              <span className={`text-xs font-medium ${confidenceTone(item.token?.confidence_hint)}`}>
                {item.token?.confidence_hint}
              </span>
            </div>
            <div className="mt-3 grid grid-cols-3 gap-3 text-xs">
              <div>
                <p className="text-slate-500">24h</p>
                <p className={`${(item.token?.price_change_pct_24h ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {formatPct(item.token?.price_change_pct_24h ?? 0)}
                </p>
              </div>
              <div>
                <p className="text-slate-500">Liquidity</p>
                <p className="text-slate-200">{formatUsd(item.token?.liquidity_usd ?? 0)}</p>
              </div>
              <div>
                <p className="text-slate-500">Volume</p>
                <p className="text-slate-200">{formatUsd(item.token?.volume_usd_24h ?? 0)}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
