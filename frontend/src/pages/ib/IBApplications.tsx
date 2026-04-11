import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2, PlusCircle } from 'lucide-react';
import { useMemo, useState } from 'react';
import api, { type CreatePartnerApplicationPayload } from '../../api';
import { getUserWorkspaceRole } from '../../auth/roles';
import { useToastStore } from '../../components/ErrorBoundary';
import { PageContainer } from '../../components/PageContainer';
import { useAuthStore } from '../../store/auth';

type StatusFilter = 'all' | 'pending' | 'reviewing' | 'approved' | 'rejected';

const statusColors: Record<string, string> = {
  pending: 'border-amber-500/30 bg-amber-500/10 text-amber-200',
  reviewing: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-200',
  approved: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200',
  rejected: 'border-red-700/30 bg-red-900/20 text-red-300',
};

const formatDateTime = (value?: string) => {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '—';
  return parsed.toLocaleString();
};

const STATUS_FILTERS: StatusFilter[] = ['all', 'pending', 'reviewing', 'approved', 'rejected'];

export const IBApplications = () => {
  const user = useAuthStore((state) => state.user);
  const role = getUserWorkspaceRole(user);
  const queryClient = useQueryClient();
  const successToast = useToastStore((state) => state.success);
  const errorToast = useToastStore((state) => state.error);

  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<CreatePartnerApplicationPayload>({
    requested_role: 'ib',
    business_name: '',
    notes: '',
  });

  const applicationsQuery = useQuery({
    queryKey: ['portal', 'applications', 'ib'],
    queryFn: async () => (await api.listPartnerApplications(200, 0)).data,
    staleTime: 10_000,
    refetchInterval: 20_000,
  });

  const createMutation = useMutation({
    mutationFn: async (payload: CreatePartnerApplicationPayload) =>
      api.createPartnerApplication(payload),
    onSuccess: () => {
      successToast('Application submitted', 'Your upgrade request is now under review.');
      setForm({ requested_role: 'ib', business_name: '', notes: '' });
      setShowForm(false);
      void queryClient.invalidateQueries({ queryKey: ['portal', 'applications', 'ib'] });
    },
    onError: (error: unknown) => {
      errorToast('Failed to submit', error instanceof Error ? error.message : 'Unknown error');
    },
  });

  const applications = applicationsQuery.data?.applications ?? [];
  // Only sub_ib can apply for an IB upgrade through this portal
  const canApply = role === 'sub_ib';

  const filtered = useMemo(
    () =>
      statusFilter === 'all' ? applications : applications.filter((a) => a.status === statusFilter),
    [applications, statusFilter]
  );

  const counts = useMemo(
    () => ({
      all: applications.length,
      pending: applications.filter((a) => a.status === 'pending').length,
      reviewing: applications.filter((a) => a.status === 'reviewing').length,
      approved: applications.filter((a) => a.status === 'approved').length,
      rejected: applications.filter((a) => a.status === 'rejected').length,
    }),
    [applications]
  );

  return (
    <PageContainer size="wide" className="space-y-6">
      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-6">
        <div className="premium-kicker">Applications</div>
        <h1 className="mt-2 text-2xl font-semibold text-white">Partner applications</h1>
        <p className="mt-2 text-sm text-slate-400">
          Track partner upgrade requests visible to your role. Admins and backoffice see all; IBs
          see their sponsored applications; sub-IBs see their own.
        </p>
      </div>

      {/* Status filter bar */}
      <div className="flex flex-wrap items-center gap-2">
        {STATUS_FILTERS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setStatusFilter(s)}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
              statusFilter === s
                ? 'bg-cyan-500/15 text-cyan-200'
                : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
            }`}
          >
            {s === 'all' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}{' '}
            <span className="ml-1 tabular-nums text-slate-500">({counts[s]})</span>
          </button>
        ))}
        {canApply && (
          <button
            type="button"
            onClick={() => setShowForm((v) => !v)}
            className="ml-auto flex items-center gap-1.5 rounded-lg border border-cyan-700/40 bg-cyan-900/20 px-3 py-1.5 text-sm font-medium text-cyan-200 transition hover:bg-cyan-900/35"
          >
            <PlusCircle className="h-3.5 w-3.5" />
            Apply for IB upgrade
          </button>
        )}
      </div>

      {/* Apply form — sub_ib only */}
      {canApply && showForm && (
        <div className="rounded-2xl border border-cyan-700/40 bg-slate-900/70 p-5">
          <h2 className="text-lg font-semibold text-white">Apply for IB upgrade</h2>
          <p className="mt-1 text-sm text-slate-400">
            Submit a request to be promoted from sub-IB to IB status. A backoffice reviewer will
            assess your application.
          </p>
          <div className="mt-4 space-y-3">
            <input
              value={String(form.business_name ?? '')}
              onChange={(e) => setForm((prev) => ({ ...prev, business_name: e.target.value }))}
              placeholder="Business name (optional)"
              className="premium-input"
            />
            <textarea
              value={String(form.notes ?? '')}
              onChange={(e) => setForm((prev) => ({ ...prev, notes: e.target.value }))}
              placeholder="Notes or context for reviewers..."
              rows={3}
              className="premium-input resize-none"
            />
          </div>
          <div className="mt-4 flex gap-3">
            <button
              type="button"
              onClick={() => createMutation.mutate({ ...form, requested_role: 'ib' })}
              disabled={createMutation.isPending}
              className="inline-flex items-center gap-2 rounded-xl bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:bg-slate-700"
            >
              {createMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <PlusCircle className="h-4 w-4" />
              )}
              Submit application
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="rounded-xl border border-slate-700/60 bg-slate-800/60 px-4 py-2.5 text-sm font-medium text-slate-300 transition hover:text-white"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Application cards */}
      {applicationsQuery.isLoading ? (
        <div className="flex items-center gap-2 text-slate-300">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading applications...
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-700/60 bg-slate-900/40 p-10 text-center">
          <p className="text-sm font-medium text-slate-300">No applications match this filter</p>
          <p className="mt-1 text-xs text-slate-500">
            {statusFilter === 'all'
              ? 'Applications appear here once users submit partner upgrade requests.'
              : `No ${statusFilter} applications in scope.`}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {filtered.map((application) => (
            <div
              key={application.id}
              className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-base font-semibold text-white">
                    {application.business_name || `Application #${application.id}`}
                  </p>
                  <p className="mt-1 text-xs uppercase tracking-[0.14em] text-slate-500">
                    Requested {application.requested_role} · Applicant user{' '}
                    {application.applicant_user_id}
                    {application.sponsor_user_id
                      ? ` · Sponsor #${application.sponsor_user_id}`
                      : ''}
                  </p>
                </div>
                <span
                  className={`rounded-full border px-2.5 py-1 text-[11px] uppercase tracking-[0.14em] ${statusColors[application.status] ?? 'border-slate-600 bg-slate-700/40 text-slate-300'}`}
                >
                  {application.status}
                </span>
              </div>
              {application.notes && (
                <p className="mt-3 text-sm text-slate-300">{application.notes}</p>
              )}
              {application.review_notes && (
                <div className="mt-3 rounded-xl border border-slate-700/40 bg-slate-950/50 p-3">
                  <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Review notes</p>
                  <p className="mt-1 text-sm text-slate-300">{application.review_notes}</p>
                </div>
              )}
              <div className="mt-4 grid grid-cols-2 gap-3 text-xs text-slate-400 sm:grid-cols-3">
                <p>
                  Submitted:{' '}
                  <span className="font-medium text-slate-200">
                    {formatDateTime(application.created_at)}
                  </span>
                </p>
                {application.reviewed_at && (
                  <p>
                    Reviewed:{' '}
                    <span className="font-medium text-slate-200">
                      {formatDateTime(application.reviewed_at)}
                    </span>
                  </p>
                )}
                {application.reviewed_by_user_id && (
                  <p>
                    Reviewer:{' '}
                    <span className="font-medium text-slate-200">
                      #{application.reviewed_by_user_id}
                    </span>
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </PageContainer>
  );
};
