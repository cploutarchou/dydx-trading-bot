import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowUpRight, Building2, Loader2, Send, ShieldCheck } from 'lucide-react';
import { useMemo, useState } from 'react';
import api from '../api';
import { getUserWorkspaceRole } from '../auth/roles';
import { useToastStore } from '../components/ErrorBoundary';
import { PageContainer } from '../components/PageContainer';
import {
  EmptyState,
  PlatformPageHeader,
  PlatformPanel,
  PlatformStatCard,
  StatusBadge,
  toneForStatus,
} from '../components/ui/PlatformUI';
import { useAuthStore } from '../store/auth';

const formatDateTime = (value?: string) => {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? '—' : parsed.toLocaleString();
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
      <PlatformPageHeader
        kicker="Client Area"
        title="Account progression and partner onboarding"
        description="Track workspace access, request partner upgrades, and keep every review step visible without support-ticket guesswork."
        icon={ShieldCheck}
      />

      <div className="grid gap-4 md:grid-cols-3">
        <PlatformStatCard
          label="Current role"
          value={<span className="uppercase">{overview?.role || role}</span>}
          icon={ShieldCheck}
          tone="accent"
          loading={overviewQuery.isLoading}
          detail="Access profile currently active for this account."
        />
        <PlatformStatCard
          label="Pending requests"
          value={
            applications.filter(
              (item) => item.status === 'pending' || item.status === 'reviewing'
            ).length
          }
          icon={ArrowUpRight}
          tone="success"
          loading={applicationsQuery.isLoading}
          detail="Applications waiting for backoffice action."
        />
        <PlatformStatCard
          label="Available modules"
          value={overview?.modules?.length ?? 0}
          icon={Building2}
          tone="violet"
          loading={overviewQuery.isLoading}
          detail="Workspace surfaces available to this role."
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.95fr,1.05fr]">
        <PlatformPanel
          title="Promotion / partner application"
          description="Submit role upgrades with business context and, when relevant, a sponsor chain."
        >
          {applicationOptions.length === 0 ? (
            <EmptyState
              icon={ShieldCheck}
              title="No upgrade request needed"
              description="Your current role already has the highest client-side access available in this portal."
            />
          ) : (
            <>
              <div className="space-y-3">
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
                className="platform-button platform-button-primary mt-5 disabled:cursor-not-allowed disabled:opacity-60"
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
        </PlatformPanel>

        <PlatformPanel
          title="Application timeline"
          description="Every role request, review note, and status change in one audit trail."
        >
          {applicationsQuery.isLoading ? (
            <div className="flex items-center gap-2 text-slate-300">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading applications...
            </div>
          ) : applications.length === 0 ? (
            <EmptyState
              icon={Send}
              title="No applications submitted"
              description="Submitted upgrade requests will appear here with review state and backoffice notes."
            />
          ) : (
            <div className="space-y-3">
              {applications.map((application) => (
                <div
                  key={application.id}
                  className="rounded-lg border border-slate-700/60 bg-slate-950/60 p-4"
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
                    <StatusBadge tone={toneForStatus(application.status)}>
                      {application.status}
                    </StatusBadge>
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
        </PlatformPanel>
      </div>
    </PageContainer>
  );
};
