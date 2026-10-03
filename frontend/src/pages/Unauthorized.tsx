import { LockKeyhole } from 'lucide-react';
import { useEffect } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { getCurrentPortalType, getPortalAllowedRoles, getPortalLabel } from '../app/portal';
import { getUserWorkspaceRole, roleMatches } from '../auth/roles';
import { useToastStore } from '../components/ErrorBoundary';
import { PageContainer } from '../components/PageContainer';
import { EmptyState } from '../components/ui/PlatformUI';
import { useAuthStore } from '../store/auth';

export const UnauthorizedPage = () => {
  const portal = getCurrentPortalType();
  const user = useAuthStore((state) => state.user);
  const infoToast = useToastStore((state) => state.info);
  const role = getUserWorkspaceRole(user);

  const roleMatchesCurrentPortal = Boolean(
    user && roleMatches(role, getPortalAllowedRoles(portal))
  );

  // The requested route does not exist in this portal, but the user belongs
  // here — redirect home with an explanation instead of silently bouncing.
  useEffect(() => {
    if (roleMatchesCurrentPortal) {
      infoToast(
        'Not available in this workspace',
        `That page belongs to another portal. Returning you to your dashboard.`
      );
    }
  }, [roleMatchesCurrentPortal, infoToast]);

  if (roleMatchesCurrentPortal) {
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
