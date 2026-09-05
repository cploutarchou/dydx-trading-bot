import { useQuery } from '@tanstack/react-query';
import { ArrowUpRight, Newspaper, RefreshCw } from 'lucide-react';
import api from '../api';
import { httpsUrl } from '../utils/urlSafety';

const formatPublishedAt = (value?: string): string => {
  if (!value) return 'Unknown time';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
};

interface CoinDeskNewsPanelProps {
  compact?: boolean;
}

export function CoinDeskNewsPanel({ compact = false }: CoinDeskNewsPanelProps) {
  const newsQuery = useQuery({
    queryKey: ['news', 'coindesk', compact ? 'compact' : 'full'],
    queryFn: async () => {
      const response = await api.getCoinDeskNews(compact ? 4 : 6);
      return response.data;
    },
    staleTime: 2 * 60_000,
    refetchInterval: 5 * 60_000,
  });

  const articles = newsQuery.data?.articles ?? [];
  const featuredArticle = !compact ? articles[0] : null;
  const remainingArticles = featuredArticle ? articles.slice(1) : articles;

  return (
    <section className="premium-panel overflow-hidden">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="premium-icon-wrap text-cyan-300">
            <Newspaper className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white">CoinDesk News Pulse</h2>
            <p className="mt-1 text-sm text-slate-400">
              Live crypto headlines from the official CoinDesk feed, refreshed through the backend.
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => void newsQuery.refetch()}
          className="inline-flex items-center gap-2 rounded-full border border-slate-700/70 bg-slate-900/60 px-3 py-1.5 text-xs font-medium text-slate-300 transition hover:border-cyan-500/40 hover:text-white"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${newsQuery.isFetching ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      <div className="mt-5 space-y-3">
        {newsQuery.isLoading ? (
          <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-5 text-sm text-slate-400">
            Loading the latest CoinDesk coverage...
          </div>
        ) : newsQuery.isError ? (
          <div className="rounded-2xl border border-red-700/60 bg-red-950/30 p-5 text-sm text-red-200">
            CoinDesk news is temporarily unavailable. The rest of the platform is still fully usable.
          </div>
        ) : articles.length === 0 ? (
          <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-5 text-sm text-slate-400">
            No CoinDesk stories are available right now. Try again in a moment.
          </div>
        ) : (
          <>
            {featuredArticle && (
              <a
                href={httpsUrl(featuredArticle.url) ?? '#'}
                target="_blank"
                rel="noreferrer"
                className="group block overflow-hidden rounded-[1.75rem] border border-slate-700/60 bg-slate-950/50 transition hover:border-cyan-500/35 hover:bg-slate-950/70"
              >
                <div className="grid gap-0 xl:grid-cols-[1.1fr,0.9fr]">
                  <div className="p-6">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-300">
                        Lead Story
                      </span>
                      <span className="rounded-full border border-slate-700/70 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                        {featuredArticle.category || 'News'}
                      </span>
                      <span className="text-xs text-slate-500">
                        {formatPublishedAt(featuredArticle.published_at)}
                      </span>
                    </div>
                    <h3 className="mt-4 text-2xl font-semibold leading-tight text-white transition group-hover:text-cyan-100">
                      {featuredArticle.title}
                    </h3>
                    <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-400">
                      {featuredArticle.summary}
                    </p>
                    <div className="mt-5 flex items-center gap-2 text-sm text-slate-400">
                      <span>{featuredArticle.author || 'CoinDesk'}</span>
                      <ArrowUpRight className="h-4 w-4 transition group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                    </div>
                  </div>
                  {featuredArticle.image_url && (
                    <div className="min-h-[260px] overflow-hidden border-l border-slate-800/80 bg-slate-900/60">
                      <img
                        src={featuredArticle.image_url}
                        alt={featuredArticle.title}
                        className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.03]"
                        loading="lazy"
                      />
                    </div>
                  )}
                </div>
              </a>
            )}

            {remainingArticles.map((article) => (
            <a
              key={article.id}
              href={httpsUrl(article.url) ?? '#'}
              target="_blank"
              rel="noreferrer"
              className="group block rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4 transition hover:border-cyan-500/35 hover:bg-slate-950/70"
            >
              <div className={`grid gap-4 ${compact ? 'grid-cols-1' : 'grid-cols-1 lg:grid-cols-[1fr,220px]'}`}>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-300">
                      {article.category || 'News'}
                    </span>
                    <span className="text-xs text-slate-500">{formatPublishedAt(article.published_at)}</span>
                  </div>
                  <h3 className="mt-3 text-base font-semibold leading-6 text-white transition group-hover:text-cyan-100">
                    {article.title}
                  </h3>
                  <p className="mt-2 text-sm leading-6 text-slate-400">{article.summary}</p>
                  <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
                    <span>{article.author || 'CoinDesk'}</span>
                    <ArrowUpRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                  </div>
                </div>
                {!compact && article.image_url && (
                  <div className="overflow-hidden rounded-2xl border border-slate-700/60 bg-slate-900/50">
                    <img
                      src={article.image_url}
                      alt={article.title}
                      className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.03]"
                      loading="lazy"
                    />
                  </div>
                )}
              </div>
            </a>
            ))}
          </>
        )}
      </div>
    </section>
  );
}
