import { useQuery } from '@tanstack/react-query';
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Clock3,
  GitBranch,
  Network,
  Shield,
  Users,
  WalletCards,
  Workflow,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import api from '../../api';
import { PageContainer } from '../../components/PageContainer';
import {
  PlatformPageHeader,
  PlatformPanel,
  PlatformStatCard,
  StatusBadge,
} from '../../components/ui/PlatformUI';
import { formatUsdFixed } from '../../utils/format';
import { crmPath } from './paths';

export const CRMDashboard = () => {
  const summaryQuery = useQuery({
    queryKey: ['crm', 'summary'],
    queryFn: async () => (await api.getCRMSummary()).data,
    staleTime: 15_000,
    refetchInterval: 30_000,
  });

  const summary = summaryQuery.data;
  const isPending = summary && summary.pending_partner_applications > 0;

  const statCards = [
    {
      label: 'Active users',
      value: summary?.active_users ?? '—',
      icon: Users,
      color: 'text-cyan-300',
    },
    { label: 'Clients', value: summary?.clients ?? '—', icon: Clock3, color: 'text-slate-300' },
    { label: 'IBs', value: summary?.ibs ?? '—', icon: CheckCircle2, color: 'text-emerald-300' },
    {
      label: 'Sub-IBs',
      value: summary?.sub_ibs ?? '—',
      icon: CheckCircle2,
      color: 'text-teal-300',
    },
    {
      label: 'Hierarchy edges',
      value: summary?.hierarchy_edges ?? '—',
      icon: Network,
      color: 'text-violet-300',
    },
    {
      label: 'Net commissions',
      value: formatUsdFixed(summary?.net_commission_usd),
      icon: WalletCards,
      color: 'text-amber-300',
    },
  ] as const;

  const quickLinks = [
    {
      to: crmPath('clients'),
      icon: Users,
      label: 'Client directory',
      description: 'Search and manage all users, roles, and MFA state.',
      color: 'text-cyan-300 border-cyan-500/20 bg-cyan-500/5 hover:bg-cyan-500/10',
    },
    {
      to: crmPath('pipeline'),
      icon: Workflow,
      label: 'Application pipeline',
      description: 'Review and approve incoming IB / sub-IB upgrade requests.',
      color: 'text-amber-300 border-amber-500/20 bg-amber-500/5 hover:bg-amber-500/10',
      badge: summary?.pending_partner_applications ?? 0,
    },
    {
      to: crmPath('hierarchy'),
      icon: GitBranch,
      label: 'Sponsor hierarchy',
      description: 'Inspect the partner network tree and edge relationships.',
      color: 'text-violet-300 border-violet-500/20 bg-violet-500/5 hover:bg-violet-500/10',
    },
    {
      to: crmPath('commissions'),
      icon: WalletCards,
      label: 'Commission manager',
      description: 'Record and update IB rebate and notional volume metrics.',
      color: 'text-emerald-300 border-emerald-500/20 bg-emerald-500/5 hover:bg-emerald-500/10',
    },
    {
      to: crmPath('security'),
      icon: Shield,
      label: 'Security events',
      description: 'Monitor authentication outcomes and access anomalies.',
      color: 'text-red-300 border-red-500/20 bg-red-500/5 hover:bg-red-500/10',
    },
  ] as const;

  return (
    <PageContainer size="wide" className="space-y-6">
      <PlatformPageHeader
        kicker="CRM Backoffice"
        title="Client relationship dashboard"
        description="Monitor active users, partner onboarding, sponsor networks, commissions, and security posture in one operating view."
        icon={Users}
        actions={[{ label: 'Review pipeline', to: crmPath('pipeline') }]}
      />

      {isPending && (
        <div className="flex items-center gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4">
          <AlertCircle className="h-5 w-5 shrink-0 text-amber-300" />
          <div className="flex-1">
            <p className="text-sm font-medium text-amber-200">
              {summary.pending_partner_applications} application
              {summary.pending_partner_applications !== 1 ? 's' : ''} awaiting review
            </p>
            <p className="mt-0.5 text-xs text-amber-300/70">
              New partner upgrade requests are pending your attention.
            </p>
          </div>
          <Link
            to={crmPath('pipeline')}
            className="platform-button platform-button-secondary shrink-0 text-amber-200"
          >
            Review now <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-6">
        {statCards.map((card) => (
          <PlatformStatCard
            key={card.label}
            label={card.label}
            value={card.value}
            icon={card.icon}
            loading={summaryQuery.isLoading}
            tone={
              card.label === 'Net commissions'
                ? 'warning'
                : card.label === 'IBs' || card.label === 'Sub-IBs'
                  ? 'success'
                  : card.label === 'Hierarchy edges'
                    ? 'violet'
                    : 'accent'
            }
          />
        ))}
      </div>

      <PlatformPanel
        title="Backoffice workflows"
        description="High-traffic CRM paths grouped by the decisions operators need to make."
      >
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {quickLinks.map((link) => {
            const Icon = link.icon;
            return (
              <Link
                key={link.to}
                to={link.to}
                className={`group flex items-start gap-4 rounded-lg border p-5 transition ${link.color}`}
              >
                <div className="mt-0.5 shrink-0">
                  <Icon className={`h-5 w-5 ${link.color.split(' ')[0]}`} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-semibold text-white">{link.label}</p>
                    {'badge' in link && link.badge > 0 && (
                      <StatusBadge tone="warning">{link.badge}</StatusBadge>
                    )}
                  </div>
                  <p className="mt-1 text-xs leading-5 text-slate-400">{link.description}</p>
                </div>
                <ArrowRight className="h-4 w-4 shrink-0 translate-x-0 text-slate-600 transition-transform group-hover:translate-x-1" />
              </Link>
            );
          })}
        </div>
      </PlatformPanel>
    </PageContainer>
  );
};
