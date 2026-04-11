import { useQuery } from '@tanstack/react-query';
import { GitBranch, KeyRound, Loader2, ScrollText, Users, WalletCards } from 'lucide-react';
import { Link } from 'react-router-dom';
import api from '../../api';
import { getUserWorkspaceRole } from '../../auth/roles';
import { PageContainer } from '../../components/PageContainer';
import { useAuthStore } from '../../store/auth';
import { ibPortalPath } from './paths';

const formatCurrency = (value?: number) => {
  const numeric = Number(value || 0);
  return `$${numeric.toLocaleString('en-US', { maximumFractionDigits: 2, minimumFractionDigits: 2 })}`;
};

export const IBDashboard = () => {
  const user = useAuthStore((state) => state.user);
  const role = getUserWorkspaceRole(user);

  const overviewQuery = useQuery({
    queryKey: ['portal', 'overview', 'ib'],
    queryFn: async () => (await api.getPortalOverview()).data,
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
      {/* Header */}
      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-6">
        <div className="premium-kicker">IB Portal</div>
        <h1 className="mt-2 text-2xl font-semibold text-white">Partner dashboard</h1>
        <p className="mt-2 text-sm text-slate-400">
          Overview of your introducing broker activity, partner network, and commission metrics.
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4">
          <div className="flex items-center gap-2 text-slate-300">
            <Users className="h-4 w-4 text-cyan-300" /> Direct partners
          </div>
          <p className="mt-3 text-2xl font-semibold text-white">{relationships.length}</p>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4">
          <div className="flex items-center gap-2 text-slate-300">
            <GitBranch className="h-4 w-4 text-violet-300" /> Sub-IBs
          </div>
          <p className="mt-3 text-2xl font-semibold text-white">{overview?.counts?.sub_ibs ?? 0}</p>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4">
          <div className="flex items-center gap-2 text-slate-300">
            <WalletCards className="h-4 w-4 text-emerald-300" /> Net commission
          </div>
          <p className="mt-3 text-2xl font-semibold text-white">
            {ownerCommission?.net_commission_usd
              ? formatCurrency(ownerCommission.net_commission_usd)
              : '—'}
          </p>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4">
          <div className="flex items-center gap-2 text-slate-300">
            <ScrollText className="h-4 w-4 text-amber-300" /> Open applications
          </div>
          <p className="mt-3 text-2xl font-semibold text-white">{openApplications.length}</p>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        {/* Role & overview card */}
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
          <h2 className="text-lg font-semibold text-white">Portal overview</h2>
          <p className="mt-1 text-sm text-slate-400">
            Your current workspace role and available modules.
          </p>
          <div className="mt-4 space-y-3">
            <div className="rounded-xl border border-slate-700/60 bg-slate-950/60 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Current role</p>
              <p className="mt-2 text-xl font-semibold uppercase tracking-[0.14em] text-white">
                {overview?.role || role}
              </p>
            </div>
            <div className="rounded-xl border border-slate-700/60 bg-slate-950/60 p-4">
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
                className="rounded-xl border border-slate-700/60 bg-slate-950/60 p-4 transition hover:border-cyan-500/40 hover:bg-slate-950/80"
              >
                <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Network edges</p>
                <p className="mt-2 text-2xl font-semibold text-white">{relationships.length}</p>
                <p className="mt-1 text-xs text-cyan-400">View network →</p>
              </Link>
              <Link
                to={ibPortalPath('applications')}
                className="rounded-xl border border-slate-700/60 bg-slate-950/60 p-4 transition hover:border-cyan-500/40 hover:bg-slate-950/80"
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
              className="rounded-lg border border-slate-700/60 bg-slate-800/60 px-3 py-2 text-sm text-slate-300 transition hover:text-white"
            >
              <WalletCards className="mr-1.5 inline h-3.5 w-3.5" />
              Commission metrics
            </Link>
            {(user?.is_admin || role === 'backoffice') && (
              <Link
                to={ibPortalPath('tokens')}
                className="rounded-lg border border-cyan-700/40 bg-cyan-900/20 px-3 py-2 text-sm text-cyan-200 transition hover:bg-cyan-900/35"
              >
                <KeyRound className="mr-1.5 inline h-3.5 w-3.5" />
                Manage tokens
              </Link>
            )}
          </div>
        </div>

        {/* Recent applications */}
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
          <h2 className="text-lg font-semibold text-white">Recent applications</h2>
          <p className="mt-1 text-sm text-slate-400">
            Latest partner upgrade requests visible to your role.
          </p>
          {applicationsQuery.isLoading ? (
            <div className="mt-4 flex items-center gap-2 text-slate-300">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading...
            </div>
          ) : recentApplications.length === 0 ? (
            <div className="mt-4 rounded-xl border border-dashed border-slate-700/60 bg-slate-950/40 p-6 text-center">
              <p className="text-sm font-medium text-slate-300">No applications in scope</p>
              <p className="mt-1 text-xs text-slate-500">
                Applications appear once partner upgrade requests are visible to your role.
              </p>
            </div>
          ) : (
            <div className="mt-4 space-y-3">
              {recentApplications.map((application) => (
                <div
                  key={application.id}
                  className="rounded-xl border border-slate-700/60 bg-slate-950/60 p-4"
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
                    <span
                      className={`rounded-full border px-2.5 py-1 text-[11px] uppercase tracking-[0.14em] ${
                        application.status === 'pending' || application.status === 'reviewing'
                          ? 'border-amber-500/30 bg-amber-500/10 text-amber-200'
                          : application.status === 'approved'
                            ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
                            : 'border-slate-600 bg-slate-700/40 text-slate-300'
                      }`}
                    >
                      {application.status}
                    </span>
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
        </div>
      </div>
    </PageContainer>
  );
};
