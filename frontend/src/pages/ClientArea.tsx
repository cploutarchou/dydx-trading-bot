import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
	ArrowRight,
	ArrowUpRight,
	BrainCircuit,
	Building2,
	CheckCircle2,
	Compass,
	Loader2,
	Send,
	ShieldCheck,
	Sparkles,
	WalletCards,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
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
import { useAIProviderAvailability } from '../features/ai/providerAvailability';
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
  const pendingApplications = applications.filter(
    (item) => item.status === 'pending' || item.status === 'reviewing'
  );
  const assistantStatus = useAIProviderAvailability();
  const assistantReady = assistantStatus.availableProviders.length > 0;
  const moduleCount = overview?.modules?.length ?? 0;

  const guidanceCards = [
    {
      title: 'Secure account access',
      description: 'Confirm profile details, 2FA, sessions, and dYdX keys before live execution.',
      href: '/settings?section=security',
      action: 'Review security',
      icon: ShieldCheck,
      status: 'Recommended',
    },
    {
      title: 'Research market context',
      description: assistantReady
        ? 'Use guided market filters and token intelligence to shortlist cleaner opportunities.'
        : 'Use Market Intel now; guided filters become available when assistant access is enabled.',
      href: '/market-intel',
      action: 'Open Market Intel',
      icon: Sparkles,
      status: assistantReady ? 'Guidance ready' : 'Core research ready',
    },
    {
      title: 'Validate before deployment',
      description:
        'Move from strategy idea to backtest, compare results, then deploy only validated setups.',
      href: '/backtests',
      action: 'Open Backtests',
      icon: Compass,
      status: 'Validation path',
    },
    {
      title: 'Monitor live runtime health',
      description:
        'Use the Bots desk for live strategy P/L, open positions, runtime uptime, and latest heartbeat updates.',
      href: '/bots',
      action: 'Open Bots desk',
      icon: BrainCircuit,
      status: 'Live monitoring',
    },
    {
      title: 'Prepare wallet credentials',
      description:
        'Keep wallet and API credentials current so approved strategies can move into Bots cleanly.',
      href: '/settings?section=dydx_keys',
      action: 'Review keys',
      icon: WalletCards,
      status: moduleCount > 0 ? `${moduleCount} modules` : 'Account setup',
    },
  ];

  return (
    <PageContainer size="wide" className="space-y-6">
      <PlatformPageHeader
        kicker="Client Area"
        title="Account readiness and guided onboarding"
        description="See what is active, what needs review, and the fastest next step from account setup into research, validation, and live monitoring."
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
          value={pendingApplications.length}
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

      <div className="grid gap-6 xl:grid-cols-[1.1fr,0.9fr]">
        <PlatformPanel
          title="Guided next steps"
          description="Use this client path: secure the account, research markets, validate strategies, then monitor live bots with real runtime metrics."
        >
          <div className="grid gap-3 md:grid-cols-2">
            {guidanceCards.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.title}
                  to={item.href}
                  className="group rounded-lg border border-slate-700/60 bg-slate-950/55 p-4 transition hover:border-cyan-500/45 hover:bg-slate-900/70"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex min-w-0 items-start gap-3">
                      <div className="rounded-lg border border-cyan-500/20 bg-cyan-500/10 p-2 text-cyan-300">
                        <Icon className="h-4 w-4" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-white">{item.title}</p>
                        <p className="mt-1 text-xs leading-5 text-slate-400">{item.description}</p>
                      </div>
                    </div>
                    <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-slate-500 transition group-hover:text-cyan-300" />
                  </div>
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                    <span className="rounded-full border border-slate-700 bg-slate-900/80 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-300">
                      {item.status}
                    </span>
                    <span className="text-xs font-medium text-cyan-300">{item.action}</span>
                  </div>
                </Link>
              );
            })}
          </div>
        </PlatformPanel>

        <PlatformPanel
          title="Smart guidance status"
          description="Assistant features are embedded directly in Market Intel, Strategies, Backtests, and live runtime monitoring so users get help exactly where decisions are made."
        >
          <div className="rounded-lg border border-cyan-500/20 bg-cyan-500/10 p-4">
            <div className="flex items-start gap-3">
              <div className="rounded-lg bg-slate-950/50 p-2 text-cyan-300">
                {assistantStatus.isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : assistantReady ? (
                  <BrainCircuit className="h-4 w-4" />
                ) : (
                  <Sparkles className="h-4 w-4" />
                )}
              </div>
              <div>
                <p className="text-sm font-semibold text-white">
                  {assistantStatus.isLoading
                    ? 'Checking guidance access'
                    : assistantReady
                      ? 'Guided assistance is ready'
                      : 'Core workflows are ready'}
                </p>
                <p className="mt-1 text-sm leading-6 text-slate-300">
                  {assistantReady
                    ? 'You can use guided market filters, strategy suggestions, backtest explanations, and runtime summaries from their dedicated workspaces.'
                    : 'You can still use the full portal. Guided recommendations will appear automatically when account access is enabled.'}
                </p>
              </div>
            </div>
          </div>

          <div className="mt-4 space-y-3 text-sm text-slate-300">
            <div className="flex gap-2">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300" />
              <span>Research help lives in Market Intel so the Dashboard stays simple.</span>
            </div>
            <div className="flex gap-2">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300" />
              <span>Strategy and backtest guidance stays close to the workflow it improves.</span>
            </div>
            <div className="flex gap-2">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300" />
              <span>Live runtime guidance is available from Bots and monitoring surfaces.</span>
            </div>
            <div className="flex gap-2">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300" />
              <span>
                Bots now surface runtime uptime, strategy P/L, and latest update timestamp together.
              </span>
            </div>
          </div>
        </PlatformPanel>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.95fr,1.05fr]">
        <PlatformPanel
          title="Partner application"
          description="Request a role upgrade with enough business context for backoffice to decide quickly."
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
                  placeholder="Business, desk, or community name"
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
                  placeholder="Describe your audience, expected activity, operating region, and why the upgrade is needed."
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
          description="Every request, review note, and status change stays visible here."
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
