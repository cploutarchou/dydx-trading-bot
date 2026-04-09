import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowUpRight, Building2, Loader2, Send, ShieldCheck } from 'lucide-react';
import { useMemo, useState } from 'react';
import api from '../api';
import { getUserWorkspaceRole } from '../auth/roles';
import { useToastStore } from '../components/ErrorBoundary';
import { PageContainer } from '../components/PageContainer';
import { useAuthStore } from '../store/auth';

const formatDateTime = (value?: string) => {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? '—' : parsed.toLocaleString();
};

const statusTone: Record<string, string> = {
  pending: 'border-amber-500/30 bg-amber-500/10 text-amber-200',
  reviewing: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-200',
  approved: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200',
  rejected: 'border-red-500/30 bg-red-500/10 text-red-200',
};

export const ClientAreaPage = () => {
  const user = useAuthStore((state) => state.user);
  const role = getUserWorkspaceRole(user);
  const queryClient = useQueryClient();
  const successToast = useToastStore((state) => state.success);
  const errorToast = useToastStore((state) => state.error);
  const [businessName, setBusinessName] = useState('');
  const [notes, setNotes] = useState('');
  const [sponsorUserId, setSponsorUserId] = useState('');

  const overviewQuery = useQuery({
    queryKey: ['portal', 'overview'],
    queryFn: async () => (await api.getPortalOverview()).data,
    staleTime: 20_000,
  });

  const applicationsQuery = useQuery({
    queryKey: ['portal', 'applications'],
    queryFn: async () => (await api.listPartnerApplications(100, 0)).data,
    staleTime: 10_000,
    refetchInterval: 20_000,
  });

  const applicationOptions = useMemo(() => {
    if (role === 'sub_ib') {
      return [{ value: 'ib', label: 'Request promotion to IB' }];
    }
    if (role === 'client' || role === 'user') {
      return [{ value: 'ib', label: 'Apply to become an IB' }];
    }
    return [];
  }, [role]);

  const [requestedRole, setRequestedRole] = useState<'ib' | 'sub_ib'>('ib');

  const submitMutation = useMutation({
    mutationFn: async () =>
      api.createPartnerApplication({
        requested_role: requestedRole,
        business_name: businessName,
        notes,
        ...(sponsorUserId.trim() ? { sponsor_user_id: Number(sponsorUserId) } : {}),
      }),
    onSuccess: () => {
      successToast('Application submitted', 'Your onboarding request is now queued for review.');
      setBusinessName('');
      setNotes('');
      setSponsorUserId('');
      void queryClient.invalidateQueries({ queryKey: ['portal', 'applications'] });
      void queryClient.invalidateQueries({ queryKey: ['portal', 'overview'] });
    },
    onError: (error: unknown) => {
      errorToast('Application failed', error instanceof Error ? error.message : 'Unknown error');
    },
  });

  const applications = applicationsQuery.data?.applications ?? [];
  const overview = overviewQuery.data;

  return (
    <PageContainer size="wide" className="space-y-6">
      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-6">
        <div className="premium-kicker">Client Area</div>
        <h1 className="mt-2 text-2xl font-semibold text-white">
          Account progression and partner onboarding
        </h1>
        <p className="mt-2 text-sm text-slate-400">
          Track your current workspace access, submit upgrade requests, and monitor every review
          without chasing support tickets into the void.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4">
          <div className="flex items-center gap-2 text-slate-300">
            <ShieldCheck className="h-4 w-4 text-cyan-300" /> Current Role
          </div>
          <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.14em] text-white">
            {overview?.role || role}
          </p>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4">
          <div className="flex items-center gap-2 text-slate-300">
            <ArrowUpRight className="h-4 w-4 text-emerald-300" /> Pending Requests
          </div>
          <p className="mt-3 text-2xl font-semibold text-white">
            {
              applications.filter(
                (item) => item.status === 'pending' || item.status === 'reviewing'
              ).length
            }
          </p>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4">
          <div className="flex items-center gap-2 text-slate-300">
            <Building2 className="h-4 w-4 text-violet-300" /> Available Modules
          </div>
          <p className="mt-3 text-2xl font-semibold text-white">{overview?.modules?.length ?? 0}</p>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.95fr,1.05fr]">
        <section className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
          <h2 className="text-lg font-semibold text-white">Promotion / partner application</h2>
          <p className="mt-1 text-sm text-slate-400">
            Apply for role upgrades with business context and, if relevant, a sponsor chain.
          </p>

          {applicationOptions.length === 0 ? (
            <div className="mt-4 rounded-xl border border-slate-700/60 bg-slate-950/60 p-4 text-sm text-slate-400">
              Your current role already has the highest client-side access available in this portal.
            </div>
          ) : (
            <>
              <div className="mt-4 space-y-3">
                <select
                  value={requestedRole}
                  onChange={(event) => setRequestedRole(event.target.value as 'ib' | 'sub_ib')}
                  className="premium-input"
                >
                  {applicationOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <input
                  value={businessName}
                  onChange={(event) => setBusinessName(event.target.value)}
                  placeholder="Business / desk name"
                  className="premium-input"
                />
                <input
                  value={sponsorUserId}
                  onChange={(event) => setSponsorUserId(event.target.value)}
                  placeholder="Sponsor user ID (optional)"
                  className="premium-input"
                />
                <textarea
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                  rows={5}
                  placeholder="Tell backoffice why this application should be approved."
                  className="premium-input min-h-35"
                />
              </div>

              <button
                type="button"
                onClick={() => submitMutation.mutate()}
                disabled={submitMutation.isPending}
                className="mt-5 inline-flex items-center gap-2 rounded-xl bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:bg-slate-700"
              >
                {submitMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
                Submit application
              </button>
            </>
          )}
        </section>

        <section className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
          <h2 className="text-lg font-semibold text-white">Application timeline</h2>
          <p className="mt-1 text-sm text-slate-400">
            Every role request, review note, and status change in one neat audit trail.
          </p>

          {applicationsQuery.isLoading ? (
            <div className="mt-4 flex items-center gap-2 text-slate-300">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading applications...
            </div>
          ) : applications.length === 0 ? (
            <div className="mt-4 rounded-xl border border-slate-700/60 bg-slate-950/60 p-4 text-sm text-slate-400">
              No applications submitted yet.
            </div>
          ) : (
            <div className="mt-4 space-y-3">
              {applications.map((application) => (
                <div
                  key={application.id}
                  className="rounded-xl border border-slate-700/60 bg-slate-950/60 p-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-white">
                        {application.business_name || `Application #${application.id}`}
                      </p>
                      <p className="mt-1 text-xs uppercase tracking-[0.16em] text-slate-500">
                        Requested role: {application.requested_role}
                      </p>
                    </div>
                    <span
                      className={`rounded-full border px-2.5 py-1 text-[11px] uppercase tracking-[0.16em] ${statusTone[application.status] || 'border-slate-600 bg-slate-700/40 text-slate-300'}`}
                    >
                      {application.status}
                    </span>
                  </div>
                  <p className="mt-3 text-sm text-slate-300">
                    {application.notes || 'No application notes provided.'}
                  </p>
                  <div className="mt-3 grid gap-2 text-xs text-slate-400 sm:grid-cols-2">
                    <p>
                      Submitted:{' '}
                      <span className="text-slate-200">
                        {formatDateTime(application.created_at)}
                      </span>
                    </p>
                    <p>
                      Reviewed:{' '}
                      <span className="text-slate-200">
                        {formatDateTime(application.reviewed_at)}
                      </span>
                    </p>
                  </div>
                  {application.review_notes && (
                    <div className="mt-3 rounded-lg border border-slate-700/60 bg-slate-900/70 p-3 text-sm text-slate-300">
                      <span className="font-medium text-slate-100">Review notes:</span>{' '}
                      {application.review_notes}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </PageContainer>
  );
};
