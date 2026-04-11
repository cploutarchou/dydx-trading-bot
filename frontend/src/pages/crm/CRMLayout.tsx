import { GitBranch, LayoutDashboard, Shield, Users, WalletCards, Workflow } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { crmPath } from './paths';

const tabs = [
  { path: crmPath('dashboard'), label: 'Dashboard', icon: LayoutDashboard },
  { path: crmPath('clients'), label: 'Clients', icon: Users },
  { path: crmPath('pipeline'), label: 'Pipeline', icon: Workflow },
  { path: crmPath('hierarchy'), label: 'Hierarchy', icon: GitBranch },
  { path: crmPath('commissions'), label: 'Commissions', icon: WalletCards },
  { path: crmPath('security'), label: 'Security', icon: Shield },
] as const;

interface CRMLayoutProps {
  children: ReactNode;
}

export const CRMLayout = ({ children }: CRMLayoutProps) => {
  const { pathname } = useLocation();
  const clientsPath = crmPath('clients');

  const activeTab = tabs.find((tab) =>
    tab.path === clientsPath ? pathname.startsWith(clientsPath) : pathname.startsWith(tab.path)
  );

  return (
    <div className="flex min-h-0 flex-col">
      {/* CRM secondary navigation */}
      <div className="sticky top-0 z-20 border-b border-slate-800/80 bg-slate-950/95 backdrop-blur">
        <div className="flex items-center gap-1 overflow-x-auto px-4 py-1 scrollbar-none">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive =
              tab.path === clientsPath
                ? pathname.startsWith(clientsPath)
                : pathname.startsWith(tab.path);
            return (
              <Link
                key={tab.path}
                to={tab.path}
                className={`flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-cyan-500/15 text-cyan-200'
                    : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                {tab.label}
              </Link>
            );
          })}
          {activeTab && (
            <div className="ml-auto flex items-center">
              <span className="rounded-full border border-slate-700/60 bg-slate-800/60 px-2.5 py-0.5 text-[10px] uppercase tracking-[0.14em] text-slate-400">
                CRM backoffice
              </span>
            </div>
          )}
        </div>
      </div>

      <div className="flex-1">{children}</div>
    </div>
  );
};
