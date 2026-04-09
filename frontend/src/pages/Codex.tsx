import { useQuery } from '@tanstack/react-query';
import {
  AlertCircle,
  BarChart3,
  DatabaseZap,
  ExternalLink,
  Loader2,
  Search,
  ShieldCheck,
  Sparkles,
  TrendingUp,
} from 'lucide-react';
import React, { useDeferredValue, useMemo, useState } from 'react';
import api, { type CodexTokenSummary } from '../api';
import { PageContainer } from '../components/PageContainer';
import { CODEX_NETWORK_OPTIONS, confidenceTone, formatPct, formatUsd } from '../features/codex/marketIntel';

const TokenCard: React.FC<{
  token: CodexTokenSummary;
  onSelect: (token: CodexTokenSummary) => void;
}> = ({ token, onSelect }) => (
  <button
    type="button"
    onClick={() => onSelect(token)}
    className="rounded-2xl border border-slate-700/60 bg-slate-800/60 p-4 text-left transition hover:border-blue-500/40 hover:bg-slate-800"
  >
    <div className="flex items-start justify-between gap-3">
      <div>
        <p className="text-base font-semibold text-white">{token.symbol}</p>
        <p className="text-sm text-slate-400">{token.name}</p>
      </div>
      <span className={`rounded-full px-2 py-1 text-xs font-medium ${confidenceTone(token.confidence_hint)}`}>
        {token.confidence_hint}
      </span>
    </div>
    <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
      <div>
        <p className="text-slate-500">Price</p>
        <p className="font-semibold text-white">{formatUsd(token.price_usd)}</p>
      </div>
      <div>
        <p className="text-slate-500">24h move</p>
        <p className={`font-semibold ${token.price_change_pct_24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          {formatPct(token.price_change_pct_24h)}
        </p>
      </div>
      <div>
        <p className="text-slate-500">Liquidity</p>
        <p className="font-semibold text-slate-200">{formatUsd(token.liquidity_usd)}</p>
      </div>
      <div>
        <p className="text-slate-500">Volume 24h</p>
        <p className="font-semibold text-slate-200">{formatUsd(token.volume_usd_24h)}</p>
      </div>
    </div>
  </button>
);

const MiniChart: React.FC<{ points: Array<{ close: number }> }> = ({ points }) => {
  const coordinates = useMemo(() => {
    if (points.length < 2) return '';
    const values = points.map((point) => point.close);
    const maxValue = Math.max(...values);
    const minValue = Math.min(...values);
    const spread = Math.max(maxValue - minValue, 1);
    return values
      .map((value, index) => {
        const x = (index / Math.max(values.length - 1, 1)) * 100;
        const y = 100 - ((value - minValue) / spread) * 100;
        return `${x},${y}`;
      })
      .join(' ');
  }, [points]);

  if (!coordinates) {
    return (
      <div className="flex h-40 items-center justify-center rounded-2xl border border-slate-700/60 bg-slate-900/50 text-sm text-slate-500">
        No chart data available yet.
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-slate-700/60 bg-slate-900/50 p-3">
      <svg viewBox="0 0 100 100" className="h-40 w-full">
        <defs>
          <linearGradient id="codex-chart-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="rgba(59,130,246,0.45)" />
            <stop offset="100%" stopColor="rgba(59,130,246,0)" />
          </linearGradient>
        </defs>
        <polyline
          fill="none"
          stroke="#60a5fa"
          strokeWidth="2"
          points={coordinates}
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    </div>
  );
};

export const CodexPage: React.FC = () => {
  const [networkId, setNetworkId] = useState(1);
  const [searchValue, setSearchValue] = useState('');
  const [selectedToken, setSelectedToken] = useState<CodexTokenSummary | null>(null);
  const [interval, setInterval] = useState<'1h' | '4h' | '1d'>('1d');
  const deferredSearchValue = useDeferredValue(searchValue.trim());

  const statusQuery = useQuery({
    queryKey: ['codex', 'status'],
    queryFn: async () => {
      const response = await api.getCodexStatus();
      return response.data;
    },
    staleTime: 30_000,
  });

  const overviewQuery = useQuery({
    queryKey: ['codex', 'overview', networkId],
    queryFn: async () => {
      const response = await api.getCodexMarketOverview(networkId, 6);
      return response.data;
    },
    staleTime: 30_000,
  });

  const searchQuery = useQuery({
    queryKey: ['codex', 'search', deferredSearchValue, networkId],
    queryFn: async () => {
      const response = await api.searchCodexTokens(deferredSearchValue, networkId, 8);
      return response.data;
    },
    staleTime: 30_000,
    enabled: deferredSearchValue.length >= 2,
  });

  const detailQuery = useQuery({
    queryKey: ['codex', 'detail', selectedToken?.network_id, selectedToken?.address],
    queryFn: async () => {
      const response = await api.getCodexTokenDetail(selectedToken!.network_id, selectedToken!.address);
      return response.data;
    },
    enabled: Boolean(selectedToken),
    staleTime: 60_000,
  });

  const chartQuery = useQuery({
    queryKey: ['codex', 'chart', selectedToken?.network_id, selectedToken?.address, interval],
    queryFn: async () => {
      const response = await api.getCodexTokenChart(selectedToken!.network_id, selectedToken!.address, interval, 60);
      return response.data;
    },
    enabled: Boolean(selectedToken),
    staleTime: 5 * 60_000,
  });

  const searchResults = searchQuery.data?.results ?? [];
  const selectedDetail = detailQuery.data;
  const selectedChart = chartQuery.data;
  const keySourceLabel =
    statusQuery.data?.active_key_source === 'user'
      ? 'Using your personal key'
      : statusQuery.data?.active_key_source === 'shared'
        ? 'Using shared backend key'
        : 'No active key';

  return (
    <PageContainer size="wide" className="space-y-6">
      <section
        className="relative overflow-hidden rounded-3xl border border-slate-700/60 px-6 py-6 sm:px-8"
        style={{
          background:
            'linear-gradient(135deg, rgba(15,23,42,.96) 0%, rgba(17,24,39,.94) 46%, rgba(8,145,178,.24) 100%)',
        }}
      >
        <div className="absolute -right-16 top-0 h-56 w-56 rounded-full bg-cyan-500/10 blur-3xl" />
        <div className="absolute -bottom-14 left-0 h-44 w-44 rounded-full bg-emerald-500/10 blur-3xl" />
        <div className="relative flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-cyan-300">
              <Sparkles className="h-3.5 w-3.5" />
              Codex.io Market Intel
            </div>
            <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
              Find trending movers, safer liquid tokens, and sharper market context without leaving the app.
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
              This workspace is tuned for the Codex.io free plan: query-only, backend-proxied, cached, and throttled so you get useful token intelligence without leaking API keys into the browser.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="rounded-2xl border border-slate-700/60 bg-slate-900/45 px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Provider</p>
              <p className="mt-1 text-sm font-semibold text-white">{statusQuery.data?.provider ?? 'codex.io'}</p>
            </div>
            <div className="rounded-2xl border border-slate-700/60 bg-slate-900/45 px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Key source</p>
              <p className="mt-1 text-sm font-semibold text-white">{keySourceLabel}</p>
            </div>
            <div className="rounded-2xl border border-slate-700/60 bg-slate-900/45 px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Plan shape</p>
              <p className="mt-1 text-sm font-semibold text-white">5 req/sec, cached</p>
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-700/60 bg-slate-800/60 p-5 backdrop-blur-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex items-start gap-3">
            <div className="rounded-xl bg-blue-500/10 p-2 text-blue-300">
              <DatabaseZap className="h-5 w-5" />
            </div>
            <div>
              <p className="text-lg font-semibold text-white">Connection and plan status</p>
              <p className="mt-1 text-sm text-slate-400">
                {statusQuery.data?.message ?? 'Checking Codex.io availability...'}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <select
              value={networkId}
              onChange={(event) => {
                setNetworkId(Number(event.target.value));
                setSelectedToken(null);
              }}
              className="rounded-xl border border-slate-700 bg-slate-900/60 px-4 py-3 text-sm text-white outline-none transition focus:border-blue-500/60"
            >
              {CODEX_NETWORK_OPTIONS.map((network) => (
                <option key={network.id} value={network.id}>
                  {network.label}
                </option>
              ))}
            </select>

            <div className="relative min-w-[260px]">
              <Search className="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-slate-500" />
              <input
                value={searchValue}
                onChange={(event) => setSearchValue(event.target.value)}
                placeholder="Search token symbol, name, or address"
                className="w-full rounded-xl border border-slate-700 bg-slate-900/60 py-3 pl-10 pr-4 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-blue-500/60"
              />
            </div>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-3 text-xs text-slate-400">
          <span className="rounded-full border border-slate-700 px-3 py-1">No websockets</span>
          <span className="rounded-full border border-slate-700 px-3 py-1">No webhooks</span>
          <span className="rounded-full border border-slate-700 px-3 py-1">No wallet P&amp;L assumptions</span>
          <span className="rounded-full border border-slate-700 px-3 py-1">
            {statusQuery.data?.capabilities?.monthly_requests ?? 10000} monthly requests
          </span>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-[1.05fr,1.05fr,1.1fr]">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-800/60 p-5 backdrop-blur-sm">
          <div className="mb-4 flex items-center gap-3">
            <div className="rounded-xl bg-emerald-500/10 p-2 text-emerald-300">
              <TrendingUp className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Trending Movers</h2>
              <p className="text-sm text-slate-400">High momentum, still filtered for baseline liquidity.</p>
            </div>
          </div>

          <div className="space-y-3">
            {overviewQuery.isLoading ? (
              <div className="flex items-center gap-2 text-sm text-slate-300">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading movers...
              </div>
            ) : overviewQuery.isError ? (
              <div className="rounded-xl border border-red-700/60 bg-red-950/30 p-4 text-sm text-red-200">
                Unable to load movers right now.
              </div>
            ) : (
              (overviewQuery.data?.movers ?? []).map((token) => (
                <TokenCard key={token.id} token={token} onSelect={setSelectedToken} />
              ))
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-700/60 bg-slate-800/60 p-5 backdrop-blur-sm">
          <div className="mb-4 flex items-center gap-3">
            <div className="rounded-xl bg-cyan-500/10 p-2 text-cyan-300">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Safe Movers</h2>
              <p className="text-sm text-slate-400">Biased toward liquidity and volume instead of pure volatility.</p>
            </div>
          </div>

          <div className="space-y-3">
            {overviewQuery.isLoading ? (
              <div className="flex items-center gap-2 text-sm text-slate-300">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading safer movers...
              </div>
            ) : overviewQuery.isError ? (
              <div className="rounded-xl border border-red-700/60 bg-red-950/30 p-4 text-sm text-red-200">
                Unable to load safer movers right now.
              </div>
            ) : (
              (overviewQuery.data?.safe_movers ?? []).map((token) => (
                <TokenCard key={token.id} token={token} onSelect={setSelectedToken} />
              ))
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-700/60 bg-slate-800/60 p-5 backdrop-blur-sm">
          <div className="mb-4 flex items-center gap-3">
            <div className="rounded-xl bg-amber-500/10 p-2 text-amber-300">
              <Search className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Token Search</h2>
              <p className="text-sm text-slate-400">Search is debounced and filtered by the selected network.</p>
            </div>
          </div>

          {deferredSearchValue.length < 2 ? (
            <div className="rounded-xl border border-slate-700/60 bg-slate-900/45 p-4 text-sm text-slate-400">
              Start typing at least two characters to search by symbol, token name, or address.
            </div>
          ) : searchQuery.isLoading ? (
            <div className="flex items-center gap-2 text-sm text-slate-300">
              <Loader2 className="h-4 w-4 animate-spin" />
              Searching Codex.io...
            </div>
          ) : searchResults.length === 0 ? (
            <div className="rounded-xl border border-slate-700/60 bg-slate-900/45 p-4 text-sm text-slate-400">
              No tokens matched that query on the selected network.
            </div>
          ) : (
            <div className="space-y-3">
              {searchResults.map((token) => (
                <TokenCard key={token.id} token={token} onSelect={setSelectedToken} />
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="rounded-2xl border border-slate-700/60 bg-slate-800/60 p-5 backdrop-blur-sm">
        <div className="mb-4 flex items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-white">Token Detail</h2>
            <p className="mt-1 text-sm text-slate-400">
              Select a mover or search result to inspect liquidity, volume, and recent price structure.
            </p>
          </div>
          {selectedToken && (
            <div className="flex gap-2">
              {(['1h', '4h', '1d'] as const).map((nextInterval) => (
                <button
                  key={nextInterval}
                  type="button"
                  onClick={() => setInterval(nextInterval)}
                  className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                    interval === nextInterval
                      ? 'bg-blue-600 text-white'
                      : 'border border-slate-700 bg-slate-900/60 text-slate-300 hover:border-blue-500/40'
                  }`}
                >
                  {nextInterval}
                </button>
              ))}
            </div>
          )}
        </div>

        {!selectedToken ? (
          <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-900/35 p-8 text-center text-slate-400">
            Select a token from the lists above to open its detail workspace.
          </div>
        ) : detailQuery.isLoading ? (
          <div className="flex items-center gap-2 text-sm text-slate-300">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading token detail...
          </div>
        ) : detailQuery.isError || !selectedDetail ? (
          <div className="rounded-xl border border-red-700/60 bg-red-950/30 p-4 text-sm text-red-200">
            Unable to load token detail right now.
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.1fr,0.9fr]">
            <div className="space-y-4">
              <div className="rounded-2xl border border-slate-700/60 bg-slate-900/45 p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-2xl font-bold text-white">
                      {selectedDetail.token.symbol}{' '}
                      <span className="text-base font-medium text-slate-500">{selectedDetail.token.name}</span>
                    </p>
                    <p className="mt-2 text-sm text-slate-400">
                      {selectedDetail.description || 'No description available for this token yet.'}
                    </p>
                  </div>
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold ${confidenceTone(selectedDetail.token.confidence_hint)}`}>
                    {selectedDetail.token.confidence_hint}
                  </span>
                </div>

                <div className="mt-5 grid grid-cols-2 gap-4 md:grid-cols-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Price</p>
                    <p className="mt-1 text-lg font-semibold text-white">{formatUsd(selectedDetail.token.price_usd)}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.16em] text-slate-500">24h</p>
                    <p className={`mt-1 text-lg font-semibold ${selectedDetail.token.price_change_pct_24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {formatPct(selectedDetail.token.price_change_pct_24h)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Liquidity</p>
                    <p className="mt-1 text-lg font-semibold text-white">{formatUsd(selectedDetail.token.liquidity_usd)}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Volume 24h</p>
                    <p className="mt-1 text-lg font-semibold text-white">{formatUsd(selectedDetail.token.volume_usd_24h)}</p>
                  </div>
                </div>
              </div>

              {chartQuery.isLoading ? (
                <div className="flex items-center gap-2 text-sm text-slate-300">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading chart data...
                </div>
              ) : selectedChart ? (
                <MiniChart points={selectedChart.points} />
              ) : (
                <div className="rounded-xl border border-slate-700/60 bg-slate-900/45 p-4 text-sm text-slate-400">
                  Chart data is unavailable for this token right now.
                </div>
              )}
            </div>

            <div className="space-y-4">
              <div className="rounded-2xl border border-slate-700/60 bg-slate-900/45 p-5">
                <div className="mb-4 flex items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-blue-300" />
                  <p className="font-semibold text-white">Market structure</p>
                </div>
                <div className="space-y-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">Market cap</span>
                    <span className="font-semibold text-slate-200">{formatUsd(selectedDetail.token.market_cap_usd)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">Supply tracked</span>
                    <span className="font-semibold text-slate-200">
                      {selectedDetail.circulating_supply > 0 ? selectedDetail.circulating_supply.toLocaleString() : 'N/A'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">Transactions 24h</span>
                    <span className="font-semibold text-slate-200">{selectedDetail.token.transactions_24h.toLocaleString()}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">Exchanges</span>
                    <span className="font-semibold text-slate-200">
                      {selectedDetail.token.exchanges.length > 0 ? selectedDetail.token.exchanges.join(', ') : 'N/A'}
                    </span>
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-slate-700/60 bg-slate-900/45 p-5">
                <div className="mb-4 flex items-center gap-2">
                  <ExternalLink className="h-4 w-4 text-cyan-300" />
                  <p className="font-semibold text-white">Relevant pairs</p>
                </div>
                {selectedDetail.top_pairs.length === 0 ? (
                  <p className="text-sm text-slate-400">No pair metadata available for this token right now.</p>
                ) : (
                  <div className="space-y-3">
                    {selectedDetail.top_pairs.map((pair) => (
                      <div key={pair.pair_id} className="rounded-xl border border-slate-700/60 bg-slate-950/60 p-3">
                        <div className="flex items-center justify-between gap-3">
                          <p className="font-semibold text-white">{pair.exchange_name || pair.protocol || 'Pair'}</p>
                          <span className="text-xs text-slate-500">{pair.backing_token}</span>
                        </div>
                        <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
                          <div>
                            <p className="text-slate-500">Liquidity</p>
                            <p className="font-semibold text-slate-200">{formatUsd(pair.liquidity_usd)}</p>
                          </div>
                          <div>
                            <p className="text-slate-500">Volume 24h</p>
                            <p className="font-semibold text-slate-200">{formatUsd(pair.volume_usd_24h)}</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </section>

      {(statusQuery.isError || overviewQuery.isError) && (
        <div className="rounded-2xl border border-red-700/60 bg-red-950/30 p-4 text-sm text-red-200">
          <div className="flex items-start gap-3">
            <AlertCircle className="mt-0.5 h-4 w-4" />
            <div>
              Codex.io is temporarily degraded. The rest of the app still works, and you can retry this page once the backend key or upstream service is healthy again.
            </div>
          </div>
        </div>
      )}
    </PageContainer>
  );
};
