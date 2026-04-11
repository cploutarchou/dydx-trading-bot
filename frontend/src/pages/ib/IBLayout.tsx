import {
  ExternalLink,
  KeyRound,
  LayoutDashboard,
  Network,
  Percent,
  ScrollText,
  WalletCards,
} from 'lucide-react';
import type { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../store/auth';
import { ibPortalHref, ibPortalPath, isIBPortalHost } from './paths';

const baseTabs = [
  { path: ibPortalPath('dashboard'), label: 'Dashboard', icon: LayoutDashboard },
  { path: ibPortalPath('network'), label: 'My Network', icon: Network },
  { path: ibPortalPath('applications'), label: 'Applications', icon: ScrollText },
  { path: ibPortalPath('commissions'), label: 'Commissions', icon: WalletCards },
] as const;

const adminTabs = [
  { path: ibPortalPath('tokens'), label: 'Tokens', icon: KeyRound },
  { path: ibPortalPath('tier-rates'), label: 'Tier Rates', icon: Percent },
] as const;

interface IBLayoutProps {
  children: ReactNode;
}

export const IBLayout = ({ children }: IBLayoutProps) => {
  const { pathname } = useLocation();
  const user = useAuthStore((state) => state.user);
  const showSubdomainAction = !isIBPortalHost();
  const subdomainHref = ibPortalHref('dashboard');

  const canSeeAdminTabs = user?.is_admin === true || user?.role === 'backoffice';
  const tabs = canSeeAdminTabs
    ? ([...baseTabs, ...adminTabs] as const)
    : (baseTabs as readonly (typeof baseTabs)[number][]);

  return (
    <div className="flex min-h-0 flex-col">
      {/* IB Portal secondary navigation */}
      <div className="sticky top-0 z-20 border-b border-slate-800/80 bg-slate-950/95 backdrop-blur">
        <div className="flex items-center gap-1 overflow-x-auto px-4 py-1 scrollbar-none">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = pathname.startsWith(tab.path);
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
          <div className="ml-auto flex items-center gap-2">
            {showSubdomainAction && subdomainHref.startsWith('http') && (
              <a
                href={subdomainHref}
                className="inline-flex items-center gap-1 rounded-lg border border-cyan-600/30 bg-cyan-900/20 px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-cyan-200 transition hover:bg-cyan-900/35"
              >
                <ExternalLink className="h-3 w-3" /> Open in subdomain
              </a>
            )}
            <span className="rounded-full border border-slate-700/60 bg-slate-800/60 px-2.5 py-0.5 text-[10px] uppercase tracking-[0.14em] text-slate-400">
              IB portal
            </span>
          </div>
        </div>
      </div>

      <div className="flex-1">{children}</div>
    </div>
  );
};
