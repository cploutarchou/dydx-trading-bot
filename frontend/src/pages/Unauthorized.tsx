import { LockKeyhole } from 'lucide-react';
import { Link, Navigate } from 'react-router-dom';
import { getCurrentPortalType, getPortalAllowedRoles, getPortalLabel } from '../app/portal';
import { getUserWorkspaceRole, roleMatches } from '../auth/roles';
import { PageContainer } from '../components/PageContainer';
import { EmptyState } from '../components/ui/PlatformUI';
import { useAuthStore } from '../store/auth';

export const UnauthorizedPage = () => {
  const portal = getCurrentPortalType();
  const user = useAuthStore((state) => state.user);
  const role = getUserWorkspaceRole(user);

  if (user && roleMatches(role, getPortalAllowedRoles(portal))) {
    return <Navigate to="/dashboard" replace />;
  }

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
