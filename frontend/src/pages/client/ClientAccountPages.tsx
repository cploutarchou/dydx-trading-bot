import { KeyRound, LockKeyhole, UserCircle, WalletCards } from 'lucide-react';
import { AuthSettingsComponent } from '../../components/AuthSettings';
import { DYDXKeyManager } from '../../components/DYDXKeyManager';
import { PageContainer } from '../../components/PageContainer';
import { ProfileSettings } from '../../components/ProfileSettings';
import { PlatformPageHeader } from '../../components/ui/PlatformUI';

export const ClientProfilePage = () => (
  <PageContainer size="wide" className="space-y-6">
    <PlatformPageHeader
      kicker="Client Portal"
      title="Profile"
      description="Update your personal profile and contact details."
      icon={UserCircle}
    />
    <ProfileSettings />
  </PageContainer>
);

export const ClientSecurityPage = () => (
  <PageContainer size="wide" className="space-y-6">
    <PlatformPageHeader
      kicker="Client Portal"
      title="Security"
      description="Manage two-factor authentication and session security for your account."
      icon={LockKeyhole}
    />
    <AuthSettingsComponent />
  </PageContainer>
);

export const ClientWalletPage = () => (
  <PageContainer size="wide" className="space-y-6">
    <PlatformPageHeader
      kicker="Client Portal"
      title="Wallet & API Keys"
      description="Manage client-facing wallet access and dYdX API credentials."
      icon={WalletCards}
      meta={
        <span className="inline-flex items-center gap-2 rounded-lg border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-xs font-semibold text-cyan-200">
          <KeyRound className="h-3.5 w-3.5" />
          Client scoped
        </span>
      }
    />
    <DYDXKeyManager />
  </PageContainer>
);
