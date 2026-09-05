import { AlertTriangle } from 'lucide-react';
import { isRouteErrorResponse, useLocation, useNavigate, useRouteError } from 'react-router-dom';
import { PageContainer } from './PageContainer';
import { EmptyState } from './ui/PlatformUI';

/**
 * Route-level error boundary (React Router `errorElement`). A crash in one
 * screen renders this in place instead of blanking the whole application,
 * which is what the single global ErrorBoundary alone cannot do.
 */
export const RouteErrorBoundary = () => {
  const error = useRouteError();
  const location = useLocation();
  const navigate = useNavigate();

  let title = 'This screen could not be displayed';
  let description = `Something went wrong while rendering ${location.pathname}. The rest of the workspace is still available.`;

  if (isRouteErrorResponse(error)) {
    title = `${error.status} — ${error.statusText || 'Route error'}`;
    if (typeof error.data === 'string' && error.data) {
      description = error.data;
    } else if (error.data && typeof error.data === 'object' && 'message' in error.data) {
      description = String((error.data as { message?: unknown }).message ?? description);
    }
  } else if (error instanceof Error && error.message) {
    description = `${error.message} The rest of the workspace is still available.`;
  }

  return (
    <PageContainer size="wide">
      <div className="premium-panel">
        <EmptyState
          icon={AlertTriangle}
          title={title}
          description={description}
          action={
            <div className="flex flex-wrap items-center justify-center gap-3">
              <button
                type="button"
                className="platform-button platform-button-primary"
                onClick={() => navigate(0)}
              >
                Reload this page
              </button>
              <button
                type="button"
                className="platform-button platform-button-secondary"
                onClick={() => navigate('/dashboard')}
              >
                Back to dashboard
              </button>
            </div>
          }
        />
      </div>
    </PageContainer>
  );
};
