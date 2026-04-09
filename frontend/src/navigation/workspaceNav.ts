import {
  BarChart3,
  Bot,
  BriefcaseBusiness,
  Building2,
  Home,
  KeyRound,
  Library,
  type LucideIcon,
  Newspaper,
  PlayCircle,
  PlusCircle,
  Settings,
  ShieldCheck,
  Sparkles,
  Target,
} from 'lucide-react';
import { roleMatches, type WorkspaceRole } from '../auth/roles';

export interface WorkspaceNavItem {
  label: string;
  path: string;
  description: string;
  section: 'Cockpit' | 'Execute' | 'Research' | 'System';
  keywords: string[];
  exact?: boolean;
  icon: LucideIcon;
  shortcut?: string;
  allowedRoles?: WorkspaceRole[];
}

export const workspaceNavItems: WorkspaceNavItem[] = [
  {
    label: 'Dashboard',
    path: '/dashboard',
    description: 'Portfolio overview, active runs, market pulse, and quick launch.',
    section: 'Cockpit',
    keywords: ['home', 'overview', 'kpi', 'pulse'],
    exact: true,
    icon: Home,
    shortcut: 'G D',
  },
  {
    label: 'Client Area',
    path: '/client-area',
    description: 'Onboarding, account progression, and partner upgrade requests.',
    section: 'Cockpit',
    keywords: ['client', 'account', 'onboarding', 'promotion'],
    exact: true,
    icon: Building2,
    shortcut: 'G C',
  },
  {
    label: 'Backtests',
    path: '/backtests',
    description: 'Explore backtest runs, rankings, and strategy intelligence.',
    section: 'Execute',
    keywords: ['runs', 'simulation', 'history', 'results'],
    exact: true,
    icon: Target,
    shortcut: 'G B',
  },
  {
    label: 'Compare Backtests',
    path: '/backtests/compare',
    description: 'Compare multiple runs and inspect relative performance.',
    section: 'Execute',
    keywords: ['compare', 'benchmark', 'versus'],
    exact: false,
    icon: BarChart3,
  },
  {
    label: 'Strategies',
    path: '/strategies',
    description: 'Browse and organize reusable trading strategies.',
    section: 'Execute',
    keywords: ['library', 'templates', 'alpha'],
    exact: true,
    icon: Library,
    shortcut: 'G S',
  },
  {
    label: 'Strategy Runtime',
    path: '/strategies/manage',
    description: 'Monitor live strategy runtime state and execution health.',
    section: 'Execute',
    keywords: ['runtime', 'signals', 'live', 'manage'],
    exact: false,
    icon: PlayCircle,
  },
  {
    label: 'Bot Manager',
    path: '/bots',
    description: 'Operate bot instances, runtime health, and control flows.',
    section: 'Execute',
    keywords: ['instances', 'operator', 'deploy'],
    exact: false,
    icon: Bot,
    shortcut: 'G O',
  },
  {
    label: 'Market Intel',
    path: '/codex',
    description: 'AI-assisted asset intelligence and research context.',
    section: 'Research',
    keywords: ['intel', 'codex', 'analysis', 'assets'],
    exact: true,
    icon: Sparkles,
  },
  {
    label: 'Market News',
    path: '/news',
    description: 'News flow, narratives, and market context.',
    section: 'Research',
    keywords: ['news', 'headlines', 'coindesk'],
    exact: true,
    icon: Newspaper,
  },
  {
    label: 'CRM',
    path: '/crm',
    description: 'Backoffice workflows for clients, IB approvals, and partner reviews.',
    section: 'System',
    keywords: ['crm', 'backoffice', 'approvals', 'partners'],
    exact: true,
    icon: BriefcaseBusiness,
    shortcut: 'G R',
    allowedRoles: ['admin', 'backoffice'],
  },
  {
    label: 'Settings',
    path: '/settings',
    description: 'Operator preferences, credentials, integrations, and system config.',
    section: 'System',
    keywords: ['preferences', 'config', 'auth', 'keys'],
    exact: false,
    icon: Settings,
    shortcut: 'G ,',
  },
  {
    label: 'IB Portal',
    path: '/ib-portal',
    description: 'Invitation tokens and Introducing Broker onboarding operations.',
    section: 'System',
    keywords: ['ib', 'invites', 'tokens', 'partners', 'onboarding'],
    exact: true,
    icon: KeyRound,
    shortcut: 'G I',
    allowedRoles: ['admin', 'backoffice', 'ib', 'sub_ib'],
  },
  {
    label: 'Admin Hub',
    path: '/admin',
    description: 'Platform operating center for access, controls, and cross-portal oversight.',
    section: 'System',
    keywords: ['admin', 'hub', 'controls', 'governance'],
    exact: true,
    icon: ShieldCheck,
    shortcut: 'G A',
    allowedRoles: ['admin'],
  },
];

