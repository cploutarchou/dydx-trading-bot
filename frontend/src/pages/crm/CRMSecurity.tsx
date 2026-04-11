import { useQuery } from '@tanstack/react-query';
import { Loader2, RefreshCw, Shield } from 'lucide-react';
import { useMemo, useState } from 'react';
import api from '../../api';
import { PageContainer } from '../../components/PageContainer';

const outcomeTone: Record<string, string> = {
  success: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200',
  failure: 'border-red-500/30 bg-red-500/10 text-red-200',
  lockout: 'border-amber-500/30 bg-amber-500/10 text-amber-200',
};

const formatDateTime = (value?: string) => {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString();
};

export const CRMSecurity = () => {
  const [outcomeFilter, setOutcomeFilter] = useState<string>('all');
  const [search, setSearch] = useState('');

  const eventsQuery = useQuery({
    queryKey: ['crm', 'security-events', 'full'],
    queryFn: async () => (await api.getCRMSecurityEvents(500, 0)).data,
    staleTime: 10_000,
    refetchInterval: 20_000,
  });

  const allEvents = eventsQuery.data?.events ?? [];

  const filtered = useMemo(() => {
    const term = search.toLowerCase().trim();
    return allEvents.filter((e) => {
      if (outcomeFilter !== 'all' && e.outcome !== outcomeFilter) return false;
      if (
        term &&
        !String(e.username ?? '')
          .toLowerCase()
          .includes(term) &&
        !String(e.ip_address ?? '').includes(term) &&
        !String(e.reason ?? '')
          .toLowerCase()
          .includes(term)
      )
        return false;
      return true;
    });
  }, [allEvents, outcomeFilter, search]);

  const counts = useMemo(() => {
    const r: Record<string, number> = { all: allEvents.length };
    for (const e of allEvents) {
      const o = String(e.outcome);
      r[o] = (r[o] ?? 0) + 1;
    }
    return r;
  }, [allEvents]);

  return (
    <PageContainer size="wide" className="space-y-6">
      {/* Header */}
      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-6">
        <div className="premium-kicker">Security events</div>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-white">Authentication & access log</h1>
            <p className="mt-1 text-sm text-slate-400">
              Recent login outcomes, lockouts, and access anomalies for operational monitoring and
              incident response.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void eventsQuery.refetch()}
            disabled={eventsQuery.isFetching}
            className="flex items-center gap-1.5 rounded-lg border border-slate-700/60 bg-slate-800/60 px-3 py-2 text-xs text-slate-300 transition hover:text-white disabled:opacity-60"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${eventsQuery.isFetching ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Summary stats */}
      <div className="grid gap-4 sm:grid-cols-4">
        {(
          [
            ['all', 'Total events', 'text-slate-300'],
            ['success', 'Successful logins', 'text-emerald-300'],
            ['failure', 'Failed logins', 'text-red-300'],
            ['lockout', 'Lockout events', 'text-amber-300'],
          ] as const
        ).map(([key, label, color]) => (
          <button
            key={key}
            type="button"
            onClick={() => setOutcomeFilter(key)}
            className={`rounded-2xl border p-4 text-left transition ${
              outcomeFilter === key
                ? 'border-cyan-500/40 bg-cyan-500/10'
                : 'border-slate-700/60 bg-slate-900/70 hover:border-slate-600/60'
            }`}
          >
            <p className="text-xs text-slate-500">{label}</p>
            <p className={`mt-1 text-2xl font-semibold ${color}`}>{counts[key] ?? 0}</p>
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="text"
          placeholder="Search username, IP, or reason…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="premium-input min-w-56 flex-1"
        />
        <div className="flex gap-1.5">
          {(['all', 'success', 'failure', 'lockout'] as const).map((o) => (
            <button
              key={o}
              type="button"
              onClick={() => setOutcomeFilter(o)}
              className={`rounded-lg border px-3 py-1.5 text-xs font-medium capitalize transition ${
                outcomeFilter === o
                  ? 'border-cyan-500/40 bg-cyan-500/15 text-cyan-200'
                  : 'border-slate-700/60 bg-slate-900/40 text-slate-400 hover:text-slate-200'
              }`}
            >
              {o}
            </button>
          ))}
        </div>
        <span className="ml-auto text-xs text-slate-500">
          {filtered.length} / {allEvents.length} events
        </span>
      </div>

      {/* Events table */}
      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70">
        {eventsQuery.isLoading ? (
          <div className="flex items-center justify-center gap-2 p-12 text-slate-400">
            <Loader2 className="h-5 w-5 animate-spin" /> Loading events…
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-12 text-center">
            <Shield className="mx-auto h-8 w-8 text-slate-700" />
            <p className="mt-3 text-sm text-slate-400">No events match the current filters</p>
            <button
              type="button"
              onClick={() => {
                setSearch('');
                setOutcomeFilter('all');
              }}
              className="mt-3 text-xs text-cyan-400 hover:text-cyan-200"
            >
              Clear filters
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-xs text-slate-300">
              <thead className="border-b border-slate-800 bg-slate-950/60 text-[10px] uppercase tracking-[0.14em] text-slate-500">
                <tr>
                  <th className="px-4 py-2.5 text-left">When</th>
                  <th className="px-4 py-2.5 text-left">User</th>
                  <th className="px-4 py-2.5 text-left">Outcome</th>
                  <th className="px-4 py-2.5 text-left">Reason</th>
                  <th className="px-4 py-2.5 text-left">IP address</th>
                  <th className="px-4 py-2.5 text-left">Event type</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((event) => (
                  <tr key={event.id} className="border-t border-slate-800/80">
                    <td className="px-4 py-2.5 text-slate-500">
                      {formatDateTime(String(event.created_at ?? ''))}
                    </td>
                    <td className="px-4 py-2.5 font-medium text-slate-100">
                      {String(event.username ?? '—')}
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] ${outcomeTone[String(event.outcome)] ?? 'border-slate-600 bg-slate-700/40 text-slate-300'}`}
                      >
                        {String(event.outcome ?? '—')}
                      </span>
                    </td>
                    <td className="max-w-52 px-4 py-2.5 text-slate-400">
                      {String(event.reason ?? '—')}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-slate-500">
                      {String(event.ip_address ?? '—')}
                    </td>
                    <td className="px-4 py-2.5 text-slate-600">
                      {String(event.event_type ?? '—')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </PageContainer>
  );
};
