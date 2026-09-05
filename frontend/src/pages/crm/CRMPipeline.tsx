import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2, Workflow } from 'lucide-react';
import { useMemo, useState } from 'react';
import api, { type PartnerApplication } from '../../api';
import { useToastStore } from '../../components/ErrorBoundary';
import { PageContainer } from '../../components/PageContainer';
import {
  EmptyState,
  PlatformPageHeader,
  StatusBadge,
  toneForStatus,
} from '../../components/ui/PlatformUI';

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

  const applicationsData = applicationsQuery.data?.applications;

  const filtered = useMemo(() => {
    const source = applicationsData ?? [];
    const base = statusFilter === 'all' ? source : source.filter((a) => a.status === statusFilter);
    return [...base].sort((a, b) => {
      const priority = { pending: 0, reviewing: 1, approved: 2, rejected: 3 };
      return (
        (priority[a.status as keyof typeof priority] ?? 9) -
          (priority[b.status as keyof typeof priority] ?? 9) || b.id - a.id
      );
    });
  }, [applicationsData, statusFilter]);

  const counts = useMemo(() => {
    const source = applicationsData ?? [];
    const result: Record<string, number> = { all: source.length };
    for (const app of source) {
      result[app.status] = (result[app.status] ?? 0) + 1;
    }
    return result;
  }, [applicationsData]);

  return (
    <PageContainer size="wide" className="space-y-6">
      <PlatformPageHeader
        kicker="Application pipeline"
        title="Partner application queue"
        description="Move requests through pending, reviewing, approved, and rejected states. Each action is persisted with review notes for auditability."
        icon={Workflow}
        meta={
          applicationsQuery.isFetching ? (
            <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
          ) : null
        }
      />

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

      {applicationsQuery.isLoading ? (
        <div className="flex items-center gap-2 text-slate-400">
          <Loader2 className="h-5 w-5 animate-spin" /> Loading applications...
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Workflow}
          title={statusFilter === 'all' ? 'Queue is clear' : `No ${statusFilter} applications`}
          description={
            statusFilter === 'all'
              ? 'Applications appear here as soon as users submit upgrade requests.'
              : 'Change the filter above to see other applications.'
          }
        />
      ) : (
        <div className="space-y-4">
          {filtered.map((app) => (
            <div key={app.id} className="platform-panel p-5">
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
                <StatusBadge tone={toneForStatus(app.status)}>{app.status}</StatusBadge>
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
                    className="platform-button platform-button-secondary text-cyan-200 disabled:opacity-60"
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
                    className="platform-button platform-button-secondary text-emerald-200 disabled:opacity-60"
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
                    className="platform-button platform-button-secondary text-red-200 disabled:opacity-60"
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