export const workspaceQuickActions: WorkspaceNavItem[] = [
  {
    label: 'New Strategy',
    path: '/strategies/new',
    description: 'Create a fresh strategy blueprint.',
    section: 'Execute',
    keywords: ['create', 'new', 'builder', 'strategy'],
    exact: false,
    icon: PlusCircle,
    shortcut: 'N S',
  },
  ...workspaceNavItems.filter((item) =>
    ['/backtests', '/bots', '/strategies/manage'].includes(item.path)
  ),
];

export const workspaceSections: Array<WorkspaceNavItem['section']> = [
  'Cockpit',
  'Execute',
  'Research',
  'System',
];

export const filterNavItemsForRole = (
  items: WorkspaceNavItem[],
  role: WorkspaceRole
): WorkspaceNavItem[] => items.filter((item) => roleMatches(role, item.allowedRoles));

export const isNavItemActive = (pathname: string, item: WorkspaceNavItem): boolean =>
  item.exact ? pathname === item.path : pathname.startsWith(item.path);

export const getWorkspaceBreadcrumbs = (pathname: string) => {
  const paths = pathname.split('/').filter(Boolean);
  const breadcrumbs = [{ label: 'Home', path: '/dashboard' }];

  if (paths.includes('settings')) {
    breadcrumbs.push({ label: 'Settings', path: '/settings' });
  } else if (paths.includes('admin')) {
    breadcrumbs.push({ label: 'Admin Hub', path: '/admin' });
  } else if (paths.includes('crm')) {
    breadcrumbs.push({ label: 'CRM', path: '/crm' });
  } else if (paths.includes('client-area')) {
    breadcrumbs.push({ label: 'Client Area', path: '/client-area' });
  } else if (paths.includes('ib-portal')) {
    breadcrumbs.push({ label: 'IB Portal', path: '/ib-portal' });
  } else if (paths.includes('backtests') || paths.includes('backtest')) {
    const backtestIndex = paths.findIndex(
      (segment) => segment === 'backtests' || segment === 'backtest'
    );
    const runId = backtestIndex >= 0 ? paths[backtestIndex + 1] : undefined;

    breadcrumbs.push({ label: 'Backtests', path: '/backtests' });

    if (runId && runId !== 'compare') {
      breadcrumbs.push({ label: `Run ${runId}`, path: `/backtest/${runId}` });
    } else if (runId === 'compare') {
      breadcrumbs.push({ label: 'Compare Backtests', path: '/backtests/compare' });
    }
  } else if (paths.includes('strategies')) {
    breadcrumbs.push({ label: 'Strategies', path: '/strategies' });
    if (paths.includes('manage')) {
      breadcrumbs.push({ label: 'Strategy Runtime', path: '/strategies/manage' });
    } else if (paths.includes('new')) {
      breadcrumbs.push({ label: 'New Strategy', path: '/strategies/new' });
    } else if (paths.includes('edit')) {
      const strategyId = paths[paths.indexOf('edit') - 1];
      breadcrumbs.push({
        label: `Edit Strategy ${strategyId}`,
        path: `/strategies/${strategyId}/edit`,
      });
    }
  } else if (paths.includes('bots')) {
    breadcrumbs.push({ label: 'Bot Manager', path: '/bots' });
  } else if (paths.includes('codex')) {
    breadcrumbs.push({ label: 'Market Intel', path: '/codex' });
  } else if (paths.includes('news')) {
    breadcrumbs.push({ label: 'Market News', path: '/news' });
  }

  return breadcrumbs;
};
