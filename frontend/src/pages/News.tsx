import { useQuery } from '@tanstack/react-query';
import { ArrowRight, Clock3, Newspaper, ShieldCheck, Sparkles } from 'lucide-react';
import React, { useMemo } from 'react';
import { Link } from 'react-router-dom';
import api from '../api';
import { CoinDeskNewsPanel } from '../components/CoinDeskNewsPanel';
import { PageContainer } from '../components/PageContainer';
import { PortalSubnav } from '../components/ui/PlatformUI';
import { useAuthStore } from '../store/auth';

const MARKET_INTEL_TABS = [
  { path: '/market-intel', label: 'Token Intel', icon: Sparkles },
  { path: '/market-intel/news', label: 'Market News', icon: Newspaper },
] as const;

const formatPublishedAt = (value?: string): string => {
  if (!value) return 'Awaiting latest feed pull';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
};

export const NewsPage: React.FC = () => {
  const user = useAuthStore((state) => state.user);
  const newsQuery = useQuery({
    queryKey: ['news', 'coindesk', 'page'],
    queryFn: async () => {
      const response = await api.getCoinDeskNews(12);
      return response.data;
    },
    staleTime: 2 * 60_000,
    refetchInterval: 5 * 60_000,
  });

  const latestArticle = useMemo(() => newsQuery.data?.articles?.[0], [newsQuery.data?.articles]);

  return (
    <PageContainer size="wide" className="space-y-6">
      <PortalSubnav tabs={MARKET_INTEL_TABS} label="Market Intel" />
      <section className="premium-hero px-6 py-7 sm:px-8">
        <div className="premium-orb -right-10 top-0 h-44 w-44 bg-cyan-500/10" />
        <div className="premium-orb -left-8 bottom-0 h-36 w-36 bg-emerald-500/10" />

        <div className="relative flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <div className="premium-kicker">
              <Newspaper className="h-3.5 w-3.5" />
              Market Intel / Newsroom
            </div>
            <h1 className="mt-4 text-3xl font-bold tracking-tight text-white sm:text-4xl">
              Daily crypto coverage curated beside token intelligence and strategy research.
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
              The backend fetches and caches CoinDesk updates so every user sees the latest market context
              without exposing provider credentials in the browser.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Coverage</p>
              <p className="mt-1 text-xl font-semibold text-white">
                {newsQuery.data?.articles?.length ?? 0} stories
              </p>
            </div>
            <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Latest headline</p>
              <p className="mt-1 line-clamp-2 text-sm font-semibold text-white">
                {latestArticle?.title ?? 'Refreshing market pulse'}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Last published</p>
              <p className="mt-1 text-sm font-semibold text-white">
                {formatPublishedAt(latestArticle?.published_at)}
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-[1.45fr,0.95fr]">
        <div className="premium-panel">
          <div className="flex items-start gap-3">
            <div className="premium-icon-wrap text-cyan-300">
              <Clock3 className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Why this matters</h2>
              <p className="mt-1 text-sm leading-6 text-slate-400">
                News belongs inside the trading workflow. This page helps clients move from macro context
                to strategy analysis without hopping between tools.
              </p>
            </div>
          </div>
        </div>

        <div className="premium-panel">
          <div className="flex items-start gap-3">
            <div className="premium-icon-wrap text-emerald-300">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Backend-served and safe</h2>
              <p className="mt-1 text-sm leading-6 text-slate-400">
                The feed is proxied, cached, and controlled centrally. Users only consume normalized news
                data, while admins can manage provider access inside Settings.
              </p>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-400">
            <span className="rounded-full border border-slate-700/70 px-3 py-1">Shared access</span>
            <span className="rounded-full border border-slate-700/70 px-3 py-1">Cached backend feed</span>
            <span className="rounded-full border border-slate-700/70 px-3 py-1">No browser key exposure</span>
          </div>

          {user?.is_admin && (
            <Link
              to="/settings"
              className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-cyan-300 transition hover:text-cyan-200"
            >
              Manage newsroom key in Settings
              <ArrowRight className="h-4 w-4" />
            </Link>
          )}
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="premium-panel">
          <div className="flex items-center gap-3">
            <div className="premium-icon-wrap text-amber-300">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">Operator signal</p>
              <p className="text-xs text-slate-400">
                Use coverage here to validate whether market regime shifts line up with your latest backtests.
              </p>
            </div>
          </div>
        </div>
        <div className="premium-panel">
          <div className="flex items-center gap-3">
            <div className="premium-icon-wrap text-cyan-300">
              <Newspaper className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">Shared visibility</p>
              <p className="text-xs text-slate-400">
                Every authenticated user sees the same live market pulse, keeping decision context aligned.
              </p>
            </div>
          </div>
        </div>
        <div className="premium-panel">
          <div className="flex items-center gap-3">
            <div className="premium-icon-wrap text-emerald-300">
              <Clock3 className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">Fast and stable</p>
              <p className="text-xs text-slate-400">
                Feed pulls are cached server-side so the UI feels immediate even during heavier usage.
              </p>
            </div>
          </div>
        </div>
      </section>

      <CoinDeskNewsPanel />
    </PageContainer>
  );
};
