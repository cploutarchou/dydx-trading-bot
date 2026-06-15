import { useQuery } from '@tanstack/react-query';
import { Activity, ArrowRight, LockKeyhole, ShieldCheck, Users, Workflow } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import api from '../api';
import { PageContainer } from '../components/PageContainer';
import {
    EmptyState,
    InlineNotice,
    PlatformPageHeader,
    PlatformPanel,
    PlatformStatCard,
} from '../components/ui/PlatformUI';
import { crmHref } from './crm/paths';
import { ibPortalHref } from './ib/paths';

const resolveModuleHref = (route: string | undefined): string => {
  if (!route) return '/dashboard';
  if (route.startsWith('/crm/')) {
    return crmHref(route.replace('/crm/', ''));
  }
  if (route.startsWith('/ib-portal/')) {
    return ibPortalHref(route.replace('/ib-portal/', ''));
  }
  return route;
};

export const AdminHubPage = () => {
  const navigate = useNavigate();

  const getApiErrorCode = (error: unknown): string | null => {
    if (
      typeof error === 'object' &&
      error !== null &&
      'response' in error &&
      typeof (error as { response?: unknown }).response === 'object' &&
      (error as { response?: unknown }).response !== null
    ) {
      const response = (error as { response?: { data?: { code?: unknown } } }).response;
      const code = response?.data?.code;
      if (typeof code === 'string' && code.trim().length > 0) {
        return code.trim().toLowerCase();
      }
    }

    return null;
  };

  const overviewQuery = useQuery({
    queryKey: ['portal', 'overview', 'admin'],
    queryFn: async () => (await api.getPortalOverview()).data,
    staleTime: 20_000,
  });

  const summaryQuery = useQuery({
    queryKey: ['crm', 'summary', 'admin'],
    queryFn: async () => (await api.getCRMSummary()).data,
    staleTime: 20_000,
  });

  const botStatsQuery = useQuery({
    queryKey: ['admin', 'bot-api-stats'],
    queryFn: async () => (await api.getBotAPIStats()).data,
    staleTime: 15_000,
    refetchInterval: 30_000,
  });

  const modules = overviewQuery.data?.modules ?? [];
  const pendingApps = summaryQuery.data?.pending_partner_applications ?? 0;
  const mfaEnrollmentRequired = [overviewQuery.error, summaryQuery.error, botStatsQuery.error]
    .map(getApiErrorCode)
    .some((code) => code === 'mfa_required');

  if (mfaEnrollmentRequired) {
    return (
      <PageContainer size="wide" className="space-y-6">
        <InlineNotice
          tone="warning"
          title="MFA enrollment required"
          description="Admin hub operations are protected. Complete 2FA enrollment before accessing this workspace."
          action={
            <button
              type="button"
              onClick={() => navigate('/2fa-setup')}
              className="rounded-lg border border-amber-500/30 bg-amber-500/15 px-4 py-2 text-sm font-medium text-amber-100 transition hover:border-amber-400/40 hover:bg-amber-500/20"
            >
              Open 2FA setup
            </button>
          }
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer size="wide" className="space-y-6">
      <PlatformPageHeader
        kicker="Admin Hub"
        title="Platform operations command center"
        description="Oversee access, partner growth, CRM flow, security posture, and high-importance operating surfaces from one controlled workspace."
        icon={ShieldCheck}
        actions={[
          { label: 'Open CRM', href: crmHref('dashboard'), variant: 'secondary' },
          { label: 'Open IB Portal', href: ibPortalHref('dashboard') },
        ]}
      />

      <div className="grid gap-4 md:grid-cols-4">
        {[
          {
            label: 'Active users',
            value: summaryQuery.data?.active_users ?? 0,
            icon: Users,
            tone: 'accent' as const,
          },
          {
            label: 'Pending partner apps',
            value: pendingApps,
            icon: Workflow,
            tone: pendingApps > 0 ? ('warning' as const) : ('success' as const),
          },
          {
            label: 'Portal modules',
            value: modules.length,
            icon: Activity,
            tone: 'violet' as const,
          },
          {
            label: 'Security surfaces',
            value: 3,
            icon: LockKeyhole,
            tone: 'success' as const,
          },
        ].map((card) => {
          return (
            <PlatformStatCard
              key={card.label}
              label={card.label}
              value={card.value}
              icon={card.icon}
              tone={card.tone}
              loading={summaryQuery.isLoading || overviewQuery.isLoading}
            />
          );
        })}
      </div>

      <PlatformPanel
        title="Role-based workspaces"
        description="Live surfaces available to the current admin account."
      >
        {modules.length === 0 && !overviewQuery.isLoading ? (
          <EmptyState
            icon={Activity}
            title="No modules reported"
            description="The backend did not return any role-based modules for this account."
          />
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {modules.map((module) => (
              <a
                key={module.key}
                href={resolveModuleHref(module.routes[0])}
                className="group rounded-lg border border-slate-700/60 bg-slate-950/60 p-4 transition hover:border-cyan-500/30 hover:bg-slate-900"
              >
                <p className="text-sm font-semibold text-white">{module.title}</p>
                <p className="mt-2 text-sm leading-6 text-slate-400">{module.description}</p>
                <p className="mt-4 inline-flex items-center gap-1 text-xs font-semibold uppercase text-cyan-300">
                  Open workspace
                  <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" />
                </p>
              </a>
            ))}
          </div>
        )}
      </PlatformPanel>

      <section className="grid gap-4 lg:grid-cols-2">
        <PlatformPanel title="Operational checklist">
          <ul className="space-y-3 text-sm leading-6 text-slate-300">
            <li>Review partner applications and approve only validated sponsor hierarchies.</li>
            <li>
              Use the CRM desk for backoffice intervention instead of editing records directly.
            </li>
            <li>Keep invitation issuance constrained to named campaigns and monitored usage.</li>
          </ul>
        </PlatformPanel>
        <PlatformPanel title="Fast access">
          <div className="flex flex-wrap gap-2">
            <a href={crmHref('dashboard')} className="platform-button platform-button-secondary">
              Open CRM
            </a>
            <a
              href={ibPortalHref('dashboard')}
              className="platform-button platform-button-secondary"
            >
              Open IB Portal
            </a>
            <Link to="/settings" className="platform-button platform-button-secondary">
              Open Settings
            </Link>
            <Link to="/admin/ico" className="platform-button platform-button-secondary">
              ICO Admin
            </Link>
          </div>
        </PlatformPanel>
      </section>

      <PlatformPanel
        title="Bot API gateway health"
        description="In-process counters for Go → Python bot API calls since last restart."
      >
        {botStatsQuery.isLoading ? (
          <p className="text-sm text-slate-400">Loading…</p>
        ) : botStatsQuery.isError ? (
          <p className="text-sm text-rose-400">Stats unavailable.</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-5 text-sm">
            {[
              { label: 'Total requests', value: botStatsQuery.data?.total_requests ?? 0 },
              { label: 'Successful', value: botStatsQuery.data?.successful_requests ?? 0 },
              { label: 'Failed', value: botStatsQuery.data?.failed_requests ?? 0 },
              {
                label: 'Avg latency (ms)',
                value: botStatsQuery.data?.average_latency_ms?.toFixed(1) ?? '—',
              },
              { label: 'Max latency (ms)', value: botStatsQuery.data?.max_latency_ms ?? 0 },
            ].map(({ label, value }) => (
              <div key={label} className="rounded border border-slate-700/50 bg-slate-900/60 p-3">
                <p className="text-xs text-slate-400">{label}</p>
                <p className="mt-1 text-lg font-semibold text-white">{value}</p>
              </div>
            ))}
          </div>
        )}
      </PlatformPanel>
    </PageContainer>
  );
};
