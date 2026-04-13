import {
  GitBranch,
  LayoutDashboard,
  Shield,
  Users,
  WalletCards,
  Workflow,
} from 'lucide-react';
import type { ReactNode } from 'react';
import { PortalSubnav, type PortalTab } from '../../components/ui/PlatformUI';
import { crmHref, crmPath, isCRMHost } from './paths';

const tabs: readonly PortalTab[] = [
  { path: crmPath('dashboard'), label: 'Dashboard', icon: LayoutDashboard },
  { path: crmPath('clients'), label: 'Clients', icon: Users, matchPrefix: crmPath('clients') },
  { path: crmPath('pipeline'), label: 'Pipeline', icon: Workflow },
  { path: crmPath('hierarchy'), label: 'Hierarchy', icon: GitBranch },
  { path: crmPath('commissions'), label: 'Commissions', icon: WalletCards },
  { path: crmPath('security'), label: 'Security', icon: Shield },
] as const;

interface CRMLayoutProps {
  children: ReactNode;
}

export const CRMLayout = ({ children }: CRMLayoutProps) => {
  const showSubdomainAction = !isCRMHost();
  const subdomainHref = crmHref('dashboard');

  return (
    <div className="flex min-h-0 flex-col">
      <PortalSubnav
        tabs={tabs}
        label="CRM backoffice"
        externalHref={showSubdomainAction ? subdomainHref : undefined}
      />

      <div className="flex-1">{children}</div>
    </div>
  );
};
