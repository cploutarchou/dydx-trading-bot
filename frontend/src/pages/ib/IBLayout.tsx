import {
  KeyRound,
  LayoutDashboard,
  Network,
  Percent,
  ScrollText,
  WalletCards,
} from 'lucide-react';
import type { ReactNode } from 'react';
import { BACKOFFICE_ROLES, getUserWorkspaceRole, roleMatches } from '../../auth/roles';
import { PortalSubnav, type PortalTab } from '../../components/ui/PlatformUI';
import { useAuthStore } from '../../store/auth';
import { ibPortalHref, ibPortalPath, isIBPortalHost } from './paths';

const baseTabs: readonly PortalTab[] = [
  { path: ibPortalPath('dashboard'), label: 'Dashboard', icon: LayoutDashboard },
  { path: ibPortalPath('network'), label: 'My Network', icon: Network },
  { path: ibPortalPath('applications'), label: 'Applications', icon: ScrollText },
  { path: ibPortalPath('commissions'), label: 'Commissions', icon: WalletCards },
] as const;

const adminTabs: readonly PortalTab[] = [
  { path: ibPortalPath('tokens'), label: 'Tokens', icon: KeyRound },
  { path: ibPortalPath('tier-rates'), label: 'Tier Rates', icon: Percent },
] as const;

interface IBLayoutProps {
  children: ReactNode;
}

export const IBLayout = ({ children }: IBLayoutProps) => {
  const user = useAuthStore((state) => state.user);
  const showSubdomainAction = !isIBPortalHost();
  const subdomainHref = ibPortalHref('dashboard');

  const canSeeAdminTabs = roleMatches(getUserWorkspaceRole(user), BACKOFFICE_ROLES);
  const tabs = canSeeAdminTabs ? [...baseTabs, ...adminTabs] : baseTabs;

  return (
    <div className="flex min-h-0 flex-col">
      <PortalSubnav
        tabs={tabs}
        label="IB portal"
        externalHref={showSubdomainAction ? subdomainHref : undefined}
      />

      <div className="flex-1">{children}</div>
    </div>
  );
};
