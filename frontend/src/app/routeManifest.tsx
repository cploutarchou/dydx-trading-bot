import { lazy, type ReactElement } from 'react';
import { Navigate } from 'react-router-dom';
import { BACKOFFICE_ROLES, CLIENT_ROLES, IB_ROLES, type WorkspaceRole } from '../auth/roles';
import type { AppPortalType } from './portal';

export interface PortalRouteDefinition {
  path: string;
  allowedRoles: WorkspaceRole[];
  element: ReactElement;
}

const BacktestComparator = lazy(() =>
  import('../components/BacktestComparator').then((module) => ({
    default: module.BacktestComparator,
  }))
);
const BotManager = lazy(() => import('../components/BotManager'));
const StrategyBuilder = lazy(() => import('../components/StrategyBuilder'));
const StrategyLibrary = lazy(() => import('../components/StrategyLibrary'));
const StrategyManager = lazy(() => import('../components/StrategyManager'));
const AdminHubPage = lazy(() =>
  import('../pages/AdminHub').then((module) => ({ default: module.AdminHubPage }))
);
const AdminCeleryPage = lazy(() =>
  import('../pages/AdminCelery').then((module) => ({ default: module.AdminCeleryPage }))
);
const BacktestDetailsV2 = lazy(() => import('../pages/BacktestDetailsV2'));
const BacktestsPage = lazy(() =>
  import('../pages/Backtests').then((module) => ({ default: module.BacktestsPage }))
);
const ClientAreaPage = lazy(() =>
  import('../pages/ClientArea').then((module) => ({ default: module.ClientAreaPage }))
);
const CodexPage = lazy(() =>
  import('../pages/Codex').then((module) => ({ default: module.CodexPage }))
);
const CRMRouter = lazy(() =>
  import('../pages/crm/index').then((module) => ({ default: module.CRMRouter }))
);
const DashboardPage = lazy(() =>
  import('../pages/Dashboard').then((module) => ({ default: module.DashboardPage }))
);
const ClientProfilePage = lazy(() =>
  import('../pages/client/ClientAccountPages').then((module) => ({
    default: module.ClientProfilePage,
  }))
);
const ClientSecurityPage = lazy(() =>
  import('../pages/client/ClientAccountPages').then((module) => ({
    default: module.ClientSecurityPage,
  }))
);
const IBRouter = lazy(() => import('../pages/ib').then((module) => ({ default: module.IBRouter })));
const NewsPage = lazy(() =>
  import('../pages/News').then((module) => ({ default: module.NewsPage }))
);
const SettingsPage = lazy(() => import('../pages/Settings'));

const clientRoutes: PortalRouteDefinition[] = [
  { path: '/dashboard', allowedRoles: CLIENT_ROLES, element: <DashboardPage /> },
  { path: '/client-area', allowedRoles: CLIENT_ROLES, element: <ClientAreaPage /> },
  { path: '/market-intel', allowedRoles: CLIENT_ROLES, element: <CodexPage /> },
  { path: '/market-intel/news', allowedRoles: CLIENT_ROLES, element: <NewsPage /> },
  { path: '/codex', allowedRoles: CLIENT_ROLES, element: <Navigate to="/market-intel" replace /> },
  {
    path: '/news',
    allowedRoles: CLIENT_ROLES,
    element: <Navigate to="/market-intel/news" replace />,
  },
  { path: '/backtests', allowedRoles: CLIENT_ROLES, element: <BacktestsPage view="dashboard" /> },
  { path: '/backtests/new', allowedRoles: CLIENT_ROLES, element: <BacktestsPage view="new" /> },
  { path: '/backtests/runs', allowedRoles: CLIENT_ROLES, element: <BacktestsPage view="runs" /> },
  {
    path: '/backtests/experiments',
    allowedRoles: CLIENT_ROLES,
    element: <BacktestsPage view="experiments" />,
  },
  { path: '/backtest/:runId', allowedRoles: CLIENT_ROLES, element: <BacktestDetailsV2 /> },
  { path: '/backtests/compare', allowedRoles: CLIENT_ROLES, element: <BacktestComparator /> },
  { path: '/strategies', allowedRoles: CLIENT_ROLES, element: <StrategyLibrary /> },
  { path: '/strategies/new', allowedRoles: CLIENT_ROLES, element: <StrategyBuilder /> },
  { path: '/strategies/manage', allowedRoles: CLIENT_ROLES, element: <StrategyManager /> },
  {
    path: '/strategies/managet',
    allowedRoles: CLIENT_ROLES,
    element: <Navigate to="/strategies/manage" replace />,
  },
  { path: '/strategies/:id/edit', allowedRoles: CLIENT_ROLES, element: <StrategyBuilder /> },
  { path: '/bots', allowedRoles: CLIENT_ROLES, element: <BotManager /> },
  {
    path: '/profile',
    allowedRoles: CLIENT_ROLES,
    element: <Navigate to="/settings?section=profile" replace />,
  },
  {
    path: '/security',
    allowedRoles: CLIENT_ROLES,
    element: <Navigate to="/settings?section=security" replace />,
  },
  {
    path: '/wallet',
    allowedRoles: CLIENT_ROLES,
    element: <Navigate to="/settings?section=dydx_keys" replace />,
  },
  { path: '/settings', allowedRoles: CLIENT_ROLES, element: <SettingsPage /> },
];

const backofficeRoutes: PortalRouteDefinition[] = [
  { path: '/dashboard', allowedRoles: BACKOFFICE_ROLES, element: <AdminHubPage /> },
  { path: '/admin', allowedRoles: BACKOFFICE_ROLES, element: <AdminHubPage /> },
  {
    path: '/admin/celery',
    allowedRoles: ['admin', 'super_admin', 'backoffice_admin'],
    element: <AdminCeleryPage />,
  },
  { path: '/crm/*', allowedRoles: BACKOFFICE_ROLES, element: <CRMRouter /> },
  { path: '/ib-portal/*', allowedRoles: BACKOFFICE_ROLES, element: <IBRouter /> },
  { path: '/settings', allowedRoles: BACKOFFICE_ROLES, element: <SettingsPage /> },
];

const ibPortalRoles: WorkspaceRole[] = [...IB_ROLES, ...BACKOFFICE_ROLES];

const ibRoutes: PortalRouteDefinition[] = [
  { path: '/profile', allowedRoles: ibPortalRoles, element: <ClientProfilePage /> },
  { path: '/security', allowedRoles: ibPortalRoles, element: <ClientSecurityPage /> },
  { path: '/*', allowedRoles: ibPortalRoles, element: <IBRouter /> },
];

export const getPortalRouteManifest = (portal: AppPortalType): PortalRouteDefinition[] => {
  switch (portal) {
    case 'backoffice':
      return backofficeRoutes;
    case 'ib':
      return ibRoutes;
    case 'client':
    default:
      return clientRoutes;
  }
};
