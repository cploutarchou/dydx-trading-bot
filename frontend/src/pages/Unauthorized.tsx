import { LockKeyhole } from 'lucide-react';
import { Link } from 'react-router-dom';
import { getCurrentPortalType, getPortalLabel } from '../app/portal';
import { PageContainer } from '../components/PageContainer';
import { EmptyState } from '../components/ui/PlatformUI';

export const UnauthorizedPage = () => {
  const portal = getCurrentPortalType();

  return (
    <PageContainer size="wide">
      <div className="premium-panel">
        <EmptyState
          icon={LockKeyhole}
          title="Unauthorized"
          description={`Your current role does not have access to the ${getPortalLabel(portal)} surface or the requested page.`}
          action={
            <Link to="/dashboard" className="platform-button platform-button-secondary">
              Return to dashboard
            </Link>
          }
        />
      </div>
    </PageContainer>
  );
};
