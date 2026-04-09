import { useQuery } from '@tanstack/react-query';
import { Activity, LockKeyhole, Users, Workflow } from 'lucide-react';
import { Link } from 'react-router-dom';
import api from '../api';
import { PageContainer } from '../components/PageContainer';

export const AdminHubPage = () => {
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

  const modules = overviewQuery.data?.modules ?? [];

  return (
    <PageContainer size="wide" className="space-y-6">
      <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-6">
        <div className="premium-kicker">Admin Hub</div>
        <h1 className="mt-2 text-2xl font-semibold text-white">
          Platform operations command center
        </h1>
        <p className="mt-2 text-sm text-slate-400">
          One place to oversee access, partner growth, CRM flow, and the rest of the platform
          machinery humming behind the curtain.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        {[
          { label: 'Active users', value: summaryQuery.data?.active_users ?? 0, icon: Users },
          {
            label: 'Pending partner apps',
            value: summaryQuery.data?.pending_partner_applications ?? 0,
            icon: Workflow,
          },
          { label: 'Portal modules', value: modules.length, icon: Activity },
          { label: 'Security surfaces', value: 3, icon: LockKeyhole },
        ].map((card) => {
          const Icon = card.icon;
          return (
            <div
              key={card.label}
              className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4"
            >
              <div className="flex items-center gap-2 text-slate-300">
                <Icon className="h-4 w-4 text-cyan-300" /> {card.label}
              </div>
              <p className="mt-3 text-2xl font-semibold text-white">{card.value}</p>
            </div>
          );
        })}
      </div>

      <section className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
        <h2 className="text-lg font-semibold text-white">Role-based workspaces</h2>
        <p className="mt-1 text-sm text-slate-400">
          These are the live surfaces the current admin account can jump into.
        </p>
        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {modules.map((module) => (
            <Link
              key={module.key}
              to={module.routes[0] || '/dashboard'}
              className="rounded-2xl border border-slate-700/60 bg-slate-950/60 p-4 transition hover:border-cyan-500/30 hover:bg-slate-900"
            >
              <p className="text-sm font-semibold text-white">{module.title}</p>
              <p className="mt-2 text-sm text-slate-400">{module.description}</p>
              <p className="mt-4 text-xs uppercase tracking-[0.16em] text-cyan-300">
                Open workspace
              </p>
            </Link>
          ))}
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
          <h2 className="text-lg font-semibold text-white">Operational checklist</h2>
          <ul className="mt-4 space-y-3 text-sm text-slate-300">
            <li>Review partner applications and approve only validated sponsor hierarchies.</li>
            <li>
              Use the CRM desk for backoffice intervention instead of editing records directly.
            </li>
            <li>Keep invitation issuance constrained to named campaigns and monitored usage.</li>
          </ul>
        </div>
        <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5">
          <h2 className="text-lg font-semibold text-white">Fast access</h2>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link
              to="/crm"
              className="rounded-xl border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-200 transition hover:border-cyan-500/30"
            >
              Open CRM
            </Link>
            <Link
              to="/ib-portal"
              className="rounded-xl border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-200 transition hover:border-cyan-500/30"
            >
              Open IB Portal
            </Link>
            <Link
              to="/settings"
              className="rounded-xl border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-200 transition hover:border-cyan-500/30"
            >
              Open Settings
            </Link>
          </div>
        </div>
      </section>
    </PageContainer>
  );
};
