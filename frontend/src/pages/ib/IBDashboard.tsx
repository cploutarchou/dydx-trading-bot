import { useQuery } from '@tanstack/react-query';
import { GitBranch, KeyRound, Loader2, ScrollText, Users, WalletCards } from 'lucide-react';
import { Link } from 'react-router-dom';
import api from '../../api';
import { BACKOFFICE_ROLES, getUserWorkspaceRole, roleMatches } from '../../auth/roles';
import { PageContainer } from '../../components/PageContainer';
import {
  EmptyState,
  PlatformPageHeader,
  PlatformPanel,
  PlatformStatCard,
  StatusBadge,
  toneForStatus,
} from '../../components/ui/PlatformUI';
import { useAuthStore } from '../../store/auth';
import { formatUsdFixed } from '../../utils/format';
import { ibPortalPath } from './paths';

export const IBDashboard = () => {
  const user = useAuthStore((state) => state.user);
  const role = getUserWorkspaceRole(user);
  const canManageIB = roleMatches(role, BACKOFFICE_ROLES);

  const overviewQuery = useQuery({
    queryKey: ['ib', 'dashboard'],
    queryFn: async () => (await api.getIBDashboard()).data,
    staleTime: 20_000,
  });

  const applicationsQuery = useQuery({
    queryKey: ['portal', 'applications', 'ib'],
    queryFn: async () => (await api.listPartnerApplications(100, 0)).data,
    staleTime: 10_000,
    refetchInterval: 30_000,
  });

  const commissionQuery = useQuery({
    queryKey: ['portal', 'commission-metrics', 'ib'],
    queryFn: async () => (await api.getPartnerCommissionMetrics()).data,
    staleTime: 10_000,
    refetchInterval: 60_000,
  });

  const hierarchyQuery = useQuery({
    queryKey: ['portal', 'hierarchy', 'ib'],
    queryFn: async () => (await api.getPartnerHierarchy()).data,
    staleTime: 10_000,
  });

  const overview = overviewQuery.data;
  const applications = applicationsQuery.data?.applications ?? [];
  const ownerCommission = commissionQuery.data?.owner;
  const relationships = hierarchyQuery.data?.relationships ?? [];

  const openApplications = applications.filter(
    (a) => a.status === 'pending' || a.status === 'reviewing'
  );
  const recentApplications = applications.slice(0, 5);

  return (
    <PageContainer size="wide" className="space-y-6">
      <PlatformPageHeader
        kicker="IB Portal"
        title="Partner dashboard"
        description="Track introducing broker activity, referral network growth, open applications, and commission performance with business-grade clarity."
        icon={WalletCards}
        actions={[{ label: 'View commissions', to: ibPortalPath('commissions') }]}
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <PlatformStatCard
          label="Direct partners"
          value={relationships.length}
          icon={Users}
          tone="accent"
          loading={hierarchyQuery.isLoading}
        />
        <PlatformStatCard
          label="Sub-IBs"
          value={overview?.counts?.sub_ibs ?? 0}
          icon={GitBranch}
          tone="violet"
          loading={overviewQuery.isLoading}
        />
        <PlatformStatCard
          label="Net commission"
          value={
            ownerCommission?.net_commission_usd
              ? formatUsdFixed(ownerCommission.net_commission_usd)
              : '—'
          }
          icon={WalletCards}
          tone="success"
          loading={commissionQuery.isLoading}
        />
        <PlatformStatCard
          label="Open applications"
          value={openApplications.length}
          icon={ScrollText}
          tone={openApplications.length > 0 ? 'warning' : 'success'}
          loading={applicationsQuery.isLoading}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <PlatformPanel
          title="Portal overview"
          description="Current role, available modules, and shortcut paths for the partner workflow."
        >
          <div className="space-y-3">
            <div className="rounded-lg border border-slate-700/60 bg-slate-950/60 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Current role</p>
              <p className="mt-2 text-xl font-semibold uppercase tracking-[0.14em] text-white">
                {overview?.role || role}
              </p>
            </div>
            <div className="rounded-lg border border-slate-700/60 bg-slate-950/60 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                Available modules
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {overviewQuery.isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
                ) : (
                  (overview?.modules ?? []).map((module) => (
                    <span
                      key={module.key}
                      className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-cyan-200"
                    >
                      {module.title}
                    </span>
                  ))
                )}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Link
                to={ibPortalPath('network')}
                className="rounded-lg border border-slate-700/60 bg-slate-950/60 p-4 transition hover:border-cyan-500/40 hover:bg-slate-950/80"
              >
                <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Network edges</p>
                <p className="mt-2 text-2xl font-semibold text-white">{relationships.length}</p>
                <p className="mt-1 text-xs text-cyan-400">View network →</p>
              </Link>
              <Link
                to={ibPortalPath('applications')}
                className="rounded-lg border border-slate-700/60 bg-slate-950/60 p-4 transition hover:border-cyan-500/40 hover:bg-slate-950/80"
              >
                <p className="text-xs uppercase tracking-[0.14em] text-slate-500">
                  In-view applications
                </p>
                <p className="mt-2 text-2xl font-semibold text-white">{applications.length}</p>
                <p className="mt-1 text-xs text-cyan-400">View all →</p>
              </Link>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link
              to={ibPortalPath('commissions')}
              className="platform-button platform-button-secondary"
            >
              <WalletCards className="mr-1.5 inline h-3.5 w-3.5" />
              Commission metrics
            </Link>
            {canManageIB && (
              <Link
                to={ibPortalPath('tokens')}
                className="platform-button platform-button-primary"
              >
                <KeyRound className="mr-1.5 inline h-3.5 w-3.5" />
                Manage tokens
              </Link>
            )}
          </div>
        </PlatformPanel>

        <PlatformPanel
          title="Recent applications"
          description="Latest partner upgrade requests visible to your role."
        >
          {applicationsQuery.isLoading ? (
            <div className="mt-4 flex items-center gap-2 text-slate-300">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading...
            </div>
          ) : recentApplications.length === 0 ? (
            <EmptyState
              icon={ScrollText}
              title="No applications in scope"
              description="Applications appear once partner upgrade requests are visible to your role."
            />
          ) : (
            <div className="space-y-3">
              {recentApplications.map((application) => (
                <div
                  key={application.id}
                  className="rounded-lg border border-slate-700/60 bg-slate-950/60 p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-white">
                        {application.business_name || `Application #${application.id}`}
                      </p>
                      <p className="mt-1 text-xs uppercase tracking-[0.14em] text-slate-500">
                        {application.requested_role} · user {application.applicant_user_id}
                      </p>
                    </div>
                    <StatusBadge tone={toneForStatus(application.status)}>
                      {application.status}
                    </StatusBadge>
                  </div>
                </div>
              ))}
              <Link
                to={ibPortalPath('applications')}
                className="mt-2 block text-center text-xs text-cyan-400 transition hover:text-cyan-200"
              >
                View all applications →
              </Link>
            </div>
          )}
        </PlatformPanel>
      </div>
    </PageContainer>
  );
};
