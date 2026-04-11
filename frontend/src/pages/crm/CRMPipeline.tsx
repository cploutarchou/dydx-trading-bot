import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import api, { type PartnerApplication } from '../../api';
import { useToastStore } from '../../components/ErrorBoundary';
import { PageContainer } from '../../components/PageContainer';

const statusTone: Record<string, string> = {
  pending: 'border-amber-500/30 bg-amber-500/10 text-amber-200',
  reviewing: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-200',
  approved: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200',
  rejected: 'border-red-500/30 bg-red-500/10 text-red-200',
};

const formatDateTime = (value?: string) => {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString();
};

const buildNextStatus = (app: PartnerApplication): 'reviewing' | 'approved' | 'rejected' =>
  app.status === 'pending' ? 'reviewing' : 'approved';

export const CRMPipeline = () => {
  const queryClient = useQueryClient();
  const successToast = useToastStore((s) => s.success);
  const errorToast = useToastStore((s) => s.error);
  const [reviewNotes, setReviewNotes] = useState<Record<number, string>>({});
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const applicationsQuery = useQuery({
    queryKey: ['portal', 'applications', 'crm'],
    queryFn: async () => (await api.listPartnerApplications(500, 0)).data,
    staleTime: 10_000,
    refetchInterval: 20_000,
  });

  const reviewMutation = useMutation({
    mutationFn: async ({
      applicationId,
      status,
    }: {
      applicationId: number;
      status: 'reviewing' | 'approved' | 'rejected';
    }) =>
      api.reviewPartnerApplication(applicationId, {
        status,
        review_notes: reviewNotes[applicationId] || '',
      }),
    onSuccess: (_res, vars) => {
      successToast('Application updated', `Application #${vars.applicationId} → ${vars.status}.`);
      void queryClient.invalidateQueries({ queryKey: ['crm', 'summary'] });
      void queryClient.invalidateQueries({ queryKey: ['portal', 'applications'] });
      void queryClient.invalidateQueries({ queryKey: ['crm', 'users'] });
    },
    onError: (err: unknown) => {
      errorToast('Review failed', err instanceof Error ? err.message : 'Unknown error');
    },
  });

  const allApplications = applicationsQuery.data?.applications ?? [];

  const filtered = useMemo(() => {
    const base =
      statusFilter === 'all'
        ? allApplications
        : allApplications.filter((a) => a.status === statusFilter);
    return [...base].sort((a, b) => {
      const priority = { pending: 0, reviewing: 1, approved: 2, rejected: 3 };
      return (
        (priority[a.status as keyof typeof priority] ?? 9) -
          (priority[b.status as keyof typeof priority] ?? 9) || b.id - a.id
      );
    });
  }, [allApplications, statusFilter]);

  const counts = useMemo(() => {
    const result: Record<string, number> = { all: allApplications.length };
    for (const app of allApplications) {
      result[app.status] = (result[app.status] ?? 0) + 1;
    }
    return result;
  }, [allApplications]);

  return (
    <PageContainer size="wide" className="space-y-6">
      {/* Header */}
      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-6">
        <div className="premium-kicker">Application pipeline</div>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-white">Partner application queue</h1>
            <p className="mt-1 text-sm text-slate-400">
              Move requests through pending → reviewing → approved/rejected. Each action is
              timestamped and persisted with review notes.
            </p>
          </div>
          {applicationsQuery.isFetching && (
            <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
          )}
        </div>
      </div>

      {/* Status filter tabs */}
      <div className="flex flex-wrap gap-2">
        {(['all', 'pending', 'reviewing', 'approved', 'rejected'] as const).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setStatusFilter(s)}
            className={`rounded-lg border px-3 py-1.5 text-xs font-medium capitalize transition ${
              statusFilter === s
                ? 'border-cyan-500/40 bg-cyan-500/15 text-cyan-200'
                : 'border-slate-700/60 bg-slate-900/40 text-slate-400 hover:text-slate-200'
            }`}
          >
            {s === 'all' ? 'All' : s} {counts[s] ? `(${counts[s]})` : ''}
          </button>
        ))}
      </div>

      {/* Application cards */}
      {applicationsQuery.isLoading ? (
        <div className="flex items-center gap-2 text-slate-400">
          <Loader2 className="h-5 w-5 animate-spin" /> Loading applications…
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-700/60 bg-slate-950/40 p-12 text-center">
          <p className="text-sm font-medium text-slate-300">
            {statusFilter === 'all' ? 'Queue is clear' : `No ${statusFilter} applications`}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {statusFilter === 'all'
              ? 'Applications appear here as soon as users submit upgrade requests.'
              : 'Change the filter above to see other applications.'}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {filtered.map((app) => (
            <div
              key={app.id}
              className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-white">
                    #{app.id} · {app.business_name || 'Unnamed business'}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Applicant #{app.applicant_user_id} · Sponsor{' '}
                    {app.sponsor_user_id ? `#${app.sponsor_user_id}` : '—'} · Requested{' '}
                    <span className="uppercase">{app.requested_role}</span>
                  </p>
                </div>
                <span
                  className={`rounded-full border px-2.5 py-1 text-[10px] uppercase tracking-[0.16em] ${statusTone[app.status] ?? 'border-slate-600 bg-slate-700/40 text-slate-300'}`}
                >
                  {app.status}
                </span>
              </div>

              <div className="mt-3 grid gap-2 text-sm text-slate-300 md:grid-cols-2">
                <p className="text-xs text-slate-400">{app.notes || 'No notes provided.'}</p>
                <div className="space-y-1 text-xs text-slate-500">
                  <p>
                    Submitted:{' '}
                    <span className="text-slate-200">{formatDateTime(app.created_at)}</span>
                  </p>
                  <p>
                    Reviewed:{' '}
                    <span className="text-slate-200">{formatDateTime(app.reviewed_at)}</span>
                  </p>
                </div>
              </div>

              <textarea
                value={reviewNotes[app.id] ?? app.review_notes ?? ''}
                onChange={(e) => setReviewNotes((prev) => ({ ...prev, [app.id]: e.target.value }))}
                rows={3}
                placeholder="Internal review notes…"
                className="premium-input mt-4 min-h-20"
              />

              <div className="mt-4 flex flex-wrap gap-2">
                {app.status === 'pending' && (
                  <button
                    type="button"
                    disabled={reviewMutation.isPending}
                    onClick={() =>
                      reviewMutation.mutate({ applicationId: app.id, status: buildNextStatus(app) })
                    }
                    className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-sm font-medium text-cyan-200 transition hover:bg-cyan-500/20 disabled:opacity-60"
                  >
                    Mark reviewing
                  </button>
                )}
                {app.status !== 'approved' && (
                  <button
                    type="button"
                    disabled={reviewMutation.isPending}
                    onClick={() =>
                      reviewMutation.mutate({ applicationId: app.id, status: 'approved' })
                    }
                    className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm font-medium text-emerald-200 transition hover:bg-emerald-500/20 disabled:opacity-60"
                  >
                    Approve
                  </button>
                )}
                {app.status !== 'rejected' && (
                  <button
                    type="button"
                    disabled={reviewMutation.isPending}
                    onClick={() =>
                      reviewMutation.mutate({ applicationId: app.id, status: 'rejected' })
                    }
                    className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm font-medium text-red-200 transition hover:bg-red-500/20 disabled:opacity-60"
                  >
                    Reject
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </PageContainer>
  );
};
